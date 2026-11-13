#!/usr/bin/env python3
"""Paired comparison of two scored runs (same samples, baseline A vs variant B).

    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/compare.py \
        --a evals/results/turn_taking/A --b evals/results/turn_taking/B [--out compare.md]

Reads <run>/eval/results.json, pairs per-sample values by (version, task, id), and per metric
reports n_pairs, mean A, mean B, mean diff (B - A) with a 95% percentile-bootstrap CI (paired
resampling,
10k draws, seed 0) and a paired test:
  * binary metrics (TOR, behavior_*): exact McNemar test on discordant pairs
  * continuous metrics: Wilcoxon signed-rank test (zero differences dropped)
Pairs where either side is null are dropped (note: latency exists only for TOR=1 samples, so
latency pairs are the samples where both runs took the turn). No multiple-comparison correction.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

SKIP = {"split_t"}


def load(run: Path):
    p = run / "eval" / "results.json"
    if not p.exists():
        sys.exit(f"{p} not found; run run_eval.py first")
    return json.loads(p.read_text())


def is_binary(vals):
    return len(vals) > 0 and all(v in (0, 1) for v in vals)


def bootstrap_ci(d, n_boot=10000, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    m = d[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def paired_test(a, b):
    d = b - a
    if np.all(d == 0):
        return "n/a (identical)", 1.0
    if is_binary(list(a)) and is_binary(list(b)):
        n01 = int(((a == 0) & (b == 1)).sum())
        n10 = int(((a == 1) & (b == 0)).sum())
        return f"McNemar exact (b={n01}, c={n10})", float(
            stats.binomtest(n01, n01 + n10, 0.5).pvalue
        )
    nz = d[d != 0]
    if len(nz) < 6:
        return "n/a (<6 non-zero pairs)", None
    return "Wilcoxon signed-rank", float(stats.wilcoxon(nz).pvalue)


def fingerprint_warnings(A: dict, B: dict) -> list[str]:
    """Prominent warnings when the two runs' agents may differ beyond the design under test."""
    ra, rb = A.get("agent_resolved") or {}, B.get("agent_resolved") or {}
    fa, fb = ra.get("bench_agent_fingerprint"), rb.get("bench_agent_fingerprint")
    out = []
    if not fa or not fb:
        missing = " and ".join(n for n, f in (("A", fa), ("B", fb)) if not f)
        out.append(
            f"**AGENT FINGERPRINT MISSING in {missing}** "
            "(agent_resolved.bench_agent_fingerprint): cannot verify the agent is identical, "
            "so agent changes may be mixed with design changes."
        )
    elif fa != fb:
        out.append(
            f"**AGENT FINGERPRINT DIFFERS** (A={fa}, B={fb}): the agent changed between the runs, "
            "so this comparison mixes agent changes with design changes."
        )
    va, vb = ra.get("variant"), rb.get("variant")
    if va is not None and va == vb:
        out.append(
            f"**Same variant `{va}` in A and B**: this is not a design comparison "
            "(only run-to-run noise or non-variant config changes)."
        )
    return out


def valid_in_both(ta: dict, tb: dict) -> set[str] | None:
    """Ids whose v1.5 overlap is valid in both runs; None when either run lacks the info."""
    oa, ob = ta.get("overlap"), tb.get("overlap")
    if oa is None or ob is None:
        return None
    return {i for i, o in oa.items() if o["overlap_valid"] is True and i in ob} & {
        i for i, o in ob.items() if o["overlap_valid"] is True
    }


def _fmt(x, nd=0):
    return "-" if x is None else f"{x:.{nd}f}"


