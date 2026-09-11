#!/usr/bin/env python3
"""
Klaris ICP scorer — deterministic scoring of an account evidence file.

The agent gathers evidence; this script does the arithmetic. Weights live in
weights.yaml and nowhere else, so retuning is a one-file edit and every saved
account re-scores reproducibly.

Usage:
    python3 score.py account.json
    python3 score.py out/*.json --json
    python3 score.py account.json --lenient     # keep signals with no source URL

Stdlib only — bundles a minimal YAML reader for the subset weights.yaml uses.
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WEIGHTS = os.path.join(HERE, "weights.yaml")


# --------------------------------------------------------------------------
# Minimal YAML reader (maps, inline flow maps/lists, block scalars, scalars)
# --------------------------------------------------------------------------
def _strip_comment(line):
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _split_top(s, sep=","):
    parts, depth, quote, buf = [], 0, None, []
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _scalar(s):
    s = s.strip()
    if not s:
        return None
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for part in _split_top(s[1:-1]):
            k, _, v = part.partition(":")
            out[k.strip().strip("\"'")] = _scalar(v)
        return out
    if s.startswith("[") and s.endswith("]"):
        return [_scalar(p) for p in _split_top(s[1:-1])]
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d*\.\d+", s):
        return float(s)
    return s


def _tokenize(text):
    """-> list of (indent, content, block_value_or_None)"""
    toks, raw = [], text.split("\n")
    i = 0
    while i < len(raw):
        line = _strip_comment(raw[i])
        if not line.strip():
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        content = line.strip()
        m = re.match(r"^(.*?):\s*[>|][-+]?\s*$", content)
        if m:
            buf, j = [], i + 1
            while j < len(raw):
                if not raw[j].strip():
                    j += 1
                    continue
                nind = len(raw[j]) - len(raw[j].lstrip())
                if nind <= indent:
                    break
                buf.append(raw[j].strip())
                j += 1
            toks.append((indent, m.group(1).strip(), " ".join(buf)))
            i = j
            continue
        toks.append((indent, content, None))
        i += 1
    return toks


def _parse(toks, pos, level):
    if pos >= len(toks):
        return None, pos
    if toks[pos][1].startswith("- "):
        result = []
        while pos < len(toks):
            indent, content, _ = toks[pos]
            if indent != level or not content.startswith("- "):
                break
            result.append(_scalar(content[2:]))
            pos += 1
        return result, pos

    result = {}
    while pos < len(toks):
        indent, content, block = toks[pos]
        if indent != level or content.startswith("- "):
            break
        if block is not None:
            result[content] = block
            pos += 1
            continue
        if ":" not in content:
            pos += 1
            continue
        key, _, val = content.partition(":")
        key = key.strip().strip("\"'")
        val = val.strip()
        pos += 1
        if val:
            result[key] = _scalar(val)
        elif pos < len(toks) and toks[pos][0] > indent:
            result[key], pos = _parse(toks, pos, toks[pos][0])
        else:
            result[key] = None
    return result, pos


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as fh:
        toks = _tokenize(fh.read())
    if not toks:
        return {}
    val, _ = _parse(toks, 0, toks[0][0])
    return val


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def decay_factor(weights, age_days):
    d = weights.get("recency_decay", {})
    if age_days is None:
        return 1.0
    if age_days < 90:
        return float(d.get("under_90_days", 1.0))
    if age_days < 180:
        return float(d.get("d90_to_180", 0.7))
    if age_days < 365:
        return float(d.get("d180_to_365", 0.4))
    return float(d.get("over_365_days", 0.1))


def _families(block):
    """Yield (family_name, family_dict) for families that carry signals."""
    for name, body in (block or {}).items():
        if isinstance(body, dict) and isinstance(body.get("signals"), dict):
            yield name, body


def score_layer(block, hits, weights, apply_decay):
    """Score one layer. Returns (total, per_family, detail_rows)."""
    per_family, rows, total = {}, [], 0.0

    for fam_name, fam in _families(block):
        defs = fam["signals"]
        cap = float(fam.get("cap", 100))
        groups, repeats, fam_total = {}, {}, 0.0

        for hit in hits:
            sid = hit["id"]
            if sid not in defs:
                continue
            spec = defs[sid]
            pts = float(spec.get("points", 0))
            factor = decay_factor(weights, hit.get("age_days")) if apply_decay else 1.0
            earned = pts * factor

            group = spec.get("exclusive_group")
            if group:
                # Only the single highest-scoring member of a group counts.
                prev = groups.get(group)
                if prev is None or earned > prev[0]:
                    groups[group] = (earned, sid, hit, factor, pts)
                continue

            if spec.get("repeatable"):
                rc = float(spec.get("repeat_cap", cap))
                used = repeats.get(sid, 0.0)
                earned = min(earned, max(0.0, rc - used))
                repeats[sid] = used + earned

            fam_total += earned
            rows.append((fam_name, sid, pts, factor, earned, hit))

        for _, (earned, sid, hit, factor, pts) in groups.items():
            fam_total += earned
            rows.append((fam_name, sid, pts, factor, earned, hit))

        fam_score = min(fam_total, cap)
        per_family[fam_name] = {"raw": round(fam_total, 2), "cap": cap,
                                "score": round(fam_score, 2)}
        total += fam_score

    return round(total, 2), per_family, rows


def score_access(block, hits, weights):
    defs = (block or {}).get("signals", {}) or {}
    cap = float((block or {}).get("cap", 40))
    total, rows = 0.0, []
    for hit in hits:
        sid = hit["id"]
        if sid in defs:
            pts = float(defs[sid].get("points", 0))
            total += pts
            rows.append(("access", sid, pts, 1.0, pts, hit))
    return round(min(total, cap), 2), rows


def evaluate(account, weights, lenient=False, full_evidence=False):
    result = {
        "company": account.get("company", "?"),
        "domain": account.get("domain"),
        "gate_failures": [],
        "dropped_unsourced": [],
    }

    # --- Layer 0: gates -----------------------------------------------------
    gate_defs = weights.get("gates", {}) or {}
    for gname in gate_defs:
        g = (account.get("gates") or {}).get(gname)
        passed = g.get("pass") if isinstance(g, dict) else g
        if passed is False:
            note = g.get("evidence", "") if isinstance(g, dict) else ""
            result["gate_failures"].append({"gate": gname, "evidence": note})
        elif passed is None:
            result["gate_failures"].append({"gate": gname,
                                            "evidence": "NOT ASSESSED"})

    # --- Evidence bar: a signal without a source URL does not count ---------
    raw_signals = account.get("signals", []) or []
    signals = []
    for s in raw_signals:
        if not s.get("url") and not lenient:
            result["dropped_unsourced"].append(s.get("id"))
        else:
            signals.append(s)

    fit, fit_fams, fit_rows = score_layer(weights.get("fit"), signals, weights, False)
    trg, trg_fams, trg_rows = score_layer(weights.get("trigger"), signals, weights, True)
    acc, acc_rows = score_access(weights.get("access"), signals, weights)

    comp_w = (weights.get("composite") or {}).get("weights", {}) or {}
    norm = float((weights.get("composite") or {}).get("access_normaliser", 2.5))
    w_fit = float(comp_w.get("fit", 0.40))
    w_trg = float(comp_w.get("trigger", 0.45))
    w_acc = float(comp_w.get("access", 0.15))

    composite = w_fit * fit + w_trg * trg + w_acc * (acc * norm)

    # --- Penalties ----------------------------------------------------------
    pen_defs = weights.get("penalties", {}) or {}
    penalties, pen_total = [], 0.0
    for p in account.get("penalties", []) or []:
        pid = p.get("id") if isinstance(p, dict) else p
        if pid in pen_defs:
            pts = float(pen_defs[pid].get("points", 0))
            pen_total += pts
            penalties.append({"id": pid, "points": pts})
    composite = max(0.0, min(100.0, composite + pen_total))

    # --- Tier ---------------------------------------------------------------
    # Coverage: how much of the model this account was actually assessed against.
    # A low score from thin research must be visibly distinct from a low score
    # from a genuinely poor account.
    fam_scored = sum(1 for v in fit_fams.values() if v["score"] > 0) + \
                 sum(1 for v in trg_fams.values() if v["score"] > 0)
    fam_total_n = len(fit_fams) + len(trg_fams)
    result["coverage"] = round(100.0 * fam_scored / fam_total_n, 0) if fam_total_n else 0.0
    result["signals_counted"] = len(signals)

    tiers = weights.get("tiers_full_evidence" if full_evidence else "tiers", {}) or {}
    if result["gate_failures"]:
        tier, tier_label = "D", "Gate failure — disqualified"
    else:
        tier, tier_label = "D", tiers.get("D", {}).get("label", "Park")
        for name in ("A", "B", "C"):
            t = tiers.get(name, {}) or {}
            if composite >= float(t.get("min_composite", 101)):
                if "min_trigger" in t and trg < float(t["min_trigger"]):
                    continue
                tier, tier_label = name, t.get("label", "")
                break

    result.update({
        "fit": fit, "fit_families": fit_fams,
        "trigger": trg, "trigger_families": trg_fams,
        "access": acc, "access_normalised": round(acc * norm, 2),
        "penalties": penalties, "penalty_total": pen_total,
        "composite": round(composite, 1),
        "tier": tier, "tier_label": tier_label,
        "signal_rows": [
            {"layer": r[0], "id": r[1], "base": r[2], "decay": round(r[3], 2),
             "earned": round(r[4], 2), "evidence": r[5].get("evidence", ""),
             "url": r[5].get("url", "")}
            for r in (fit_rows + trg_rows + acc_rows)
        ],
    })
    return result


# --------------------------------------------------------------------------
def render(r):
    bar = lambda v, m: "#" * int(round(v / m * 24)) + "." * (24 - int(round(v / m * 24)))
    out = []
    out.append("=" * 68)
    out.append(f"  {r['company']}   [{r['domain'] or 'no domain'}]")
    out.append("=" * 68)
    if r["gate_failures"]:
        out.append("  GATE FAILURE — disqualified")
        for g in r["gate_failures"]:
            out.append(f"    x {g['gate']}: {g['evidence']}")
        out.append("")
    out.append(f"  Fit      {r['fit']:>5.1f}/100  [{bar(r['fit'],100)}]")
    for f, v in r["fit_families"].items():
        out.append(f"      {f:<32} {v['score']:>5.1f}/{v['cap']:<5.0f}")
    out.append(f"  Trigger  {r['trigger']:>5.1f}/100  [{bar(r['trigger'],100)}]")
    for f, v in r["trigger_families"].items():
        out.append(f"      {f:<32} {v['score']:>5.1f}/{v['cap']:<5.0f}")
    out.append(f"  Access   {r['access']:>5.1f}/40   [{bar(r['access'],40)}]")
    if r["penalties"]:
        out.append(f"  Penalties {r['penalty_total']:>+5.1f}  "
                   + ", ".join(p["id"] for p in r["penalties"]))
    out.append("-" * 68)
    out.append(f"  COMPOSITE {r['composite']:>5.1f}   ->  TIER {r['tier']}  ({r['tier_label']})")
    out.append(f"  coverage {r.get('coverage',0):.0f}% of signal families evidenced "
               f"({r.get('signals_counted',0)} sourced signals)")
    if r["dropped_unsourced"]:
        out.append(f"  ! dropped, no source URL: {', '.join(str(x) for x in r['dropped_unsourced'])}")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Score Klaris ICP account evidence.")
    ap.add_argument("files", nargs="+", help="account evidence JSON file(s)")
    ap.add_argument("--weights", default=DEFAULT_WEIGHTS)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--full-evidence", action="store_true",
                    help="use full-evidence tier thresholds (CRM/enrichment data present)")
    ap.add_argument("--lenient", action="store_true",
                    help="count signals that have no source URL")
    args = ap.parse_args()

    weights = load_yaml(args.weights)
    paths = []
    for f in args.files:
        paths.extend(sorted(glob.glob(f)) or [f])

    results = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for acct in (data if isinstance(data, list) else [data]):
            results.append(evaluate(acct, weights, args.lenient, args.full_evidence))

    results.sort(key=lambda r: (-r["composite"],))
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(render(r))
        if len(results) > 1:
            print("  RANKED")
            for i, r in enumerate(results, 1):
                print(f"   {i:>2}. [{r['tier']}] {r['composite']:>5.1f}  "
                      f"{r['company']:<26} cov {r.get('coverage',0):>3.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
