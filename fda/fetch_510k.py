"""510(k) clearances -> named regulatory contacts + the 'new product' trigger.

Why this module exists
----------------------
The 2026-09-11 calibration found `new_product_to_market` capturing 4% of its
theoretical signal from public web research, and it carries 30 of the 100
trigger points. It also found, by accident, that the FDA 510(k) database was
the single best source of NAMED regulatory individuals - the submission record
carries a regulatory contact and title on a primary, government-hosted record.

This module turns that accident into infrastructure.

A clearance in the last 12 months is the cleanest 'new product to market'
signal available anywhere: it is dated, public, and it means a technical file
was assembled, submitted and reviewed - recently, by people still in post.

Usage
-----
    python3 fda/fetch_510k.py --states NC SC VA GA TN --months 18
    python3 fda/fetch_510k.py --states NC --months 12 --out out/fda_510k.json
"""

import argparse
import datetime as dt
import json
import sys

try:
    from . import openfda
except ImportError:  # run as a script, not a package
    import openfda

# Primary, citable record for any cleared submission.
PMN_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID=%s"


def window(months):
    today = dt.date.today()
    start = today - dt.timedelta(days=int(months * 30.44))
    return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def fetch(states, months, include_giants=False):
    """Group clearances by applicant. One dict per company."""
    since, until = window(months)
    companies = {}

    for state in states:
        search = 'state:"%s" AND decision_date:[%s+TO+%s]' % (state, since, until)
        records = openfda.paginate("510k", search, max_records=1000)

        for r in records:
            applicant = (r.get("applicant") or "").strip()
            if not applicant:
                continue
            if not include_giants and openfda.is_giant(applicant):
                continue

            key = openfda.normalise(applicant)
            c = companies.setdefault(key, {
                "company": applicant,
                "state": state,
                "city": (r.get("city") or "").title(),
                "clearances": [],
                "contacts": {},
            })

            k_number = r.get("k_number", "")
            c["clearances"].append({
                "k_number": k_number,
                "device": r.get("device_name", ""),
                "decision_date": r.get("decision_date", ""),
                "advisory_committee": r.get("advisory_committee_description", ""),
                "url": PMN_URL % k_number,
            })

            person = openfda.clean_person(r.get("contact"))
            if person:
                # Keep the most recent submission as that person's citation:
                # a name attached to a 2026 filing is likelier still in post.
                prev = c["contacts"].get(person)
                date = r.get("decision_date", "")
                if not prev or date > prev["decision_date"]:
                    c["contacts"][person] = {
                        "name": person,
                        "decision_date": date,
                        "k_number": k_number,
                        "url": PMN_URL % k_number,
                    }

    out = []
    for c in companies.values():
        c["clearances"].sort(key=lambda x: x["decision_date"], reverse=True)
        c["contacts"] = sorted(
            c["contacts"].values(), key=lambda x: x["decision_date"], reverse=True
        )
        c["clearance_count"] = len(c["clearances"])
        c["latest_clearance"] = c["clearances"][0]["decision_date"] if c["clearances"] else ""
        out.append(c)

    # Cadence first: repeat filers have a continuous documentation load, which
    # is a better Klaris fit than a single-submission company.
    out.sort(key=lambda c: (c["clearance_count"], c["latest_clearance"]), reverse=True)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--states", nargs="+", default=["NC", "SC", "VA", "GA", "TN"],
                   help="Two-letter US state codes (default: Charlotte drive radius)")
    p.add_argument("--months", type=int, default=18,
                   help="Look-back window in months (default 18)")
    p.add_argument("--include-giants", action="store_true",
                   help="Do not filter out applicants that fail the headcount gate on sight")
    p.add_argument("--out", help="Write JSON here instead of stdout")
    a = p.parse_args(argv)

    companies = fetch(a.states, a.months, a.include_giants)
    payload = {
        "generated_at": dt.date.today().isoformat(),
        "states": a.states,
        "months": a.months,
        "company_count": len(companies),
        "companies": companies,
    }

    if a.out:
        with open(a.out, "w") as f:
            json.dump(payload, f, indent=2)
        named = sum(1 for c in companies if c["contacts"])
        print("%d companies (%d with a named contact) -> %s"
              % (len(companies), named, a.out), file=sys.stderr)
    else:
        json.dump(payload, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
