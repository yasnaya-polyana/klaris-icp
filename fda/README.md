# FDA signal layer

Turns the FDA's public databases into scored accounts for the model in `../icp/`.

## Why

The 2026-09-11 calibration measured how much of each signal family public web
research actually captured. Two families came back close to empty:

| Family | Trigger points | Captured |
|---|---|---|
| `prior_regulatory_pain` | 25 | 1% |
| `new_product_to_market` | 30 | 4% |

Between them they carry **40 of the 100 trigger points** and contributed almost
nothing. The design doc named the fix — systematic FDA recall and clearance
mining — and this is it.

The same research found, by accident, that the 510(k) database was the best
source of *named regulatory individuals* anywhere: the submission record carries
a regulatory contact, on a primary, government-hosted document. Sometimes it
carries their job title too.

Nothing in `../icp/` changed. The gates, the weights and the arithmetic are
exactly as they were. All that changed is how much real evidence reaches them.

## Run it

```bash
# 1. Build a cohort from clearances + recalls
python3 fda/build_cohort.py --states NC SC VA GA TN --months 18 \
    --recall-years 6 --named-only --out out/fda_accounts.json

# 2. Fold in what a human verified (headcount, ownership, CE mark)
python3 fda/apply_verification.py \
    --cohort out/fda_accounts.json \
    --verification out/verification-2026-09-17.json \
    --out out/charlotte-12.json --verified-only

# 3. Score with the existing model, unmodified
python3 icp/score.py out/charlotte-12.json
```

Stdlib only. openFDA needs no API key.

The fetchers run standalone too:

```bash
python3 fda/fetch_510k.py --states NC --months 12 --out out/510k.json
python3 fda/fetch_enforcement.py --firm "Grace Medical" --years 6
```

## The division of labour

openFDA **can** establish, automatically and with a citation: the legal
manufacturer, FDA Class II exposure, that a technical file exists, a dated
new-product trigger, portfolio breadth, prior regulatory pain, and a named
regulatory contact.

It **cannot** establish: headcount, EU MDR/IVDR status, eQMS in use, funding,
or hiring.

So `build_cohort.py` leaves the headcount gate **NOT ASSESSED**, and every
freshly built account scores Tier D until a person checks it. That is
deliberate. An unknown is recorded as an unknown, never as a zero and never as
a guess — a model that accepts vibes produces a pipeline built on vibes.

`apply_verification.py` folds the human's findings back in, from a separate
file, so re-running the fetchers never overwrites that work. Disqualifications
are recorded with their reason rather than deleted, so the same company isn't
re-researched next quarter.

## Files

| Path | What |
|---|---|
| `openfda.py` | API client, pagination, giant-filter, name normalisation |
| `fetch_510k.py` | Clearances → named contacts + `new_product_to_market` |
| `fetch_enforcement.py` | Recalls → `prior_regulatory_pain`, cause-classified |
| `build_cohort.py` | Joins both into `accounts.json` records |
| `apply_verification.py` | Merges human verification; handles disqualification |

## Cause classification

`fetch_enforcement.py` sorts each recall by its stated cause. The sharpest
sub-signal is a recall caused by labelling, IFU or documentation — that is not
a manufacturing defect, it is one document contradicting another, which is
exactly what the Consistency Reviewer catches.

Only `documentation_or_labelling_recall_fsca` exists in `weights.yaml`, so only
that one scores. The other classes (`design_or_software_recall`,
`sterility_or_manufacturing_recall`, `other_recall`) are carried as context for
a human and deliberately never emitted as scoreable signals.

## Known limits

- **Headcount is manual.** The slowest step and the real bottleneck.
- **A 510(k) contact may be an outsourced consultant**, not an employee, and may
  have left. Emitted as `champion_identified`, never as economic buyer, until a
  title is confirmed. Track the "wrong person" reply rate — above ~20% and this
  layer needs a verification step before it needs anything else.
- **US only.** EU MDR/IVDR status has no equivalent public API. EUDAMED is the
  eventual answer for `deadline_pressure`; it is still not the fix today.
- **Giant-filter is a name list.** Conservative by design: borderline names stay
  in and get verified by hand.
