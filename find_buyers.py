#!/usr/bin/env python3
"""Find regulatory buyers to contact. One command, no setup.

    python3 find_buyers.py

Edit `target.yaml` to change where and what you are looking for.
Edit `icp/weights.yaml` to change what each signal is worth.

Everything comes from openFDA - the FDA's own public API. No key, no licence,
no scraping, no paid enrichment. Every person returned carries a link to the
government record they were found on.

What it does
------------
  1. Pulls 510(k) clearances for your states and date window. A clearance is a
     dated, public record that a technical file was assembled and reviewed -
     and the submission names the regulatory contact who did it.
  2. Pulls recalls for the same region, and classifies each one by cause -
     separating documentation failures (a label, an IFU, a stated dimension)
     from manufacturing defects. A documentation recall is one document
     contradicting another.
  3. Scores every company through icp/weights.yaml and ranks them.
  4. Prints the people to contact, with the reason and the source.

What it cannot do
-----------------
openFDA carries no headcount, no EU MDR/IVDR status and no funding data. Those
are marked for verification rather than guessed. An unknown is recorded as an
unknown - a model that accepts vibes produces a pipeline built on vibes.
"""

import csv
import datetime as dt
import glob
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fda"))
sys.path.insert(0, os.path.join(HERE, "icp"))

import openfda            # noqa: E402
import fetch_510k         # noqa: E402
import fetch_enforcement  # noqa: E402
import build_cohort       # noqa: E402
import score as scorer    # noqa: E402

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
GREEN, YELLOW, RED, CYAN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"

TIER_COLOUR = {"A": RED, "B": YELLOW, "C": CYAN, "D": DIM}


def c(text, colour):
    return text if not sys.stdout.isatty() else "%s%s%s" % (colour, text, RESET)


def load_target(path):
    cfg = scorer.load_yaml(path)
    cfg.setdefault("states", ["NC"])
    cfg.setdefault("clearance_months", 18)
    cfg.setdefault("recall_years", 6)
    cfg.setdefault("require_named_contact", True)
    cfg.setdefault("min_clearances", 1)
    cfg.setdefault("exclude_giants", True)
    cfg.setdefault("exclude_also", [])
    cfg.setdefault("top", 25)
    cfg.setdefault("out", None)
    cfg.setdefault("csv", None)
    return cfg


def linkedin_search(person, company):
    """A LinkedIn people-search link. Not a scraped profile: LinkedIn's terms
    forbid automated lookup, so this opens the search for a human to confirm."""
    keywords = "%s %s" % (person, openfda.normalise(company))
    return "https://www.linkedin.com/search/results/people/?" + urllib.parse.urlencode(
        {"keywords": keywords})


FRESH_DAYS = 180

MATCH_NOTE = (
    "**ICP match** counts only the criteria that separate one company from "
    "another: continuous filer (2+ clearances in the window), fresh clearance "
    "(last %d days), and a documentation recall on record. Every company listed "
    "has already passed the search filters (legal manufacturer, FDA Class II "
    "device, in target states, named regulatory contact), so those are not "
    "counted - they would add the same points to everyone. Headcount (30–400) "
    "and ownership (not a subsidiary) cannot be checked from FDA data and are "
    "never counted - verify those by hand." % FRESH_DAYS
)


def has_doc_recall(account):
    return any(s["id"] == "documentation_or_labelling_recall_fsca"
               for s in account.get("signals", []))


def icp_match(account, comp):
    """How strongly this company matches the ICP, from FDA data.

    Only criteria that differ between companies are counted. The search filters
    (legal manufacturer, Class II device, target states, named contact) are met
    by everyone listed, so counting them would inflate every score equally.
    Headcount and ownership are left out rather than assumed, so 100% means
    'every differentiating signal FDA data can show is present', never
    'confirmed fit'.
    """
    age = build_cohort.age_days(comp.get("latest_clearance", ""))
    checks = [
        ("continuous filer", comp.get("clearance_count", 0) >= 2),
        ("fresh clearance", age is not None and age <= FRESH_DAYS),
        ("documentation recall", has_doc_recall(account)),
    ]
    met = sum(1 for _, ok in checks if ok)
    return {
        "met": met,
        "total": len(checks),
        "pct": round(100.0 * met / len(checks)),
        "missing": [label for label, ok in checks if not ok],
    }


def pct(part, whole):
    return "%d%%" % round(100.0 * part / whole) if whole else "0%"


