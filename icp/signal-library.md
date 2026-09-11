# Klaris ICP — Signal Library

How to find every signal in `weights.yaml`, and what counts as evidence.

**Evidence bar:** every signal needs a source URL. `score.py` silently drops
unsourced signals unless you pass `--lenient`. This is deliberate — an ICP model
that accepts vibes produces a pipeline built on vibes.

**Data available:** public web + LinkedIn Sales Navigator. No Apollo/Clay/ZoomInfo.

---

## LAYER 0 — Gates

| Gate | Where to check | Passes if |
|---|---|---|
| `legal_manufacturer` | Company site "legal manufacturer" / DoC / EUDAMED actor registration / UDI records | They hold the CE mark or FDA registration in their own name |
| `headcount_in_band` | LinkedIn company page; Sales Nav headcount filter; Companies House (UK) | 30–400 |
| `notified_body_exposure` | Product pages ("CE marked Class IIb"), DoC, FDA 510(k)/PMA database, EUDAMED | Any EU IIa/IIb/III, Class I s/m/r, IVDR B/C/D, FDA Class II/III |
| `technical_file_exists` | Do they market a device, or state a submission timeline? | Past design freeze |

> **Class I nuance:** Class I *sterile*, *measuring*, and *reusable surgical*
> (Is / Im / Ir) require Notified Body involvement for those aspects and
> **pass** the gate. Only plain Class I non-sterile fails.

---

## LAYER 1 — Fit signals

### 1. Regulatory burden (cap 30)
- **Device class** — product pages, IFU PDFs, DoC, FDA 510(k) database
  (`accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm`), EUDAMED.
  Search `site:company.com "Class II" OR "CE" filetype:pdf`.
- **Dual regime** — both a CE mark and an FDA clearance/registration.
- **Software / SaMD / AI** — product described as software, app, algorithm,
  "AI-powered", or embedded firmware. Triggers IEC 62304 + (in the EU) the
  AI Act overlay on top of MDR. Doc stack balloons.
- **Device families** — count distinct product lines on the site or distinct
  Basic UDI-DIs.

### 2. Compliance spend evidence (cap 25) — "already paying"
- **Named eQMS (10)** — the highest-value single signal here. Find it in:
  job ads ("experience with Greenlight Guru required"), vendor case-study
  pages, G2/Capterra reviews naming the company, LinkedIn skills on RA/QA
  staff, conference co-presentations. Vendors to match: Greenlight Guru,
  Qualio, MasterControl, Veeva Vault QMS, Matrix Requirements, Scilife,
  Dot Compliance, Ketryx, Sparta, ETQ.
- **Active NB or certificate (8)** — "CE marked under MDR by TÜV SÜD / BSI /
  DEKRA / DNV / SGS / Intertek / NSAI / Kiwa". NB fees run £30–150k+/yr, so
  this proves real, recurring regulatory spend.
- **Retained RA/QA consultancy (5)** — consultancy case studies naming them;
  "Consultant at X" appearing in their team list.
- **RA/QA FTE ratio ≥5% (7)** — Sales Nav: filter the company's employees by
  function/title for Regulatory / Quality, divide by headcount.

### 3. Company shape (cap 20)
LinkedIn headcount. Sweet spot 80–250: large enough to own a real technical
file, small enough that RA is under-resourced and procurement is not a wall.

### 4. Readiness / AI receptivity (cap 15)
Cloud eQMS rather than paper/SharePoint; AI in the product or public AI-adoption
statements; VC-backed or a recent raise; an RA leader who posts about digital RA
or speaks at RAPS/TOPRA.

### 5. Document surface & drift risk (cap 10)
- **Post-M&A integration (5)** — acquired a portfolio, now holds heterogeneous
  technical files written by different teams to different conventions. This is
  the Consistency Reviewer's ideal case and it is badly under-prospected.
- Many markets / IFU languages; legacy MDD documents being uplifted to MDR.

---

## LAYER 2 — Trigger signals (decay applies)

### 1. Hiring QA/RA (cap 30)
Sources: company careers page, LinkedIn Jobs, Indeed, Otta, Welcome to the
Jungle, RAPS job board, and medtech-specific recruiters (Kirkham Young,
RBW Consulting, Barrington James, Mantell Associates).

