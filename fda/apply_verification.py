"""Merge human verification into a machine-built cohort.

The division of labour this module enforces
-------------------------------------------
openFDA finds candidates and proves triggers. It cannot tell you how big a
company is, who owns it, or whether it holds a CE mark. Until a person checks
those, `build_cohort.py` leaves the headcount gate NOT ASSESSED, so every
account scores Tier D by design - not because it is a bad account, but because
nobody has looked yet.

This module applies what the person found. Verification is kept in its own
file, separate from the machine output, so that:

  - re-running the fetchers never overwrites human work;
  - every verified claim carries its own source URL, same evidence bar as
    everything else;
  - a disqualification is recorded WITH ITS REASON rather than by deleting the
    row, so the same company is not re-researched next quarter.

Usage
-----
    python3 fda/apply_verification.py \
        --cohort out/fda_accounts.json \
        --verification out/verification-2026-09-17.json \
        --out out/charlotte-12.json
    python3 icp/score.py out/charlotte-12.json
"""

import argparse
import json
import sys

# Headcount band -> the weights.yaml signal id for company_shape.
BANDS = [
    (30, 39, "headcount_30_39"),
    (40, 79, "headcount_40_79"),
    (80, 250, "headcount_80_250"),
    (251, 400, "headcount_251_400"),
]


def band_signal(headcount):
    for lo, hi, sid in BANDS:
        if lo <= headcount <= hi:
            return sid
    return None


def apply(account, v):
    """Fold one verification record into one account. Returns None if DQ'd."""
    if v.get("disqualified"):
        return None

    hc = v.get("headcount")
    src = v.get("headcount_url")

    if hc is not None:
        account["headcount"] = hc
        in_band = 30 <= hc <= 400
        account["gates"]["headcount_in_band"] = {
            "pass": in_band,
            "evidence": "%s (verified %s)" % (v.get("headcount_evidence", "%d staff" % hc),
                                              v.get("verified_at", "")),
            "url": src,
        }
        sid = band_signal(hc) if in_band else None
        if sid:
            account["signals"].append({
                "id": sid,
                "evidence": v.get("headcount_evidence", "%d staff" % hc),
                "url": src,
            })

    for field in ("domain", "hq"):
        if v.get(field):
            account[field] = v[field]

    # Extra signals the human found (CE mark, funding, hiring, eQMS...).
    # Each must carry a url or score.py will drop it, which is the point.
    for s in v.get("signals", []):
        account["signals"].append(s)

    for p in v.get("penalties", []):
        account.setdefault("penalties", []).append(p)

    if v.get("notes"):
        account["notes"] = v["notes"]
    if v.get("contact_title"):
        account["contact_title"] = v["contact_title"]

    account["verified_at"] = v.get("verified_at")
    account["unverified"] = [u for u in account.get("unverified", [])
                             if u != "headcount_in_band" or hc is None]
    return account


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cohort", required=True, help="Output of build_cohort.py")
    p.add_argument("--verification", required=True, help="Human verification file")
    p.add_argument("--out", required=True)
    p.add_argument("--verified-only", action="store_true",
                   help="Drop accounts nobody has checked yet")
    a = p.parse_args(argv)

    with open(a.cohort) as f:
        cohort = json.load(f)
    with open(a.verification) as f:
        vfile = json.load(f)

    vmap = {k.lower(): v for k, v in vfile.get("companies", {}).items()}

    out, dq = [], []
    for acct in cohort:
        v = vmap.get(acct["company"].lower())
        if v is None:
            if not a.verified_only:
                out.append(acct)
            continue
        merged = apply(acct, v)
        if merged is None:
            dq.append((acct["company"], v.get("disqualified")))
        else:
            out.append(merged)

    with open(a.out, "w") as f:
        json.dump(out, f, indent=2)

    print("%d accounts -> %s" % (len(out), a.out), file=sys.stderr)
    if dq:
        print("disqualified (%d):" % len(dq), file=sys.stderr)
        for name, reason in dq:
            print("   %-34s %s" % (name, reason), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
