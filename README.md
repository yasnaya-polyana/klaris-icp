# Klaris ICP — scoring model + buyer-discovery agent

Qualifies medical device companies for [Klaris.ai](https://www.klaris.ai/) and
finds the person who can buy. EU MDR/IVDR first, FDA second. 30–400 headcount.

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
[`fda/README.md`](fda/README.md).

Worked example: [`out/verification-2026-09-17.json`](out/verification-2026-09-17.json) — 91
manufacturers across NC/SC/VA/GA/TN screened to 12, for RAPS Convergence 2026.

## Read this before trusting a score

Thresholds are **provisional**, calibrated against one cohort of 13 accounts.
Public-source research captures only part of the model's theoretical signal —
`deadline_pressure` captured 0% and `prior_regulatory_pain` 1%, and together
they carry 40 of the 100 trigger points. The **ordering is trustworthy; the
absolute cut-points are not, yet.** Every result prints a `coverage` figure so a
low score from thin research is distinguishable from a genuinely poor account.

See `docs/2026-09-11-klaris-icp-design.md` for the full calibration analysis.
