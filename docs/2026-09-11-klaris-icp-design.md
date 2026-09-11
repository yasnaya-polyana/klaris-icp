# Klaris.ai — ICP definition, scoring model, and buyer-discovery agent
**Date:** 2026-09-11 · **Status:** v1.0, calibrated against a first cohort of 13 real accounts

## Context

Klaris reviews medical device technical documentation against regulatory
requirement libraries and flags gaps anchored to clauses, plus cross-document
consistency drift. It reviews; it does not draft. EU MDR/IVDR first, FDA second.
Founder-led sales, £15–60k ACV. Data available: public web + LinkedIn Sales
Navigator only.

## Decisions and their reasons

**Gate + weighted score + separate access score**, not a flat 100-point sum.
Fit is slow-moving and additive; triggers are time-sensitive and decay; access
is about us, not the account. A flat sum blurs all three — a perfect-fit account
with no trigger is a nurture, a mediocre-fit account with a screaming trigger is
a call this week, and a hot account you cannot reach is a different problem
again.

**Trigger weighted above fit (0.45 vs 0.40).** At pre-seed with founder-led
sales you cannot manufacture need, only catch it in flight. Fit stays close
behind because a bad-fit early logo becomes a bad reference customer.

**Class IIa+ is a hard gate, not a scoring line.** Class I non-sterile
self-certifies with no Notified Body review, so there is no deficiency letter
and no pain. *Assumption made without user input:* Class I sterile, measuring
and reusable-surgical (Is/Im/Ir) require NB involvement and therefore **pass**
the gate. This was the tension in the original design and the classification
nuance resolves it without loosening the gate.

**Two trigger families were added beyond the brief.** *Prior regulatory pain* —
a company that has eaten a deficiency letter or a 21 CFR 820.30/820.40 citation
has already paid for the lesson in delayed revenue, which is the highest
willingness-to-pay signal available. *Deadline pressure* — MDR legacy transition
deadlines (2027-12-31 Class III/IIb implantable, 2028-12-31 for IIa/Is/Im) are
dated and non-negotiable.

**Weights live in one YAML file; a script does the arithmetic.** Tuning is a
one-file edit and every saved account re-scores reproducibly. The agent gathers
evidence and never computes the score itself.

**Every signal requires a source URL.** `score.py` drops unsourced signals. An
ICP model that accepts vibes produces a pipeline built on vibes.

## Calibration finding (the important one)

The first real cohort put **all 13 accounts in Tier D**. Diagnosis by measured
capture rate per signal family:

| Family | Avg. capture from public sources |
|---|---|
| company_shape | 95% |
| regulatory_burden | 63% |
| readiness_ai_receptivity | 29% |
| compliance_spend_evidence | 28% |
| hiring_qa_ra | 14% |
| new_product_to_market | 4% |
| document_surface_drift_risk | 2% |
| prior_regulatory_pain | 1% |
| deadline_pressure | **0%** |

The thresholds had been set as if evidence were complete. It never is. Two fixes
were applied:

1. **Dual threshold sets.** `tiers` is calibrated to the observed distribution
   (composite min 19.4 / median 25.7 / max 36.1); `tiers_full_evidence` keeps
   the strict cut-points for when CRM history or paid enrichment is present
   (`--full-evidence`).
2. **A coverage metric.** The scorer now reports what percentage of signal
   families were actually evidenced, so a low score caused by thin research is
   visibly distinct from a low score caused by a genuinely poor account.

**The ordering the model produces is trustworthy. The absolute cut-points are
not, yet.** Recalibrate after ~50 accounts and again once closed-won/lost data
exists to fit against.

Two families are effectively unreachable without new data sources:
`deadline_pressure` needs Notified Body certificate data (EUDAMED, or scraping
certificate registers) and `prior_regulatory_pain` needs systematic FDA warning
letter / 483 / recall database mining. Both are automatable and both are worth
building — they carry 40 of the 100 trigger points between them and currently
contribute ~1%.

## Economic buyer

Buyer moves with company shape: 30–80 people → CEO/COO (the CE mark is the next
fundraise milestone; sell time-to-revenue, never compliance); 80–250 → VP/Head
of RA with real budget, champion is the RA Manager, likely blocker is Head of
Quality; 250–400 → COO/CTO/CMO with procurement.

Twelve discovery tactics are specified in `icp/buyer-map.md`. The two highest-
leverage are novel: **find the PRRC** (EU MDR Article 15 requires every
manufacturer to name a Person Responsible for Regulatory Compliance who carries
*personal legal accountability* for technical documentation conformity — exactly
what Klaris checks), and **watch for PRRC turnover** (a new PRRC inherits
personal liability for documents they did not write).

**Validated in practice:** the FDA 510(k) database proved to be the single best
source of named individuals — submission documents name the regulatory contact
and title on a primary, government-hosted record. That is tactic 3/5 validating
itself, and it was how Veronica Padharia (NICO.LAB) was found.

**Invalidated in practice:** conference speaker lists (tactic 11) skew heavily
enterprise — the MedTech Summit roster returned Edwards, J&J, Medtronic, Roche
and AstraZeneca, all of which fail the headcount gate. Useful for market
intelligence and credibility, low yield for a 30–400 ICP. Downgrade it.

## Deliverables

| Path | What |
|---|---|
| `icp/weights.yaml` | Every number in the model; the only place to tune |
| `icp/score.py` | Deterministic scorer, stdlib only, bundles its own YAML reader |
| `icp/signal-library.md` | Where to find each signal and what counts as evidence |
| `icp/buyer-map.md` | Buyer archetypes + twelve discovery tactics |
| `.claude/agents/icp-scorer.md` | The subagent: research → evidence JSON → score |
| `out/accounts.json` | 13 real scored accounts with cited evidence |
| `out/prospects.md` | 12 named prospects with confidence levels |

## Known limitations

- Headcount is an **estimate** for Quantum Surgical, Quibim, Salvia, NICO.LAB,
  Vitestro, icometrix, Perspectum, Owlstone and Xeltis. Headcount is a hard
  gate, so these must be confirmed before outreach.
- Device class is **unconfirmed** for Owlstone (IVDR class drives its gate) and
  Perspectum.
- Several trigger dates are conservative estimates where the source was undated;
  the scorer decays them accordingly, which under-scores rather than over-scores.
- The **consultancy channel** (RA consultancies who prepare technical files for
  many manufacturers — one adopter brings ten accounts) is deliberately excluded.
  Different economics, buyer and pricing; it needs its own segment model. ICP v2.
