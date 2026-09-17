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

import datetime as dt
import os
import sys

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
    return cfg


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
    companies = fetch_510k.fetch(states, cfg["clearance_months"])

    print("  [2/3] recalls, classified by cause...", flush=True)
    recalls = fetch_enforcement.fetch(states=states, years=cfg["recall_years"],
                                      max_records=2000)
    by_key = {openfda.normalise(r["firm"]): r for r in recalls}
    doc_recalls = sum(1 for r in recalls if r["has_documentation_recall"])

    print("  [3/3] scoring against icp/weights.yaml...", flush=True)
    rows = []
    for comp in companies:
        if comp["clearance_count"] < cfg["min_clearances"]:
            continue
        if cfg["require_named_contact"] and not comp.get("contacts"):
            continue
        account = build_cohort.build(comp, by_key)
        # Headcount is unknown from openFDA, so the gate cannot pass yet.
        # Score the evidence we do have rather than reporting a gate failure.
        account["gates"].pop("headcount_in_band", None)
        result = scorer.evaluate(account, weights)
        rows.append((result, account, comp))

    rows.sort(key=lambda r: r[0]["composite"], reverse=True)

    print()
    print(c("  %d manufacturers with a named regulatory contact" % len(rows), BOLD))
    print(c("  %d firms in region carry a recall; %d were caused by a document"
            % (len(recalls), doc_recalls), DIM))
    print()
    print(c("  " + "=" * 74, DIM))
    print(c("  PEOPLE TO CONTACT", BOLD))
    print(c("  ranked by score; a documentation recall outranks a clearance,", DIM))
    print(c("  and old events are decayed automatically", DIM))
    print(c("  " + "=" * 74, DIM))
    print()

    lines = []
    for i, (result, account, comp) in enumerate(rows[:cfg["top"]], 1):
        person = comp["contacts"][0] if comp.get("contacts") else None
        tier = result["tier"]
        name = person["name"] if person else "(no named contact)"

        print("  %s %s  %s" % (
            c("%2d." % i, DIM),
            c(name, BOLD),
            c("%.1f" % result["composite"], TIER_COLOUR.get(tier, DIM)),
        ))
        print("      %s - %s" % (account["company"], account["hq"]))
        print("      %s" % c(headline_trigger(account), DIM))
        if person:
            print("      %s" % c(person["url"], CYAN))
        print("      %s" % c("verify: headcount 30-400, owns its own technical file", YELLOW))
        print()

        lines.append(
            "## %d. %s — %s\n\n"
            "- **Location:** %s\n"
            "- **Clearances in window:** %d\n"
            "- **Score:** %.1f\n"
            "- **Trigger:** %s\n"
            "- **Source:** %s\n"
            "- **Verify before contacting:** headcount in 30–400 band; is the legal "
            "manufacturer, not a contract manufacturer or a subsidiary\n"
            % (i, name, account["company"], account["hq"],
               comp.get("clearance_count", 0),
               result["composite"], headline_trigger(account),
               person["url"] if person else "n/a")
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
            f.write("%d manufacturers with a named regulatory contact. "
                    "%d firms carry a recall; %d were caused by a document.\n\n---\n\n"
                    % (len(rows), len(recalls), doc_recalls))
            f.write("\n".join(lines))
        print(c("  Written to %s" % out, GREEN))
        print()

    print(c("  Tune what you are hunting   -> target.yaml", DIM))
    print(c("  Tune what signals are worth -> icp/weights.yaml", DIM))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