def summary_lines(s, cfg):
    return [
        ("FDA clearance records searched", "{:,}".format(s["clearance_records"])),
        ("FDA recall records searched", "{:,}".format(s["recall_records"])),
        ("Manufacturers found", "{:,}".format(s["found"])),
        ("  removed: too large / known subsidiary", "%d  (%s)" % (s["giant"], pct(s["giant"], s["found"]))),
        ("  removed: no named regulatory contact", "%d  (%s)" % (s["no_contact"], pct(s["no_contact"], s["found"]))),
        ("  removed: fewer than %d clearance(s)" % cfg["min_clearances"],
         "%d  (%s)" % (s["few_clearances"], pct(s["few_clearances"], s["found"]))),
        ("Match your ICP filters", "%d  (%s of manufacturers found)" % (s["matched"], pct(s["matched"], s["found"]))),
        ("  with a documentation recall", "%d  (%s)" % (s["doc_pain"], pct(s["doc_pain"], s["matched"]))),
        ("Shown", "%d  (top %d by score)" % (s["shown"], cfg["top"])),
        ("Average ICP match of those shown", "%d%%" % round(s["avg_match"])),
    ]


def load_checks():
    """Hand checks from out/verification-*.json, keyed by normalised company."""
    checks = {}
    for path in sorted(glob.glob(os.path.join(HERE, "out", "verification-*.json"))):
        with open(path) as f:
            for name, v in json.load(f).get("companies", {}).items():
                checks[openfda.normalise(name)] = v
    return checks


def check_status(company, checks):
    v = checks.get(openfda.normalise(company))
    if v is None:
        return "Not checked yet", False
    if v.get("disqualified"):
        reason = v["disqualified"].split(":", 1)[-1].strip()
        return "Ruled out: " + reason, True
    if v.get("headcount") is None:
        return "Checked: good fit, headcount not confirmed", False
    return "Checked: good fit (~%d staff)" % v["headcount"], False


def write_csv(path, rows, checks, cfg):
    records = []
    for result, account, comp, match in rows:
        status, ruled_out = check_status(account["company"], checks)
        person = comp["contacts"][0] if comp.get("contacts") else None
        name = person["name"] if person else ""
        records.append((ruled_out, -result["composite"], [
            name,
            account["company"],
            account["hq"],
            "%d%%" % match["pct"],
            "%.1f" % result["composite"],
            headline_trigger(account),
            ", ".join(match["missing"]) or "none",
            comp.get("clearance_count", 0),
            comp.get("latest_clearance", ""),
            "yes" if has_doc_recall(account) else "no",
            status,
            person["url"] if person else "",
            linkedin_search(name, account["company"]) if person else "",
        ]))
    # Ruled-out companies go to the bottom so the sheet opens on live accounts.
    records.sort(key=lambda r: (r[0], r[1]))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "Rank", "Person to contact", "Company", "Location", "ICP match",
            "Score", "Why they're worth contacting", "Signals missing",
            "Clearances (last %d months)" % cfg["clearance_months"],
            "Latest clearance", "Documentation recall", "Checked by hand",
            "FDA record", "LinkedIn search",
        ])
        for i, (_, _, row) in enumerate(records, 1):
            w.writerow([i] + row)
    return len(records)


def headline_trigger(account):
    """The one sentence explaining why this company is worth a call today."""
    best = None
    for s in account.get("signals", []):
        if s["id"] == "documentation_or_labelling_recall_fsca":
            return "Documentation recall - " + s["evidence"]
        if s["id"] == "new_udi_di_or_510k_filed" and best is None:
            best = "Recent clearance - " + s["evidence"]
    return best or "No dated trigger - fit only, do not sell yet"


