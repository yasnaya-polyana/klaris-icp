"""Recalls and enforcement -> the `prior_regulatory_pain` trigger family.

Why this module exists
----------------------
`prior_regulatory_pain` is worth 25 trigger points and the 2026-09-11
calibration measured it capturing **1%** of its theoretical signal. It was the
single worst-served family in the model, and the design doc flagged the fix:
systematic FDA recall / enforcement database mining. This is that fix.

The sharpest sub-signal is a recall whose stated cause is labelling, IFU,
instructions, or documentation. That is not a manufacturing defect - it is a
document that contradicted another document, which is precisely what Klaris's
Consistency Reviewer catches. A company that has recalled product over an IFU
error has already paid for this lesson in revenue.

Every record cites back to the FDA's own enforcement database.

Usage
-----
    python3 fda/fetch_enforcement.py --firm "Restor3D"
    python3 fda/fetch_enforcement.py --states NC SC VA GA TN --years 5
"""

import argparse
import datetime as dt
import json
import re
import sys

try:
    from . import openfda
except ImportError:
    import openfda

CITE = 'https://api.fda.gov/device/enforcement.json?search=recall_number:"%s"'

# Ordered most- to least-specific. First match wins.
CAUSE_PATTERNS = [
    ("documentation_or_labelling_recall_fsca", re.compile(
        r"label|labeling|labelling|ifu|instructions for use|package insert|"
        r"incorrect information|misprint|wrong (?:product|part) (?:number|code)|"
        r"udi|barcode|expiration date|user manual|operator manual|"
        r"translation|incorrect document|documentation error", re.I)),
    ("design_or_software_recall", re.compile(
        r"software|firmware|design (?:flaw|error|defect)|algorithm|"
        r"specification (?:error|not met)", re.I)),
    ("sterility_or_manufacturing_recall", re.compile(
        r"steril|contaminat|particulate|non-conforming material|"
        r"manufacturing (?:error|defect)|process deviation", re.I)),
]

CLASS_WEIGHT = {"Class I": "most serious", "Class II": "serious", "Class III": "least serious"}


def classify(reason):
    for signal_id, pattern in CAUSE_PATTERNS:
        if pattern.search(reason or ""):
            return signal_id
    return "other_recall"


def fetch(firm=None, states=None, years=5, max_records=1000):
    """Enforcement records, newest first, grouped by recalling firm."""
    since = (dt.date.today() - dt.timedelta(days=365 * years)).strftime("%Y%m%d")
    until = dt.date.today().strftime("%Y%m%d")
    clauses = ["report_date:[%s+TO+%s]" % (since, until)]

    if firm:
        clauses.append('recalling_firm:"%s"' % firm)
    if states:
        clauses.append("(%s)" % "+OR+".join('state:"%s"' % s for s in states))

    records = openfda.paginate(
        "enforcement", "+AND+".join(clauses), max_records=max_records
    )

    firms = {}
    for r in records:
        name = (r.get("recalling_firm") or "").strip()
        if not name:
            continue
        key = openfda.normalise(name)
        f = firms.setdefault(key, {"firm": name, "state": r.get("state", ""), "events": []})

        reason = (r.get("reason_for_recall") or "").strip()
        recall_number = r.get("recall_number", "")
        f["events"].append({
            "signal_id": classify(reason),
            "recall_number": recall_number,
            "date": r.get("report_date", ""),
            "classification": r.get("classification", ""),
            "severity": CLASS_WEIGHT.get(r.get("classification", ""), ""),
            "product": (r.get("product_description") or "")[:180],
            "reason": reason[:300],
            "url": CITE % recall_number,
        })

    out = []
    for f in firms.values():
        f["events"].sort(key=lambda e: e["date"], reverse=True)
        f["event_count"] = len(f["events"])
        # The headline is whether any event was a documentation failure.
        f["has_documentation_recall"] = any(
            e["signal_id"] == "documentation_or_labelling_recall_fsca" for e in f["events"]
        )
        f["latest"] = f["events"][0]["date"] if f["events"] else ""
        out.append(f)

    out.sort(key=lambda f: (f["has_documentation_recall"], f["latest"]), reverse=True)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--firm", help="Single recalling firm to look up")
    p.add_argument("--states", nargs="+", help="Filter by US state codes")
    p.add_argument("--years", type=int, default=5, help="Look-back in years (default 5)")
    p.add_argument("--out", help="Write JSON here instead of stdout")
    a = p.parse_args(argv)

    firms = fetch(firm=a.firm, states=a.states, years=a.years)
    payload = {
        "generated_at": dt.date.today().isoformat(),
        "years": a.years,
        "firm_count": len(firms),
        "with_documentation_recall": sum(1 for f in firms if f["has_documentation_recall"]),
        "firms": firms,
    }

    if a.out:
        with open(a.out, "w") as f:
            json.dump(payload, f, indent=2)
        print("%d firms (%d with a documentation/labelling recall) -> %s"
              % (payload["firm_count"], payload["with_documentation_recall"], a.out),
              file=sys.stderr)
    else:
        json.dump(payload, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
