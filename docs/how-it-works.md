# How it works (technical detail)

*For everyday use, see the [README](../README.md). This page is the detail behind it.*

Finds the people at medical device companies who own the technical file, using
the FDA's own public databases. No API key, no licence, no scraping, no paid
enrichment. Every person it returns carries a link to the government record
they were found on.

## Use it

```bash
python3 find_buyers.py
```

That's the whole thing. It prints a ranked list of named regulatory contacts
with the reason each one is worth a call, and writes `out/buyers.md`.

Two files control it:

| File | What it decides |
|---|---|
| **`target.yaml`** | Where and what you're hunting — states, date window, size filters, how many results |
| **`icp/weights.yaml`** | What each signal is worth — every number in the scoring model |

Want Boston instead of Charlotte? Change one line in `target.yaml`:

```yaml
states: [MA, CT, RI, NH]
```

Think prior regulatory pain should outrank a new clearance? Change the points
in `icp/weights.yaml`. Nothing else needs touching — the scorer reads them.

### What it searches

- **openFDA 510(k)** — every clearance is a dated, public record that a
  technical file was assembled, submitted and reviewed, and the submission
  **names the regulatory contact who did it**.
- **openFDA enforcement** — every recall, classified by cause, separating
  documentation failures (a label, an IFU, a stated dimension) from
  manufacturing defects. A documentation recall is one document contradicting
  another, which is the sharpest buying signal available.

### What it deliberately will not guess

openFDA carries no headcount, no EU MDR/IVDR status, no funding and no hiring
data. Those are flagged for verification rather than invented. Every result is
marked *verify: headcount 30–400, owns its own technical file* — because a
model that accepts vibes produces a pipeline built on vibes.

`fda/apply_verification.py` folds your verification back in once you've done
it, from a separate file, so re-running the search never overwrites human work.
See [`out/verification-2026-09-17.json`](../out/verification-2026-09-17.json) for a
worked example: 91 manufacturers screened to 12, with all 13 disqualifications
recorded with their reason.

---

## The model underneath

## Run it


```bash
python3 icp/score.py out/accounts.json            # score + rank (calibrated thresholds)
python3 icp/score.py out/accounts.json --json     # machine-readable
python3 icp/score.py out/accounts.json --full-evidence   # strict thresholds
python3 icp/score.py acct.json --lenient          # count signals lacking a source URL
```

Stdlib only — no `pip install`.

## Structure

- **`icp/weights.yaml`** — every number in the model. Tune here, nowhere else.
- **`icp/score.py`** — deterministic scoring; the agent never does the arithmetic.
- **`icp/signal-library.md`** — where to find each signal, what counts as evidence.
- **`icp/buyer-map.md`** — buyer archetypes and twelve ways to find the economic buyer.
- **`.claude/agents/icp-scorer.md`** — the subagent definition.
- **`out/prospects.md`** — 12 named prospects, with sources and confidence levels.
- **`docs/`** — design rationale and the calibration finding.

## The model in one screen

**Gates** (binary, fail → disqualify): legal manufacturer · 30–400 headcount ·
Notified Body exposure (EU IIa+/Is/Im/Ir, IVDR B+, FDA II+) · technical file exists.

**Fit /100** — regulatory burden 30 · compliance spend evidence 25 ·
company shape 20 · readiness 15 · document surface 10

**Trigger /100** (decays: ×1.0 <90d, ×0.7, ×0.4, ×0.1 >1yr) —
hiring QA/RA 30 · new product to market 30 · prior regulatory pain 25 ·
deadline pressure 15

**Access /40** — warm path 15 · buyer named 10 · champion 8 · buyer active 7

```
Composite = 0.40·Fit + 0.45·Trigger + 0.15·(Access × 2.5)
```

Trigger leads because at pre-seed you cannot manufacture need, only catch it.

## FDA signal layer (added 2026-09-17)

`fda/` mines openFDA for the two trigger families the first calibration found
empty — `prior_regulatory_pain` (was 1% captured) and `new_product_to_market`
(4%) — which carry 40 of the 100 trigger points between them. It also yields
named regulatory contacts from 510(k) submission records.

```bash
python3 fda/build_cohort.py --states NC SC VA GA TN --months 18 \
    --recall-years 6 --named-only --out out/fda_accounts.json
python3 fda/apply_verification.py --cohort out/fda_accounts.json \
    --verification out/verification-2026-09-17.json \
    --out out/charlotte-12.json --verified-only
python3 icp/score.py out/charlotte-12.json
```

The scoring model is unchanged — `icp/weights.yaml` and `icp/score.py` are
exactly as calibrated. Only the evidence feeding them improved. See
[`fda/README.md`](../fda/README.md).

Worked example: [`out/verification-2026-09-17.json`](../out/verification-2026-09-17.json) — 91
manufacturers across NC/SC/VA/GA/TN screened to 12, for RAPS Convergence 2026.

## Read this before trusting a score

Thresholds are **provisional**, calibrated against one cohort of 13 accounts.
Public-source research captures only part of the model's theoretical signal —
`deadline_pressure` captured 0% and `prior_regulatory_pain` 1%, and together
they carry 40 of the 100 trigger points. The **ordering is trustworthy; the
absolute cut-points are not, yet.** Every result prints a `coverage` figure so a
low score from thin research is distinguishable from a genuinely poor account.

See `docs/2026-09-11-klaris-icp-design.md` for the full calibration analysis.