def main():
    target_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "target.yaml")
    if not os.path.exists(target_path):
        print("Cannot find %s" % target_path, file=sys.stderr)
        return 1

    cfg = load_target(target_path)
    weights = scorer.load_yaml(os.path.join(HERE, "icp", "weights.yaml"))

    states = [str(s).upper() for s in cfg["states"]]
    extra = [str(x).lower() for x in (cfg.get("exclude_also") or [])]
    if extra:
        openfda.GIANTS.extend(extra)
    if not cfg["exclude_giants"]:
        openfda.GIANTS = list(extra)

    print()
    print(c("  Searching openFDA", BOLD))
    print(c("  states           %s" % "/".join(states), DIM))
    print(c("  clearances       last %d months" % cfg["clearance_months"], DIM))
    print(c("  recalls          last %d years" % cfg["recall_years"], DIM))
    print()

    print("  [1/3] 510(k) clearances + named regulatory contacts...", flush=True)
    found = fetch_510k.fetch(states, cfg["clearance_months"], include_giants=True)

    print("  [2/3] recalls, classified by cause...", flush=True)
    recalls = fetch_enforcement.fetch(states=states, years=cfg["recall_years"],
                                      max_records=2000)
    by_key = {openfda.normalise(r["firm"]): r for r in recalls}

    print("  [3/3] scoring against icp/weights.yaml...", flush=True)
    funnel = {"giant": 0, "no_contact": 0, "few_clearances": 0}
    rows = []
    for comp in found:
        if openfda.is_giant(comp["company"]):
            funnel["giant"] += 1
            continue
        if cfg["require_named_contact"] and not comp.get("contacts"):
            funnel["no_contact"] += 1
            continue
        if comp["clearance_count"] < cfg["min_clearances"]:
            funnel["few_clearances"] += 1
            continue
        account = build_cohort.build(comp, by_key)
        # Headcount is unknown from openFDA, so the gate cannot pass yet.
        # Score the evidence we do have rather than reporting a gate failure.
        account["gates"].pop("headcount_in_band", None)
        result = scorer.evaluate(account, weights)
        rows.append((result, account, comp, icp_match(account, comp)))

    rows.sort(key=lambda r: r[0]["composite"], reverse=True)
    shown = rows[:cfg["top"]]

    stats = {
        "clearance_records": sum(x["clearance_count"] for x in found),
        "recall_records": sum(x["event_count"] for x in recalls),
        "found": len(found),
        "matched": len(rows),
        "shown": len(shown),
        "doc_pain": sum(1 for r in rows if has_doc_recall(r[1])),
        "avg_match": (sum(r[3]["pct"] for r in shown) / len(shown)) if shown else 0,
        **funnel,
    }
    summary = summary_lines(stats, cfg)

    print()
    print(c("  " + "=" * 74, DIM))
    print(c("  SEARCH SUMMARY", BOLD))
    print(c("  " + "=" * 74, DIM))
    for label, value in summary:
        print("  %-46s %s" % (label, c(value, BOLD) if not label.startswith("  ") else value))
    print()
    print(c("  " + "=" * 74, DIM))
    print(c("  PEOPLE TO CONTACT", BOLD))
    print(c("  ranked by score; a documentation recall outranks a clearance,", DIM))
    print(c("  and old events are decayed automatically", DIM))
    print(c("  " + "=" * 74, DIM))
    print()

    lines = []
    for i, (result, account, comp, match) in enumerate(shown, 1):
        person = comp["contacts"][0] if comp.get("contacts") else None
        tier = result["tier"]
        name = person["name"] if person else "(no named contact)"

        print("  %s %s  %s" % (
            c("%2d." % i, DIM),
            c(name, BOLD),
            c("ICP match %d%%  ·  score %.1f" % (match["pct"], result["composite"]),
              TIER_COLOUR.get(tier, DIM)),
        ))
        print("      %s - %s" % (account["company"], account["hq"]))
        print("      %s" % c(headline_trigger(account), DIM))
        if match["missing"]:
            print("      %s" % c("missing: " + ", ".join(match["missing"]), DIM))
        if person:
            print("      FDA record  %s" % c(person["url"], CYAN))
            print("      LinkedIn    %s" % c(linkedin_search(name, account["company"]), CYAN))
        print("      %s" % c("verify: headcount 30-400, owns its own technical file", YELLOW))
        print()

        lines.append(
            "## %d. %s — %s\n\n"
            "- **Location:** %s\n"
            "- **ICP match:** %d%% (%d of %d differentiating criteria)%s\n"
            "- **Clearances in window:** %d\n"
            "- **Score:** %.1f\n"
            "- **Trigger:** %s\n"
            "- **FDA record:** %s\n"
            "- **LinkedIn search:** %s\n"
            "- **Verify before contacting:** headcount in 30–400 band; is the legal "
            "manufacturer, not a contract manufacturer or a subsidiary\n"
            % (i, name, account["company"], account["hq"],
               match["pct"], match["met"], match["total"],
               (" — missing: " + ", ".join(match["missing"])) if match["missing"] else "",
               comp.get("clearance_count", 0),
               result["composite"], headline_trigger(account),
               person["url"] if person else "n/a",
               linkedin_search(name, account["company"]) if person else "n/a")
        )

    out = cfg.get("out")
    if out:
        path = out if os.path.isabs(out) else os.path.join(HERE, out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("# Buyers to contact\n\n")
            f.write("Generated %s from openFDA 510(k) and enforcement records.\n"
                    % dt.date.today().isoformat())
            f.write("States: %s · clearances last %d months · recalls last %d years\n\n"
                    % ("/".join(states), cfg["clearance_months"], cfg["recall_years"]))
            f.write("## Search summary\n\n| | |\n|---|---|\n")
            for label, value in summary:
                f.write("| %s | %s |\n" % (label.strip(), value))
            f.write("\n" + MATCH_NOTE + "\n\n---\n\n")
            f.write("\n".join(lines))
        print(c("  Written to %s" % out, GREEN))
        print()

    csv_out = cfg.get("csv")
    if csv_out:
        path = csv_out if os.path.isabs(csv_out) else os.path.join(HERE, csv_out)
        n = write_csv(path, rows, load_checks(), cfg)
        print(c("  Spreadsheet of all %d accounts written to %s" % (n, csv_out), GREEN))
        print()

    print(c("  Tune what you are hunting   -> target.yaml", DIM))
    print(c("  Tune what signals are worth -> icp/weights.yaml", DIM))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
