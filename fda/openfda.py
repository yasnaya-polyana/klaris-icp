"""Thin openFDA client. Stdlib only, no API key required.

openFDA is a public, government-hosted API over the FDA's own device
databases. Every record this module returns is citable back to a primary
regulatory source, which is the whole point: an ICP model that accepts
vibes produces a pipeline built on vibes.

Rate limit without a key is 240 requests/min, 1000/day. We stay well under.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.fda.gov/device"

# openFDA returns HTTP 404 for "your search matched nothing". That is not an
# error condition for us - it is an empty result set.
NO_MATCH = 404

USER_AGENT = "klaris-icp/1.0 (ICP research; contact via github)"


def query(endpoint, search, limit=100, skip=0, retries=3):
    """One page of results. Returns [] when the search matches nothing."""
    params = urllib.parse.urlencode(
        {"search": search, "limit": limit, "skip": skip}, safe=":[]+\"*"
    )
    url = "%s/%s.json?%s" % (BASE, endpoint, params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("results", [])
        except urllib.error.HTTPError as e:
            if e.code == NO_MATCH:
                return []
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return []


def paginate(endpoint, search, page=100, max_records=1000):
    """Walk a result set. openFDA caps skip at 25000; we cap far lower."""
    out = []
    skip = 0
    while skip < max_records:
        batch = query(endpoint, search, limit=page, skip=skip)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page:
            break
        skip += page
    return out


def total(endpoint, search):
    """Result count without pulling the records."""
    params = urllib.parse.urlencode({"search": search, "limit": 1}, safe=":[]+\"*")
    url = "%s/%s.json?%s" % (BASE, endpoint, params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("meta", {}).get("results", {}).get("total", 0)
    except urllib.error.HTTPError as e:
        if e.code == NO_MATCH:
            return 0
        raise


# ---------------------------------------------------------------------------
# Name handling
# ---------------------------------------------------------------------------

# Applicants large enough to fail the 30-400 headcount gate on sight. Filtering
# here saves a manual verification pass on names that can never qualify. This
# list is deliberately conservative - anything borderline is left in and
# verified by hand.
GIANTS = [
    "teleflex", "medtronic", "becton", "baxter", "abbott", "boston scientific",
    "johnson", "siemens", "ge health", "ge medical", "philips", "stryker",
    "zimmer", "danaher", "thermo fisher", "3m ", "smith & nephew", "olympus",
    "canon", "fujifilm", "hologic", "bausch", "edwards lifesciences", "roche",
    "astrazeneca", "pfizer", "novartis", "merck", "sanofi", "cardinal health",
    "dentsply", "align technology", "intuitive surgical", "agilent", "bio-rad",
    "c.r. bard", "cr bard", "integra lifesciences", "conmed", "coloplast",
    "terumo", "nipro", "b. braun", "fresenius", "getinge", "draeger",
    "masimo", "resmed", "insulet", "dexcom", "hillrom", "steris", "icu medical",
    "west pharmaceutical", "avanos", "o&m halyard", "owens & minor",
    "centers for disease control", "u.s. department", "food and drug",
    "veterans affairs", "national institutes",
]

LEGAL_SUFFIX = (
    ", inc.", ", inc", " inc.", " inc", ", llc", " llc", ", corp.", " corp.",
    " corp", ", ltd.", " ltd.", " ltd", ", co.", " co.", " company",
    ", l.l.c.", " l.l.c.", ", lp", " lp", " plc", " gmbh", " ag", " s.a.",
    " b.v.", " a/s", " ab", " oy", " s.r.l.", " pty", " limited",
)


def is_giant(applicant):
    a = (applicant or "").lower()
    return any(g in a for g in GIANTS)


def normalise(applicant):
    """Collapse 'Restor3D, Inc.' and 'restor3d' onto one key."""
    a = (applicant or "").strip().lower()
    changed = True
    while changed:
        changed = False
        for suf in LEGAL_SUFFIX:
            if a.endswith(suf):
                a = a[: -len(suf)].strip().rstrip(",").strip()
                changed = True
    return " ".join(a.split())


def clean_person(name):
    """openFDA pads contact names with double spaces and inconsistent case."""
    n = " ".join((name or "").split())
    if not n:
        return ""
    # "NEWTON,  R.N." -> "Newton, R.N."  |  "Laura  Medlin" -> "Laura Medlin"
    if n.isupper():
        n = n.title()
    return n
