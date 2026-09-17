# Klaris Buyer Finder

**Finds medical device companies that need Klaris, and the person at each one to contact.**

Built for Klaris to find accounts you might otherwise miss. It works from the FDA's own public records, so there is no attendee list, data provider or subscription to pay for, and every name comes with a link to the record it was found on.

**See a finished example:** [Google Sheet: 91 companies near Charlotte](https://docs.google.com/spreadsheets/d/1y--q06FYgWcXDkle0b3adF5ku36udTGITgaf9jlYaaI/edit)

---

## What it does

It looks for two things that suggest a company needs Klaris.

**1. They've just been through an FDA submission.**
When the FDA clears a device, the record names the person who handled the submission. A recent clearance means a technical file was just built and reviewed, and that person is usually the one who owns it.

**2. A document has caused them a problem.**
When a device is recalled, the FDA records why. The tool picks out recalls caused by documentation, such as a wrong label, a missing symbol or an incorrect measurement in the instructions. That is one document contradicting another, which is exactly what Klaris catches.

It then ranks every company it finds and gives you a list like this:

| Person to contact | Company | Why | Checked by hand |
|---|---|---|---|
| Thomas Fearnley | Grace Medical, Memphis | Recalled a device in June 2026 over an incorrect length on the labelling | Good fit, ~82 staff |
| Knox Pittman | restor3d, Durham | 7 FDA clearances in 18 months, the most active filer in the region | Good fit, ~264 staff |
| Will Mauldin | Rivanna Medical, Charlottesville | Cleared a new device in July 2026; already CE marked | Good fit, ~55 staff |

Each row also links to the FDA record and to a LinkedIn search for the person.

---

## How to use it

### First time only

1. On this page, click the green **Code** button, then **Download ZIP**. Unzip it.
2. Open **Terminal** (on a Mac, press ⌘ + Space and type "Terminal").
3. Type `cd ` (with a space after it), drag the unzipped folder into the Terminal window, and press Enter.

Python 3 comes with most Macs. If Terminal says it isn't installed, download it from [python.org](https://www.python.org/downloads/).

### Every time

Type this and press Enter:

```
python3 find_buyers.py
```

It takes about a minute and a half. When it's done you'll have:

- **`out/buyers.csv`** — every company it found. Open it in Excel, or in Google Sheets via *File → Import*.
- **`out/buyers.md`** — a readable list of the top 25.

---

## Changing what it looks for

You only ever need to edit two files. Open either one in any text editor, change a value, save it, and run the tool again.

### `target.yaml`: where and when to look

| Setting | What it does | Example |
|---|---|---|
| `states` | Which US states to search | `[MA, CT, RI, NH]` for Boston |
| `clearance_months` | How far back to look for FDA clearances | `12` for only the last year |
| `recall_years` | How far back to look for recalls | `6` |
| `min_clearances` | Only include companies with at least this many clearances | `2` to find regular filers |
| `exclude_also` | Company names to leave out | `["Company You Already Know"]` |
| `top` | How many people to show in the readable list | `25` |

The file includes ready-made state lists for Charlotte, Boston, Minneapolis and the Bay Area.

### `icp/weights.yaml`: what matters most

This file sets how many points each signal is worth. If a documentation recall should count for more than a new clearance, raise its points. Every number in the scoring lives here and nowhere else, and each one has a note explaining what it means.

---

## Reading the results

**ICP match** shows how many of three buying signals a company has:
- **Regular filer**: 2 or more FDA clearances in the time window
- **Recent clearance**: one in the last 6 months
- **Documentation recall**: a recall caused by labelling or paperwork

100% means all three, and 33% means one. The "Signals missing" column tells you which are absent.

**Score** is the overall ranking. It also gives less weight to older events, so a recall from four years ago counts for much less than one from last month.

**Checked by hand** shows whether someone has already looked at the company:
- **Good fit**: checked, and the right size and independently owned
- **Ruled out**: checked and not a fit, with the reason (too big, too small, or owned by a larger group). These sit at the bottom of the sheet.
- **Not checked yet**: have a look before reaching out

---

## What it can't tell you

The FDA doesn't record **company size** or **who owns a company**. So before contacting anyone marked *Not checked yet*, spend two minutes on LinkedIn or their website to confirm that:

- they have roughly 30–400 employees, and
- they aren't a subsidiary of a larger group, whose parent company would own the paperwork.

When you check a company, add it to `out/verification-2026-09-17.json` and it will show as checked (or ruled out) on the next run.

The person named on an FDA submission is occasionally an outside consultant rather than an employee. The LinkedIn search will usually make that obvious.

---

## Good to know

- **Free and needs no login.** It uses the FDA's public data service (openFDA). There's no API key or account.
- **US only for now.** The EU has no equivalent public database of named regulatory contacts yet.
- **Every name is checkable.** Each row links to the government record it came from.

Technical detail, including how the scoring model was built and calibrated, is in [docs/how-it-works.md](docs/how-it-works.md).
