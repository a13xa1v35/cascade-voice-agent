#!/usr/bin/env python3
"""Offline checks (synthetic fixtures) for the event-derived diagnostics: pause-handling
premature_turn_end / premature_llm_start and the system-one stats, plus compare.py's handling.

    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/selftest_diag.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_eval as re_  # noqa: E402


def e(t, type_, **kw):
    return {"t": t, "type": type_, **kw}


def main() -> int:
    # --- pause metrics: pause [5.0, 6.0] -> stop window [4.7, 6.5], llm window up to 8.5
    p = [5.0, 6.0]
    m = re_.pause_event_metrics([e(5.5, "user_turn.stopped"), e(7.0, "llm.text")], p)
    assert m == {"premature_turn_end": 1, "premature_llm_start": 1}, m
    m = re_.pause_event_metrics([e(5.5, "user_turn.stopped"), e(9.0, "llm.text")], p)
    assert m == {"premature_turn_end": 1, "premature_llm_start": 0}, m  # llm after p1+2.5
    m = re_.pause_event_metrics([e(4.6, "user_turn.stopped"), e(7.0, "llm.text")], p)
    assert m == {"premature_turn_end": 0, "premature_llm_start": 0}, m  # stop before window
    m = re_.pause_event_metrics([e(6.5, "user_turn.stopped")], p)
    assert m["premature_turn_end"] == 1  # inclusive upper edge
    m = re_.pause_event_metrics([e(7.0, "llm.text")], p)
    assert m == {"premature_turn_end": 0, "premature_llm_start": 0}, m  # llm without a stop
    assert re_.pause_event_metrics(None, p)["premature_turn_end"] is None

    # --- system one, system_one_eot style (results) and system_one style (action, stale, cancelled)
    ev = [
        e(1, "system1.judgment", latency_ms=200, outcome="ok", hedged=False, winner="primary"),
        e(2, "system1.judgment", latency_ms=800, outcome="ok", hedged=True, winner="secondary"),
        e(3, "system1.judgment", latency_ms=30, outcome="cancelled (CancelledError): x"),
        e(4, "system1.judgment", latency_ms=500, outcome="error: boom", hedged=True),
        e(5, "system1.judgment", latency_ms=100, outcome="timeout", action="keep_listening"),
        e(6, "system1.judgment", latency_ms=90, outcome="ok (stale)", action="keep_listening"),
        e(7, "system1.judgment", latency_ms=400, outcome="ok", action="end_turn"),
        e(8, "system1.action", action="fallback"),
        e(9, "service.reconnect"),
    ]
    st = re_.system1_sample(ev)
    assert st["n_judgments"] == 7, st
    assert st["outcomes"] == {"ok": 3, "cancelled": 1, "error": 1, "timeout": 1, "stale": 1}, st
    assert st["ok_latency_ms"] == [200.0, 800.0, 400.0] and st["latency_ms_p50"] == 400.0
    assert (st["n_hedged"], st["n_hedge_known"]) == (2, 3), st
    assert st["actions"] == {"keep_listening": 2, "end_turn": 1, "fallback": 1}, st
    assert st["n_errors"] == 1
    assert re_.system1_sample([e(1, "vad.user_started")]) is None
    assert re_.system1_sample(None) is None

    # --- task aggregate + report block + compare
    tmp = Path(tempfile.mkdtemp(prefix="fdb_diag_selftest_"))
    try:
        runs = {}
        for name, with_s1, stop_t in (("A", False, 7.0), ("B", True, 5.5)):
            run = tmp / name
            task = run / "v1" / "candor_pause_handling"
            ids = ["1", "2"]
            for sid in ids:
                d = task / sid
                d.mkdir(parents=True)
                (d / "pause.json").write_text(json.dumps([{"text": "[PAUSE]", "timestamp": p}]))
                events = [e(stop_t, "user_turn.stopped")] if sid == "1" else []
                if with_s1 and sid == "1":
                    events += ev
                (d / "events.json").write_text(json.dumps(events))
            metrics = re_.pause_metrics(task, ids)
            assert metrics["premature_turn_end"] == {"1": int(stop_t == 5.5), "2": 0}, metrics
            mout = {}
            for k, vals in metrics.items():
                s = re_.stats(list(vals.values()))
                s["values"] = vals
                mout[k] = s
            s1 = re_.system1_task(task, ids)
            assert (s1 is not None) == with_s1
            entry = {
                "upstream_task": "pause_handling",
                "n_expected": 2,
                "n_scored": 2,
                "missing": [],
                "scored_ids": ids,
                "metrics": mout,
                "crosscheck": [],
                "upstream_printed_extra": {},
                "warnings": [],
                "error": None,
                "overlap": None,
                "system1": s1,
                "timing": {},
            }
            res = {
                "run_name": name,
                "evaluated_at": "x",
                "metrics_mode": "local",
                "device": "cpu",
                "judge": {"enabled": False},
                "upstream_commit": "c",
                "agent_resolved": {"variant": name, "bench_agent_fingerprint": "fp"},
                "tasks": {"v1/candor_pause_handling": entry},
            }
            (run / "eval").mkdir()
            (run / "eval" / "results.json").write_text(json.dumps(res))
            re_.write_report(run, res, {})
            runs[name] = run
        rep = (runs["B"] / "eval" / "report.md").read_text()
        assert "System one:" in rep and "judgments: 7" in rep and "p50 400" in rep, rep
        assert "hedged share: 66.7%" in rep and "actions: end_turn 1" in rep
        assert "System one:" not in (runs["A"] / "eval" / "report.md").read_text()
        assert "| premature_turn_end | 2 | 0.500 |" in rep

        out = tmp / "cmp.md"
        subprocess.run(
            [
                sys.executable,
                str(HERE / "compare.py"),
                "--a",
                str(runs["A"]),
                "--b",
                str(runs["B"]),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        md = out.read_text()
        assert "| premature_turn_end | 2 |" in md and "+0.5000" in md, md
        assert "## System one" in md and "| v1/candor_pause_handling | A | - |" in md
        print("selftest_diag: all assertions passed\n\n--- system-one block (B report) ---")
        print(rep[rep.index("System one:") : rep.index("System one:") + 460])
        print("--- compare System one section ---")
        print(md[md.index("## System one") :])
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