- **Head/Director/VP of RA or QA req open (15)** — a new budget owner is
  arriving with a mandate to fix something.
- **Any RA/QA req (8 each, cap 20)**.
- **Req open >90 days (+8)** — the sharpest line in the model. Check the
  original post date, or diff the careers page against the Wayback Machine.
  A company advertising for 90+ days has publicly admitted it needs capacity
  and failed to buy it in people. That is precisely when it buys tools.
- **New RA/QA leader started <90 days (12)** — Sales Nav job-change alerts.
  New leaders buy in their first 100 days.
- **Leader left with no backfill (8)** — capacity crisis.
- **JD language (+7)** — match: "MDR remediation", "technical file",
  "gap assessment", "notified body submission", "documentation backlog",
  "technical documentation", "MDR transition". These job ads describe
  Klaris's job in the company's own words; quote them back in outreach.

### 2. New product to market ≤18 months (cap 30)
- **Funding <12m with regulatory use-of-funds (12)** — press release says the
  round funds "CE marking", "regulatory approval", "FDA clearance". Budget
  explicitly earmarked for the job Klaris does. Sources: Tech.eu, Sifted,
  UKTN, MedTech Dive, Crunchbase free tier, company newsroom.
- **Public launch/approval target next year (12)** — "expects CE mark in 2027".
- **Clinical study completing ≤12m (10)** — clinicaltrials.gov, EU CTIS,
  ISRCTN. Study completion precedes submission by months.
- **New market entry (10)** — US firm entering the EU (or vice versa). High
  pain, low internal capability: an MDR technical file built from scratch
  with no in-house EU RA muscle. Tells: hiring an EU Authorised Representative,
  a first EU office, an "EC REP" appearing on labelling.
- **New UDI-DI or 510(k) filed (8)** — EUDAMED; FDA 510(k) database sorted by
  decision date.

### 3. Prior regulatory pain (cap 25) — *added, not in original brief*
- **Warning letter / Form 483 citing design or document control (15)** —
  FDA Warning Letter database and 483 releases. Grep for 21 CFR 820.30
  (design controls) and 820.40 (document controls). These two citations
  are Klaris's product described in regulatory language.
- **Public regulatory delay or resubmission (12)** — investor updates, press,
  or a CE-mark date that quietly moves on the website. See "timeline-slip
  inference" in `buyer-map.md`.
- **Documentation / labelling recall or FSCA (10)** — FDA recall database,
  MHRA field safety notices, BfArM/Swissmedic FSCA listings. A labelling or
  IFU recall *is* document drift.
- **Notified Body switch (8)** — a different NB number on new certificates
  means a full re-review of the whole technical file.

### 4. Deadline pressure (cap 15) — *added*
- **Legacy MDD certificate, deadline <18m (15)** — under Regulation 2023/607
  the transition ends **2027-12-31** for Class III and IIb implantables, and
  **2028-12-31** for other IIb, IIa, and Class I s/m/r. A company still
  selling on a legacy MDD certificate has a dated countdown and a board
  asking about it. Nobody negotiates with a deadline.
- **IVDR transition approaching (12)**.
- **NB surveillance audit ≤6m (5)** — annual, inferable from certificate dates.

---

## LAYER 3 — Access (cap 40)

| Signal | Pts | How |
|---|---|---|
| Warm path | 15 | Shared investor (Meridian Health Ventures, Antler, co-investors), NHS-trust network, founder alumni, 2nd-degree on Sales Nav |
| Economic buyer named & verified | 10 | See `buyer-map.md` triangulation |
| Champion identified | 8 | Hands-on RA/QA manager |
| Buyer publicly active | 7 | Posts on LinkedIn, speaks at RAPS/TOPRA/MedTech Summit |

---

## Negative signals

| Signal | Pts | Rule |
|---|---|---|
| Large flat in-house RA team | −10 | >10 RA FTEs, not growing — solved it with people |
| Certification just completed | −8 | Closed <3m ago; no trigger for 18–24m |
| Paper/SharePoint-only QMS | −5 | Not a software buyer yet |
| Competitor recently renewed | −12 | Locked for the cycle |