def system1_section(A: dict, B: dict, keys: list[str]) -> list[str]:
    """Side-by-side system-one aggregates; empty when neither run has system1 events."""
    rows = []
    for k in keys:
        a = (A["tasks"].get(k) or {}).get("system1")
        b = (B["tasks"].get(k) or {}).get("system1")
        if not a and not b:
            continue
        for label, x in (("A", a), ("B", b)):
            g = x["aggregate"] if x else None
            if g is None:
                rows.append(f"| {k} | {label} | - | - | - | - | - |")
                continue
            oc = ", ".join(f"{n} {v}" for n, v in sorted(g["outcomes"].items())) or "-"
            ac = ", ".join(f"{n} {v}" for n, v in sorted(g["actions"].items())) or "-"
            hs = "-" if g["hedged_share"] is None else f"{g['hedged_share']:.1%}"
            rows.append(
                f"| {k} | {label} | {g['n_judgments']} | {oc} | "
                f"{_fmt(g['latency_ms_p50'])} / {_fmt(g['latency_ms_p90'])} | {hs} | {ac} |"
            )
    if not rows:
        return []
    return [
        "## System one",
        "",
        "| task | run | judgments | outcomes | latency p50 / p90 (ms, ok) | hedged | actions |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, type=Path, help="baseline run dir")
    ap.add_argument("--b", required=True, type=Path, help="variant run dir")
    ap.add_argument("--out", type=Path, help="default: <b>/eval/compare.md")
    args = ap.parse_args()
    A, B = load(args.a), load(args.b)
    L = [
        f"# Paired comparison: A=`{A['run_name']}` (baseline) vs B=`{B['run_name']}`",
        "",
        "Diff = B - A. CI: paired percentile bootstrap (10k, seed 0). p: see test column. "
        "Uncorrected for multiple comparisons.",
        "",
    ]
    warns = fingerprint_warnings(A, B)
    if A.get("judge") != B.get("judge"):
        warns.append(f"judge config differs: A={A.get('judge')} B={B.get('judge')}")
    if A.get("upstream_commit") != B.get("upstream_commit"):
        warns.append("upstream commit differs")
    keys = sorted(set(A["tasks"]) | set(B["tasks"]))
    body = []
    for k in keys:
        ta, tb = A["tasks"].get(k), B["tasks"].get(k)
        if not ta or not tb:
            warns.append(f"{k}: present only in {'A' if ta else 'B'}")
            continue
        ia, ib = set(ta["scored_ids"]), set(tb["scored_ids"])
        if ia != ib:
            warns.append(
                f"{k}: sample sets differ (only A: {len(ia - ib)}, only B: {len(ib - ia)}, "
                f"shared: {len(ia & ib)}); comparing shared samples only"
            )
        keep = None
        if k.startswith("v1.5/"):
            keep = valid_in_both(ta, tb)
            shared = ia & ib
            if keep is None:
                warns.append(f"{k}: no overlap-validity info in A or B; using all shared samples")
            else:
                dropped = len(shared - keep)
                warns.append(
                    f"{k}: dropped {dropped} of {len(shared)} shared pairs "
                    "(overlap invalid or unknown in A or B); pairing valid-in-both only"
                )
        body += [
            f"## {k}",
            "",
            "| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for m in sorted(set(ta["metrics"]) & set(tb["metrics"])):
            if m in SKIP:
                continue
            va, vb = ta["metrics"][m]["values"], tb["metrics"][m]["values"]
            pairs = [
                (va[i], vb[i])
                for i in sorted(set(va) & set(vb))
                if (keep is None or i in keep) and va[i] is not None and vb[i] is not None
            ]
            if not pairs:
                body.append(f"| {m} | 0 | - | - | - | - | - | - |")
                continue
            a = np.array([p[0] for p in pairs], float)
            b = np.array([p[1] for p in pairs], float)
            d = b - a
            lo, hi = bootstrap_ci(d)
            test, p = paired_test(a, b)
            p_txt = "-" if p is None else f"{p:.4f}"
            body.append(
                f"| {m} | {len(a)} | {a.mean():.4f} | {b.mean():.4f} | {d.mean():+.4f} | "
                f"[{lo:+.4f}, {hi:+.4f}] | {test} | {p_txt} |"
            )
        body.append("")
    if warns:
        L += ["## Warnings", ""] + [f"- {w}" for w in warns] + [""]
        for w in warns:
            print("WARNING:", w, file=sys.stderr)
    sys1 = system1_section(A, B, keys)
    L += body + sys1
    out = args.out or (args.b / "eval" / "compare.md")
    out.write_text("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
