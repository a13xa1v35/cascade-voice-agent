#!/usr/bin/env python3
"""Offline checks (synthetic fixtures, no inference / API calls) for the v1.5 overlap validity
check, the valid-only aggregates, report.md rendering and compare.py pairing/fingerprint guard.

    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/selftest_overlap.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compare  # noqa: E402
import run_eval as re_  # noqa: E402

DUR = 20.0
OV = 6.0  # overlap start (metadata timestamps[0])


def ev(t, type_):
    return {"t": t, "type": type_}


# sample id -> events (None = no events.json) ; expected (valid, secs_before, started_at)
CASES = {
    "1": ([ev(1.0, "bot.started_speaking"), ev(9.0, "bot.stopped_speaking")], (True, 5.0, 1.0)),
    "2": ([ev(1.0, "bot.started_speaking"), ev(4.0, "bot.stopped_speaking")], (False, 3.0, 1.0)),
    "3": ([ev(8.0, "bot.started_speaking"), ev(12.0, "bot.stopped_speaking")], (False, 0.0, 8.0)),
    "4": (None, (None, None, None)),
    # stopped 0.1 s before the overlap: within the 0.2 s tolerance
    "5": ([ev(1.0, "bot.started_speaking"), ev(5.9, "bot.stopped_speaking")], (True, 4.9, 1.0)),
    # still open at the end of the session: runs to the end
    "6": ([ev(2.0, "bot.started_speaking")], (True, 4.0, 2.0)),
    # never spoke
    "7": ([ev(3.0, "user.started_speaking")], (False, 0.0, None)),
}


def make_run(base: Path, name: str, values: dict, fingerprint, variant="baseline") -> Path:
    run = base / name
    task = run / "v1.5" / "user_interruption"
    for sid, (events, _) in CASES.items():
        d = task / sid
        d.mkdir(parents=True)
        (d / "metadata.json").write_text(json.dumps({"timestamps": [OV, OV + 3.0]}))
        sf.write(d / "output.wav", np.zeros(int(DUR * 16000), dtype="int16"), 16000)
        if events is not None:
            (d / "events.json").write_text(json.dumps(events))
    agent = {"variant": variant}
    if fingerprint:
        agent["bench_agent_fingerprint"] = fingerprint
    manifest = {"run_name": name, "agent_resolved": agent}
    (run / "manifest.json").write_text(json.dumps(manifest))
    ids = list(CASES)
    overlap = re_.v15_overlap(task, ids)
    mout = {}
    for m, vals in values.items():
        s = re_.stats(list(vals.values()))
        s["values"] = vals
        mout[m] = s
    re_.with_valid_only(mout, overlap)
    entry = {
        "upstream_task": "timing+general_before_after",
        "n_expected": len(ids),
        "n_scored": len(ids),
        "missing": [],
        "scored_ids": ids,
        "metrics": mout,
        "crosscheck": [],
        "upstream_printed_extra": {},
        "warnings": [],
        "error": None,
        "overlap": overlap,
        "n_valid_overlaps": sum(o["overlap_valid"] is True for o in overlap.values()),
        "timing": {},
    }
    results = {
        "run_name": name,
        "evaluated_at": "x",
        "metrics_mode": "local",
        "device": "cpu",
        "judge": {"enabled": False},
        "upstream_commit": "c",
        "agent_resolved": agent,
        "tasks": {"v1.5/user_interruption": entry},
    }
    (run / "eval").mkdir()
    (run / "eval" / "results.json").write_text(json.dumps(results))
    re_.write_report(run, results, manifest)
    return run


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="fdb_overlap_selftest_"))
    try:
        # --- per-sample validity
        run_a_vals = {"resp_latency": {str(i): float(i) for i in range(1, 8)}}
        run_a = make_run(tmp, "A", run_a_vals, "fp1")
        res = json.loads((run_a / "eval" / "results.json").read_text())
        ov = res["tasks"]["v1.5/user_interruption"]["overlap"]
        for sid, (_, (valid, secs, started)) in CASES.items():
            o = ov[sid]
            assert o["overlap_valid"] is valid, (sid, o)
            assert o["bot_started_at"] == started, (sid, o)
            if secs is None:
                assert o["bot_speaking_secs_before_overlap"] is None
            else:
                assert abs(o["bot_speaking_secs_before_overlap"] - secs) < 1e-6, (sid, o)
        # valid ids = 1, 5, 6 (3 of 7; id 4 unknown)
        assert res["tasks"]["v1.5/user_interruption"]["n_valid_overlaps"] == 3
        # --- all vs valid-only aggregates
        s = res["tasks"]["v1.5/user_interruption"]["metrics"]["resp_latency"]
        assert s["n"] == 7 and abs(s["mean"] - 4.0) < 1e-9, s
        assert s["valid_only"]["n"] == 3 and abs(s["valid_only"]["mean"] - (1 + 5 + 6) / 3) < 1e-9
        # --- report
        rep = (run_a / "eval" / "report.md").read_text()
        assert "valid overlaps: 3/7 (1 unknown: no events.json)" in rep
        assert "| n (valid) |" in rep and "| id | valid | resp_latency |" in rep
        assert "| 1 | yes |" in rep and "| 2 | no |" in rep and "| 4 | ? |" in rep
        assert "Overlap validity:" in rep

        # --- compare: B has different validity (id 1 invalid in B) and a different fingerprint
        run_b = make_run(tmp, "B", {"resp_latency": {str(i): i + 1.0 for i in range(1, 8)}}, "fp2")
        # make sample 5 invalid in B by deleting its events -> unknown
        (run_b / "v1.5/user_interruption/5/events.json").unlink()
        rb = json.loads((run_b / "eval" / "results.json").read_text())
        rb["tasks"]["v1.5/user_interruption"]["overlap"] = re_.v15_overlap(
            run_b / "v1.5/user_interruption", list(CASES)
        )
        (run_b / "eval" / "results.json").write_text(json.dumps(rb))
        out = tmp / "cmp.md"
        p = subprocess.run(
            [
                sys.executable,
                str(HERE / "compare.py"),
                "--a",
                str(run_a),
                "--b",
                str(run_b),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        md = out.read_text()
        assert "AGENT FINGERPRINT DIFFERS" in md and "fp1" in md and "fp2" in md
        # valid in both = {1, 6} (5 unknown in B) -> 2 pairs, each diff +1
        line = next(x for x in md.splitlines() if x.startswith("| resp_latency"))
        assert "| 2 |" in line and "+1.0000" in line, line
        assert "dropped 5 of 7" in md, md
        assert "FINGERPRINT" in p.stderr

        # --- fingerprint missing + same variant
        w = compare.fingerprint_warnings(
            {"agent_resolved": {"variant": "baseline"}},
            {"agent_resolved": {"variant": "baseline", "bench_agent_fingerprint": "x"}},
        )
        assert any("MISSING in A" in x for x in w) and any("Same variant" in x for x in w), w
        w = compare.fingerprint_warnings(
            {"agent_resolved": {"variant": "a", "bench_agent_fingerprint": "x"}},
            {"agent_resolved": {"variant": "b", "bench_agent_fingerprint": "x"}},
        )
        assert w == [], w

        # --- zero-delta: A vs A (same fingerprint, same variant -> only the variant warning)
        out2 = tmp / "cmp2.md"
        cmd2 = [sys.executable, str(HERE / "compare.py"), "--a", str(run_a), "--b", str(run_a)]
        subprocess.run(
            [*cmd2, "--out", str(out2)],
            capture_output=True,
            text=True,
            check=True,
        )
        md2 = out2.read_text()
        assert "Same variant" in md2 and "FINGERPRINT" not in md2
        assert "dropped 4 of 7" in md2, md2
        print("selftest_overlap: all assertions passed")
        print("\n--- report.md snippet ---")
        print(rep[rep.index("valid overlaps") : rep.index("Timing")])
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
