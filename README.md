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

## Read this before trusting a score

Thresholds are **provisional**, calibrated against one cohort of 13 accounts.
Public-source research captures only part of the model's theoretical signal —
`deadline_pressure` captured 0% and `prior_regulatory_pain` 1%, and together
they carry 40 of the 100 trigger points. The **ordering is trustworthy; the
absolute cut-points are not, yet.** Every result prints a `coverage` figure so a
low score from thin research is distinguishable from a genuinely poor account.

See `docs/2026-09-11-klaris-icp-design.md` for the full calibration analysis.
