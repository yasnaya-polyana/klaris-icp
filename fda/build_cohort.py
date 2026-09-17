"""Join 510(k) + enforcement into accounts.json records that score.py eats.

Design rule: **this module does not change the scorer.** `icp/score.py` and
`icp/weights.yaml` are untouched. All that changes is how much real evidence
reaches them. That is the point - the model was never wrong, it was starved.

What openFDA can and cannot tell us
-----------------------------------
CAN (primary source, citable, automatic):
  - legal manufacturer            <- the 510(k) applicant of record
  - FDA Class II exposure         <- a cleared 510(k) is by definition Class II
  - technical file exists         <- a submission was assembled and reviewed
  - new product to market         <- clearance date
  - portfolio breadth             <- distinct clearances / advisory committees
  - prior regulatory pain         <- recall record, cause-classified
  - a named regulatory person     <- the submission contact

CANNOT (and this module refuses to guess):
  - headcount               -> the 30-400 gate is left NOT ASSESSED
  - EU MDR / CE mark status -> dual-regime must be confirmed on the company site
  - eQMS in use, funding, hiring

Anything in the second list is emitted as null and must be verified by hand
before the account is worked. A model that accepts vibes produces a pipeline
built on vibes - so an unknown is recorded as an unknown, not as a zero and
not as a guess.

Usage
-----
    python3 fda/build_cohort.py --states NC SC VA GA TN --months 18 \
        --out out/fda_accounts.json
    python3 icp/score.py out/fda_accounts.json
"""

import argparse
import datetime as dt
import json
import sys

try:
    from . import openfda, fetch_510k, fetch_enforcement
except ImportError:
    import openfda
    import fetch_510k
    import fetch_enforcement

# Signal ids that exist in icp/weights.yaml. Anything else is carried as
# context for a human but never emitted as a scoreable signal.
SCOREABLE_RECALL = {"documentation_or_labelling_recall_fsca"}


def age_days(yyyymmdd):
    """openFDA dates arrive as 2026-07-01 (510k) or 20260701 (enforcement)."""
    if not yyyymmdd:
        return None
    s = yyyymmdd.replace("-", "")
    try:
        d = dt.datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None
    return (dt.date.today() - d).days


def build(company, recalls_by_key):
    """One 510(k)-grouped company -> one account record in the repo schema."""
    latest = company.get("latest_clearance", "")
    n = company.get("clearance_count", 0)
    top = company["clearances"][0] if company["clearances"] else {}
    cite = top.get("url", "")

    account = {
        "company": company["company"],
        "domain": None,
        "hq": "%s, %s" % (company.get("city") or "?", company.get("state") or "?"),
        "headcount": None,
        "researched_at": dt.date.today().isoformat(),
        "source": "openFDA 510(k) + enforcement",
        "gates": {
            "legal_manufacturer": {
                "pass": True,
                "evidence": "Applicant of record on FDA 510(k) %s. Verify the "
                            "applicant is the legal manufacturer and not a "
                            "contract manufacturer filing on a client's behalf."
                            % top.get("k_number", ""),
                "url": cite,
            },
            "notified_body_exposure": {
                "pass": True,
                "evidence": "Holds FDA Class II clearance (510(k) %s, %s). "
                            "EU class not established from this source."
                            % (top.get("k_number", ""), latest),
                "url": cite,
            },
            "technical_file_exists": {
                "pass": True,
                "evidence": "%d clearance(s) since window start - a submission "
                            "dossier demonstrably exists." % n,
                "url": cite,
            },
            # Deliberately unassessed. score.py reports this as NOT ASSESSED,
            # which is the correct and honest state before a manual check.
            "headcount_in_band": {
                "pass": None,
                "evidence": "openFDA carries no headcount. Verify manually "
                            "against the 30-400 band before working this account.",
                "url": None,
            },
        },
        "signals": [],
        "unverified": ["headcount_in_band", "dual_regime_eu_and_us", "named_eqms_in_use"],
        "contacts": company.get("contacts", []),
        "clearances": company["clearances"][:8],
    }

    s = account["signals"]

    # --- trigger: new product to market ------------------------------------
    if latest:
        s.append({
            "id": "new_udi_di_or_510k_filed",
            "evidence": "510(k) %s cleared %s: %s"
                        % (top.get("k_number", ""), latest, top.get("device", "")[:70]),
            "url": cite,
            "age_days": age_days(latest),
        })

    # --- fit: portfolio breadth --------------------------------------------
    if n >= 5:
        s.append({
            "id": "device_families_5_plus",
            "evidence": "%d FDA clearances in window - continuous submission "
                        "cadence and a wide document surface." % n,
            "url": cite,
        })
    elif n >= 2:
        s.append({
            "id": "device_families_2_to_4",
            "evidence": "%d FDA clearances in window." % n,
            "url": cite,
        })

    # --- access: a named regulatory person ---------------------------------
    # A submission contact is the RA function by definition. Whether they are
    # the ECONOMIC BUYER depends on company shape and needs a manual check, so
    # this is emitted as champion, never as buyer.
    if account["contacts"]:
        c = account["contacts"][0]
        s.append({
            "id": "champion_identified",
            "evidence": "%s named as regulatory contact on 510(k) %s (%s). "
                        "Upgrade to economic_buyer once title is confirmed."
                        % (c["name"], c["k_number"], c["decision_date"]),
            "url": c["url"],
        })

    # --- trigger: prior regulatory pain ------------------------------------
    rec = recalls_by_key.get(openfda.normalise(company["company"]))
    if rec:
        account["recalls"] = rec["events"][:5]
        doc_events = [e for e in rec["events"]
                      if e["signal_id"] in SCOREABLE_RECALL]
        if doc_events:
            e = doc_events[0]
            s.append({
                "id": "documentation_or_labelling_recall_fsca",
                "evidence": "Recall %s (%s, %s): %s"
                            % (e["recall_number"], e["classification"],
                               e["date"], e["reason"][:150]),
                "url": e["url"],
                "age_days": age_days(e["date"]),
            })

    return account


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--states", nargs="+", default=["NC", "SC", "VA", "GA", "TN"])
    p.add_argument("--months", type=int, default=18)
    p.add_argument("--recall-years", type=int, default=6)
    p.add_argument("--min-clearances", type=int, default=1,
                   help="Drop companies below this clearance count")
    p.add_argument("--named-only", action="store_true",
                   help="Keep only companies with a named regulatory contact")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    print("510(k): %s, last %d months..." % ("/".join(a.states), a.months),
          file=sys.stderr)
    companies = fetch_510k.fetch(a.states, a.months)

    print("enforcement: last %d years..." % a.recall_years, file=sys.stderr)
    recalls = fetch_enforcement.fetch(states=a.states, years=a.recall_years,
                                      max_records=2000)
    by_key = {openfda.normalise(r["firm"]): r for r in recalls}

    accounts = []
    for c in companies:
        if c["clearance_count"] < a.min_clearances:
            continue
        if a.named_only and not c.get("contacts"):
            continue
        accounts.append(build(c, by_key))

    with open(a.out, "w") as f:
        json.dump(accounts, f, indent=2)

    with_pain = sum(1 for x in accounts
                    if any(s["id"] == "documentation_or_labelling_recall_fsca"
                           for s in x["signals"]))
    print("%d accounts -> %s  (%d carry a documentation/labelling recall)"
          % (len(accounts), a.out, with_pain), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
