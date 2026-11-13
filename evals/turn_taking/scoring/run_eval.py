#!/usr/bin/env python3
"""Score a stage-1 run directory with the (patched) upstream Full-Duplex-Bench code.

    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/run_eval.py \
        --run evals/results/turn_taking/<run_name> [--tasks v1/candor_pause_handling,...] [--force]

Per task: ASR (Parakeet, CPU unless CUDA) -> upstream evaluation script -> per-sample JSON
dumped by the patch -> results.json + report.md under <run>/eval/.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # repo root: evals.turn_taking.cost (stdlib-only)

from evals.turn_taking import cost as run_cost  # noqa: E402

UPSTREAM = HERE / "third_party" / "Full-Duplex-Bench" / "v1_v1.5"

# (version, task) -> upstream evaluation mapping
V1_TASKS = {
    ("v1", "candor_pause_handling"): ("pause_handling", "default"),
    ("v1", "synthetic_pause_handling"): ("pause_handling", "default"),
    ("v1", "candor_turn_taking"): ("smooth_turn_taking", "default"),
    ("v1", "icc_backchannel"): ("backchannel", "default"),
    ("v1", "synthetic_user_interruption"): ("user_interruption", "user_interruption"),
}
V15_TASKS = ["user_interruption", "user_backchannel", "talking_to_other", "background_speech"]
JUDGED = {"user_interruption", "behavior"}  # upstream tasks that call an LLM judge

DEFS = {
    "premature_turn_end": "Pause handling: 1 if the design tried to take the turn during the pause "
    "even if no audio came out "
    "(a user_turn.stopped event in [pause start - 0.3 s, pause end + 0.5 s]).",
    "premature_llm_start": "Pause handling: 1 if an llm.text event followed that premature stop "
    "(up to pause end + 2.5 s), i.e. the LLM actually started answering.",
    "TOR": "Turn-taking rate: share of samples where the agent took a turn "
    "(>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; "
    "for turn_taking/interruption HIGHER is better.",
    "n_words": "Number of ASR words in the agent's output.",
    "latency": "Seconds from the user turn/interruption end to the agent's first word, "
    "clamped at 0; only samples with TOR=1.",
    "latency_raw": "Same as latency but unclamped "
    "(negative = agent started before the user finished).",
    "score": "LLM-judge relevance rating of the agent's reply after the interruption, 0-5 "
    "(null if judge off/failed or TOR=0).",
    "JSD": "Jensen-Shannon divergence between the agent's backchannel timing histogram and "
    "the ICC human distribution (lower is better; 1 if no backchannel).",
    "freq": "Backchannels per second of audio.",
    "n_backchannels": "Number of short agent speech segments counted as backchannels.",
    "stop_latency": "v1.5 timing: mean duration (s) of user/model speech-overlap intervals "
    "in latency_intervals.json (Silero VAD).",
    "resp_latency": "v1.5 timing: mean gap (s) from the end of user speech to the next "
    "model speech start (Silero VAD).",
    "n_stop_intervals": "Number of overlap intervals found by get_timing.py.",
    "n_resp_intervals": "Number of response-gap intervals found by get_timing.py.",
    "utmosv2": "UTMOSv2 speech-quality MOS (1-5) of the segment.",
    "wpm": "Words per minute over speech-only time.",
    "speech_dur_s": "Speech duration (s) used for wpm.",
    "mean_pitch": "Mean F0 (Hz).",
    "std_pitch": "Std of F0 (Hz).",
    "mean_intensity": "Mean intensity (dB).",
    "std_intensity": "Std of intensity (dB).",
}


def definition(metric: str) -> str:
    if metric in DEFS:
        return DEFS[metric]
    for pre in ("pre_", "post_", "clean_"):
        if metric.startswith(pre) and metric[len(pre) :] in DEFS:
            seg = {
                "pre_": "before the overlap",
                "post_": "after the overlap",
                "clean_": "in the clean (no-overlap) run",
            }[pre]
            return f"{DEFS[metric[len(pre) :]]} Computed {seg}."
    if metric.startswith("behavior_"):
        return (
            "Judge label: 1 if the first post-overlap segment was tagged "
            + metric[9:]
            + " (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0."
        )
    return ""


# ----------------------------------------------------------------------------------------
def sh(cmd, cwd, env, log: Path, label: str):
    """Run a subprocess, tee to log, return (rc, seconds, text)."""
    t0 = time.time()
    p = subprocess.run(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    dt = time.time() - t0
    with log.open("a") as f:
        f.write(f"$ {' '.join(map(str, cmd))}\n{p.stdout}\n[exit {p.returncode}, {dt:.1f}s]\n\n")
    if p.returncode != 0:
        print(f"    !! {label} failed (exit {p.returncode}); tail of {log}:")
        print("\n".join(p.stdout.splitlines()[-15:]))
    return p.returncode, dt, p.stdout


def stats(vals):
    v = [x for x in vals if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x]
    # bools are 0/1 flags: keep them numeric
    v += [float(x) for x in vals if isinstance(x, bool)]
    if not v:
        return {"n": 0, "mean": None, "median": None, "p90": None, "std": None}
    a = np.asarray(v, dtype=float)
    return {
        "n": len(v),
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "p90": float(np.percentile(a, 90)),
        "std": float(a.std()),
    }


def wav_seconds(p: Path) -> float:
    import soundfile as sf

    try:
        return float(sf.info(str(p)).duration)
    except Exception:
        return 0.0


def parse_asr_log(text: str):
    out = {"model_load_s": 0.0, "transcribe_s": 0.0, "audio_s": 0.0, "files": 0}
    for m in re.finditer(r"\[asr\] model_load_s=([\d.]+)", text):
        out["model_load_s"] += float(m.group(1))
    for m in re.finditer(r"\[asr\] transcribe_s=([\d.]+) audio_s=([\d.]+) files=(\d+)", text):
        out["transcribe_s"] += float(m.group(1))
        out["audio_s"] += float(m.group(2))
        out["files"] += int(m.group(3))
    return out


def printed_aggregates(up_task: str, text: str):
    """Numbers the upstream script printed (for cross-checking per-sample means)."""
    g = {}

    def num(pat):
        m = re.findall(pat, text)
        return float(m[-1]) if m else None

    if up_task in ("pause_handling", "smooth_turn_taking", "user_interruption"):
        g["TOR"] = num(r"Average take turn:\s+([-\d.eE]+|nan)")
        if up_task != "pause_handling":
            g["latency"] = num(r"Average latency:\s+([-\d.eE]+|nan)")
        if up_task == "user_interruption":
            g["score"] = num(r"Average rating:\s+([-\d.eE]+)")
    elif up_task == "backchannel":
        g["JSD"] = num(r"JSD - Mean: ([-\d.eE]+)")
        g["TOR"] = num(r"TOR - Mean: ([-\d.eE]+)")
        g["freq"] = num(r"Frequency - Mean: ([-\d.eE]+)")
    elif up_task == "general_before_after":
        m = re.findall(r"General Evaluation Output: (\{.*\})", text)
        if m:
            with contextlib.suppress(Exception):
                g["trimmed_means"] = ast.literal_eval(m[-1])
    elif up_task == "behavior":
        m = re.findall(r"Ratios \(C-axis\): (\{.*\})", text)
        if m:
            with contextlib.suppress(Exception):
                g["ratios"] = ast.literal_eval(m[-1])
    return {k: v for k, v in g.items() if v is not None}


def sample_ids(root: Path):
    return sorted(
        (d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")),
        key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 0, x),
    )


def read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


# ---------------------------------------------------------------------------------------


def read_env_file_var(env_file: str | None, var: str) -> str | None:
    """Value of `var` in a dotenv file (KEY=value, optional quotes / trailing # comment)."""
    if not env_file or not Path(env_file).is_file():
        return None
    for line in Path(env_file).read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == var:
            value = value.split(" #", 1)[0].strip().strip("'\"")
            return value or None
    return None


OVERLAP_TOL_S = 0.2  # bot may have stopped up to this long before the overlap and still count
OVERLAP_WHY = (
    "Overlap validity: v1.5 assumes the agent is still speaking when the overlap starts "
    "(metadata timestamps[0]); if it had already finished or not yet started, the sample tests "
    "nothing, so the valid-only rows exclude those (and samples whose events.json is missing)."
)


def bot_intervals(events: list, end_s: float | None) -> list[tuple[float, float]]:
    """Bot speaking intervals from bot.started_speaking / bot.stopped_speaking events.

    An interval still open at the end runs to end_s (output.wav is truncated to the input
    length); with no end_s it runs to the last event time.
    """
    evs = sorted(
        (e for e in events if isinstance(e, dict) and "t" in e), key=lambda e: float(e["t"])
    )
    out, start = [], None
    last_t = float(evs[-1]["t"]) if evs else 0.0
    for e in evs:
        t = float(e["t"])
        if e.get("type") == "bot.started_speaking" and start is None:
            start = t
        elif e.get("type") == "bot.stopped_speaking" and start is not None:
            out.append((start, t))
            start = None
    if start is not None:
        out.append((start, max(end_s if end_s is not None else last_t, start)))
    return out


def overlap_validity(
    events: list | None,
    overlap_start: float,
    end_s: float | None = None,
    tol: float = OVERLAP_TOL_S,
) -> dict:
    """Was the bot speaking at overlap_start (allowing `tol` s of slack before it)?"""
    if events is None:
        return {
            "overlap_valid": None,
            "bot_speaking_secs_before_overlap": None,
            "bot_started_at": None,
        }
    iv = bot_intervals(events, end_s)
    valid = any(s <= overlap_start and e > overlap_start - tol for s, e in iv)
    secs = sum(max(0.0, min(e, overlap_start) - s) for s, e in iv)
    return {
        "overlap_valid": bool(valid),
        "bot_speaking_secs_before_overlap": round(secs, 3),
        "bot_started_at": iv[0][0] if iv else None,
    }


def v15_overlap(root: Path, ids: list[str]) -> dict:
    """Per-sample overlap validity from the input session's events.json (primary source).

    A VAD cross-check on output.wav is deliberately not done: it needs another model pass
    and events.json is authoritative.
    """
    res = {}
    for sid in ids:
        meta = read_json(root / sid / "metadata.json") or {}
        events = read_json(root / sid / "events.json")
        ts = meta.get("timestamps")
        if not ts or not isinstance(events, list):
            res[sid] = overlap_validity(None, 0.0)
            continue
        end_s = wav_seconds(root / sid / "output.wav") or wav_seconds(root / sid / "input.wav")
        res[sid] = overlap_validity(events, float(ts[0]), end_s or None)
    return res


def with_valid_only(mout: dict, overlap: dict) -> None:
    """Add s["valid_only"] (stats over samples with overlap_valid is True) to every metric."""
    valid = {sid for sid, o in overlap.items() if o["overlap_valid"] is True}
    for s in mout.values():
        s["valid_only"] = stats([v for sid, v in s["values"].items() if sid in valid])


PAUSE_STOP_BEFORE_S, PAUSE_STOP_AFTER_S, PAUSE_LLM_AFTER_S = 0.3, 0.5, 2.5


def pause_event_metrics(events: list | None, pause_ts: list[float]) -> dict:
    """premature_turn_end / premature_llm_start from events.json and the annotated pause."""
    if events is None:
        return {"premature_turn_end": None, "premature_llm_start": None}
    p0, p1 = float(pause_ts[0]), float(pause_ts[1])
    stops = [
        e["t"]
        for e in events
        if e["type"] == "user_turn.stopped"
        and p0 - PAUSE_STOP_BEFORE_S <= e["t"] <= p1 + PAUSE_STOP_AFTER_S
    ]
    llm = [
        e["t"]
        for e in events
        if e["type"] == "llm.text" and stops and stops[0] <= e["t"] <= p1 + PAUSE_LLM_AFTER_S
    ]
    return {"premature_turn_end": int(bool(stops)), "premature_llm_start": int(bool(llm))}


def pause_metrics(root: Path, ids: list[str]) -> dict:
    out: dict = {"premature_turn_end": {}, "premature_llm_start": {}}
    for sid in ids:
        pj = read_json(root / sid / "pause.json")
        events = read_json(root / sid / "events.json")
        if not pj or not isinstance(events, list):
            continue
        for k, v in pause_event_metrics(events, pj[0]["timestamp"]).items():
            out[k][sid] = v
    return {k: v for k, v in out.items() if v}


def outcome_class(outcome: str) -> str:
    """ok / error / timeout / cancelled / stale ('... (stale)' = judged after newer speech)."""
    o = (outcome or "").strip()
    if o.endswith("(stale)"):
        return "stale"
    return o.split(":", 1)[0].split(" ", 1)[0] or "unknown"


def system1_sample(events: list | None) -> dict | None:
    """System-one stats of one sample, or None if it has no system1.* events."""
    if not events:
        return None
    s1 = [e for e in events if str(e.get("type", "")).startswith("system1.")]
    if not s1:
        return None
    js = [e for e in s1 if e["type"] == "system1.judgment"]
    outcomes: dict[str, int] = {}
    for e in js:
        c = outcome_class(e.get("outcome", ""))
        outcomes[c] = outcomes.get(c, 0) + 1
    lat = [float(e["latency_ms"]) for e in js if outcome_class(e.get("outcome", "")) == "ok"]
    hedge_known = [e for e in js if "hedged" in e]
    actions: dict[str, int] = {}
    for e in s1:
        a = e.get("action")
        if a and e["type"] in ("system1.judgment", "system1.action"):
            actions[a] = actions.get(a, 0) + 1
    return {
        "n_judgments": len(js),
        "outcomes": outcomes,
        "ok_latency_ms": lat,
        "latency_ms_p50": float(np.percentile(lat, 50)) if lat else None,
        "latency_ms_p90": float(np.percentile(lat, 90)) if lat else None,
        "n_hedged": sum(bool(e["hedged"]) for e in hedge_known),
        "n_hedge_known": len(hedge_known),
        "actions": actions,
        "n_errors": sum(e["type"] == "system1.error" for e in s1)
        + sum(e.get("type") in ("service.error", "service.reconnect") for e in events),
    }


def system1_task(root: Path, ids: list[str]) -> dict | None:
    """Per-sample stats plus a task aggregate; None when no sample has system1 events."""
    per = {}
    for sid in ids:
        ev = read_json(root / sid / "events.json")
        st = system1_sample(ev if isinstance(ev, list) else None)
        if st:
            per[sid] = st
    if not per:
        return None
    outcomes: dict[str, int] = {}
    actions: dict[str, int] = {}
    lat: list[float] = []
    for st in per.values():
        for k, v in st["outcomes"].items():
            outcomes[k] = outcomes.get(k, 0) + v
        for k, v in st["actions"].items():
            actions[k] = actions.get(k, 0) + v
        lat += st["ok_latency_ms"]
    known = sum(st["n_hedge_known"] for st in per.values())
    agg = {
        "n_samples_with_system1": len(per),
        "n_samples": len(ids),
        "n_judgments": sum(st["n_judgments"] for st in per.values()),
        "outcomes": outcomes,
        "latency_ms_p50": float(np.percentile(lat, 50)) if lat else None,
        "latency_ms_p90": float(np.percentile(lat, 90)) if lat else None,
        "hedged_share": (sum(st["n_hedged"] for st in per.values()) / known) if known else None,
        "actions": actions,
        "n_errors": sum(st["n_errors"] for st in per.values()),
    }
    return {"aggregate": agg, "per_sample": per}


def system1_lines(agg: dict) -> list[str]:
    oc = ", ".join(f"{k} {v}" for k, v in sorted(agg["outcomes"].items())) or "-"
    hs = agg["hedged_share"]
    out = [
        f"- samples with system1 events: {agg['n_samples_with_system1']}/{agg['n_samples']}; "
        f"judgments: {agg['n_judgments']}; outcomes: {oc}",
        f"- latency over ok calls (ms): p50 {fmt(agg['latency_ms_p50'], 0)}, "
        f"p90 {fmt(agg['latency_ms_p90'], 0)}; hedged share: "
        + ("-" if hs is None else f"{hs:.1%}"),
    ]
    if agg["actions"]:
        out.append("- actions: " + ", ".join(f"{k} {v}" for k, v in sorted(agg["actions"].items())))
    if agg["n_errors"]:
        out.append(f"- service/system1 errors+reconnects: {agg['n_errors']}")
    return out


class Runner:
    def __init__(self, run: Path, manifest: dict, force: bool):
        self.run, self.manifest, self.force = run, manifest, force
        ev = (manifest.get("config") or {}).get("eval") or {}
        self.device = ev.get("device", "auto")
        self.metrics_mode = ev.get("metrics", "local")
        self.judge = ev.get("judge") or {}
        self.env = dict(os.environ)
        self.env.update({"PYTHONUNBUFFERED": "1", "TOKENIZERS_PARALLELISM": "false"})
        if self.device == "cpu":
            self.env["CUDA_VISIBLE_DEVICES"] = ""
        if self.metrics_mode == "all":
            self.env.pop("FDB_SKIP_JUDGE", None)
            if self.judge.get("provider"):
                self.env["FDB_JUDGE_PROVIDER"] = self.judge["provider"]
            if self.judge.get("model"):
                self.env["FDB_JUDGE_MODEL"] = self.judge["model"]
            # Appended across invocations: a resumed scoring only pays for the samples it redoes.
            self.env["FDB_JUDGE_USAGE_LOG"] = str(self.run / "eval" / run_cost.JUDGE_LOG)
        else:
            self.env["FDB_SKIP_JUDGE"] = "1"
            self.env.pop("FDB_JUDGE_PROVIDER", None)
            self.env.pop("FDB_JUDGE_MODEL", None)

    def judge_info(self):
        if self.metrics_mode != "all":
            return {"enabled": False}
        return {
            "enabled": True,
            "provider": self.judge.get("provider", "openai"),
            "model": self.judge.get("model")
            or "(upstream default: gpt-4-turbo / gpt-4o-2024-08-06)",
        }

    def check_judge_key(self):
        prov = self.judge.get("provider", "openai")
        var = "ANTHROPIC_API_KEY" if prov == "anthropic" else "OPENAI_API_KEY"
        if not self.env.get(var):
            # Fall back to the agent's env_file recorded in the manifest (same .env as stage 1).
            value = read_env_file_var(self.manifest.get("config", {}).get("env_file"), var)
            if value:
                self.env[var] = value
        if not self.env.get(var):
            sys.exit(
                f"metrics=all with judge provider {prov!r} needs {var} in the environment "
                f"(or set eval.metrics=local in the manifest)."
            )

    # ---- ASR
    def asr(
        self,
        root: Path,
        logdir: Path,
        audio_name: str,
        up_task: str,
        tstages: dict,
        never_force: bool = False,
    ):
        cmd = [
            sys.executable,
            "get_transcript/asr.py",
            "--root_dir",
            str(root),
            "--task",
            up_task,
            "--audio_name",
            audio_name,
        ]
        force = self.force and not never_force
        if not force:
            cmd.append("--skip_existing")
        jname = audio_name.rsplit(".", 1)[0] + ".json"
        todo = [
            d
            for d in root.iterdir()
            if (d / audio_name).exists() and (force or not (d / jname).exists())
        ]
        if not todo:
            print(f"    asr {audio_name}: up to date")
            return True
        print(f"    asr {audio_name}: {len(todo)} files ...", flush=True)
        rc, dt, text = sh(cmd, UPSTREAM, self.env, logdir / "asr.log", f"asr {audio_name}")
        info = parse_asr_log(text)
        info["wall_s"] = dt
        info["audio_name"] = audio_name
        tstages.setdefault("asr", []).append(info)
        if info["audio_s"]:
            print(
                f"      model load {info['model_load_s']:.1f}s; "
                f"transcribe {info['transcribe_s']:.1f}s for {info['audio_s']:.1f}s audio = "
                f"{info['transcribe_s'] / info['audio_s']:.2f} s/audio-s"
            )
        return rc == 0

    def evaluate(self, root: Path, logdir: Path, task: str, tstages: dict, cwd_log: bool = True):
        env = dict(self.env)
        env["FDB_PER_SAMPLE_DIR"] = str(logdir)
        cmd = [
            sys.executable,
            str(UPSTREAM / "evaluation" / "evaluate.py"),
            "--task",
            task,
            "--root_dir",
            str(root),
        ]
        rc, dt, text = sh(cmd, logdir, env, logdir / f"evaluate_{task}.log", f"evaluate {task}")
        tstages.setdefault("eval", {})[task] = dt
        print(f"    evaluate {task}: {dt:.1f}s")
        return rc == 0, text


def v1_task(r: Runner, version, task, up_task, asr_task, ids_expected, root, logdir):
    stages = {}
    asr_ok = r.asr(root, logdir, "output.wav", asr_task, stages)
    if up_task == "user_interruption" and r.metrics_mode == "all":
        r.check_judge_key()
    ok_eval, text = r.evaluate(root, logdir, up_task, stages) if asr_ok else (False, "")
    per = read_json(logdir / f"per_sample_{up_task}.json") if ok_eval else None
    metrics, scored = {}, []
    if per:
        for row in per:
            sid = row["id"]
            scored.append(sid)
            for k, v in row.items():
                if k == "id":
                    continue
                metrics.setdefault(k, {})[sid] = v
    return stages, metrics, scored, printed_aggregates(up_task, text), ok_eval


def v15_task(r: Runner, version, task, ids_expected, root, logdir):
    stages = {}
    metrics, scored = {}, set()
    ok = r.asr(root, logdir, "output.wav", "default", stages)
    ok &= r.asr(root, logdir, "clean_output.wav", "default", stages)
    if r.metrics_mode == "all":
        # shipped input.json/clean_input.json are symlinked from the dataset; ASR only if absent
        # never_force: input.json / clean_input.json are symlinks into evals/turn_taking/data;
        # never overwrite them
        r.asr(root, logdir, "input.wav", "default", stages, never_force=True)
        r.asr(root, logdir, "clean_input.wav", "default", stages, never_force=True)
    printed = {}

    # timing
    rc, dt, _ = sh(
        [sys.executable, str(UPSTREAM / "evaluation" / "get_timing.py"), "--root_dir", str(root)],
        logdir,
        r.env,
        logdir / "get_timing.log",
        "get_timing",
    )
    stages.setdefault("eval", {})["get_timing"] = dt
    ok &= rc == 0
    print(f"    get_timing: {dt:.1f}s")
    for sid in ids_expected:
        li = read_json(root / sid / "latency_intervals.json")
        if li is None:
            continue
        scored.add(sid)
        stop = [e - s for s, e in li.get("latency_stop_list", [])]
        resp = [e - s for s, e in li.get("latency_resp_list", [])]
        metrics.setdefault("stop_latency", {})[sid] = float(np.mean(stop)) if stop else None
        metrics.setdefault("resp_latency", {})[sid] = float(np.mean(resp)) if resp else None
        metrics.setdefault("n_stop_intervals", {})[sid] = len(stop)
        metrics.setdefault("n_resp_intervals", {})[sid] = len(resp)

    # general before/after (stale cache guard: upstream reuses general_split.json)
    for sid in ids_expected:
        gs = root / sid / "general_split.json"
        oj = root / sid / "output.json"
        if gs.exists() and (r.force or (oj.exists() and gs.stat().st_mtime < oj.stat().st_mtime)):
            gs.unlink()
    okg, text = r.evaluate(root, logdir, "general_before_after", stages)
    ok &= okg
    printed["general_before_after"] = printed_aggregates("general_before_after", text)
    for sid in ids_expected:
        g = read_json(root / sid / "general_split.json")
        if not g:
            continue
        scored.add(sid)
        for side in ("pre", "post", "clean"):
            for k, v in (g.get(side) or {}).items():
                if isinstance(v, (int, float)):
                    metrics.setdefault(f"{side}_{k}", {})[sid] = None if v != v else float(v)
        metrics.setdefault("split_t", {})[sid] = g.get("split_t")

    if r.metrics_mode == "all":
        r.check_judge_key()
        if r.force:
            for sid in ids_expected:
                (root / sid / "content_tag.json").unlink(missing_ok=True)
        okb, text = r.evaluate(root, logdir, "behavior", stages)
        ok &= okb
        printed["behavior"] = printed_aggregates("behavior", text)
        per = read_json(logdir / "per_sample_behavior.json") or {}
        for sid, res in per.items():
            scored.add(sid)
            tags = (res or {}).get("behaviour") if res else None
            for tag in ("C_RESPOND", "C_RESUME", "C_UNCERTAIN_HANDLING", "C_UNKNOWN"):
                metrics.setdefault(f"behavior_{tag}", {})[sid] = (
                    None if tags is None else int(tag in tags)
                )
    return stages, metrics, sorted(scored), printed, ok


# ---------------------------------------------------------------------------------------
def crosscheck(metrics, printed):
    rows = []
    for k, up in printed.items():
        if k in metrics and isinstance(up, float):
            mine = stats(list(metrics[k].values()))["mean"]
            if mine is None and up != up:
                ok = True
            else:
                ok = (mine is not None and abs(mine - up) <= max(1e-4, 1e-6 * abs(up))) or (
                    mine is None and up != up
                )
            rows.append(
                {"metric": k, "per_sample_mean": mine, "upstream_printed": up, "match": bool(ok)}
            )
    return rows


def fmt(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def write_report(run: Path, results: dict, manifest: dict):
    L = [
        f"# FDB evaluation: {results['run_name']}",
        "",
        f"- evaluated at: {results['evaluated_at']}",
        f"- eval metrics mode: `{results['metrics_mode']}`; device: `{results['device']}`",
        f"- judge: {json.dumps(results['judge'])}",
        f"- upstream: Full-Duplex-Bench @ `{results['upstream_commit']}` "
        "+ evals/turn_taking/scoring/patches/fdb.patch",
        "",
        "## agent_resolved",
        "",
        "```json",
        json.dumps(manifest.get("agent_resolved", {}), indent=2),
        "```",
        "",
    ]
    for key, t in results["tasks"].items():
        L += [
            f"## {key}  (upstream task: `{t['upstream_task']}`)",
            "",
            f"samples expected {t['n_expected']}, scored {t['n_scored']}"
            + (
                f", missing {len(t['missing'])}: {t['missing'][:10]}"
                + ("..." if len(t["missing"]) > 10 else "")
                if t["missing"]
                else ""
            ),
            "",
        ]
        for w in t.get("warnings", []):
            L += [f"**WARNING**: {w}", ""]
        if t.get("error"):
            L += [f"**ERROR**: {t['error']}", ""]
        has_ov = t.get("overlap") is not None
        if has_ov:
            n_unknown = sum(o["overlap_valid"] is None for o in t["overlap"].values())
            L += [
                f"valid overlaps: {t['n_valid_overlaps']}/{len(t['overlap'])}"
                + (f" ({n_unknown} unknown: no events.json)" if n_unknown else ""),
                "",
                "| metric | n (all) | mean (all) | median (all) | p90 (all) "
                "| n (valid) | mean (valid) | median (valid) | p90 (valid) |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            for m, s in t["metrics"].items():
                v = s["valid_only"]
                L.append(
                    f"| {m} | {s['n']} | {fmt(s['mean'])} | {fmt(s['median'])} | {fmt(s['p90'])} "
                    f"| {v['n']} | {fmt(v['mean'])} | {fmt(v['median'])} | {fmt(v['p90'])} |"
                )
        else:
            L += ["| metric | n | mean | median | p90 |", "|---|---|---|---|---|"]
            for m, s in t["metrics"].items():
                L.append(
                    f"| {m} | {s['n']} | {fmt(s['mean'])} | {fmt(s['median'])} | {fmt(s['p90'])} |"
                )
        L += [""]
        if has_ov:
            L += [f"- {OVERLAP_WHY}"]
        for m in t["metrics"]:
            d = definition(m)
            if d:
                L.append(f"- `{m}`: {d}")
        L.append("")
        if t.get("system1"):
            L += ["System one:", "", *system1_lines(t["system1"]["aggregate"]), ""]
        if t["crosscheck"]:
            L += [
                "Cross-check against upstream-printed aggregate:",
                "",
                "| metric | per-sample mean | upstream printed | match |",
                "|---|---|---|---|",
            ]
            for c in t["crosscheck"]:
                verdict = "yes" if c["match"] else "NO"
                L.append(
                    f"| {c['metric']} | {fmt(c['per_sample_mean'], 5)} | "
                    f"{fmt(c['upstream_printed'], 5)} | {verdict} |"
                )
            L.append("")
        if t.get("upstream_printed_extra"):
            L += [
                "Upstream-printed (trimmed/ratio) aggregates:",
                "",
                "```json",
                json.dumps(t["upstream_printed_extra"], indent=1),
                "```",
                "",
            ]
        names = list(t["metrics"])
        ids = t["scored_ids"]
        cols = [n for n in names if not n.startswith(("pre_", "post_", "clean_"))] or names[:6]
        if ids and cols:
            lim = 40
            shown = f"first {lim} of {len(ids)}" if len(ids) > lim else "all"
            vcol = ["valid"] if has_ov else []
            L += [
                f"Per-sample values ({shown}; full table in results.json):",
                "",
                "| id | " + " | ".join(vcol + cols) + " |",
                "|---|" + "---|" * len(vcol + cols),
            ]
            for sid in ids[:lim]:
                cells = [fmt(t["metrics"][c]["values"].get(sid)) for c in cols]
                if has_ov:
                    ov = t["overlap"].get(sid, {}).get("overlap_valid")
                    cells.insert(0, "?" if ov is None else ("yes" if ov else "no"))
                L.append(f"| {sid} | " + " | ".join(cells) + " |")
            L.append("")
        L += ["Timing: " + json.dumps(t["timing"]), ""]
    L += ["", *run_cost.report_lines(run_cost.collect(run, manifest), manifest), ""]
    (run / "eval" / "report.md").write_text("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument(
        "--tasks", help="comma list e.g. v1/candor_pause_handling,v1.5/user_interruption"
    )
    ap.add_argument("--force", action="store_true", help="redo ASR and delete cached derived files")
    args = ap.parse_args()

    run = args.run.resolve()
    manifest = read_json(run / "manifest.json")
    if manifest is None:
        sys.exit(f"{run}/manifest.json missing or unreadable")
    if not (UPSTREAM / "evaluation" / "fdb_common.py").exists():
        sys.exit("patched upstream not found; run evals/turn_taking/scoring/setup.sh first")

    by_task: dict[tuple, list] = {}
    for s in manifest.get("samples", []):
        by_task.setdefault((s["version"], s["task"]), []).append(str(s["id"]))
    for vt in list(by_task):
        if not (run / vt[0] / vt[1]).is_dir():
            by_task.pop(vt)
    if args.tasks:
        want = {tuple(x.split("/", 1)) for x in args.tasks.split(",")}
        by_task = {k: v for k, v in by_task.items() if k in want}
    if not by_task:
        sys.exit("no tasks to evaluate (check manifest samples / --tasks)")

    r = Runner(run, manifest, args.force)
    (run / "eval").mkdir(exist_ok=True)
    commit = (HERE / "UPSTREAM_COMMIT").read_text().strip()
    results = {
        "run_name": manifest.get("run_name", run.name),
        "evaluated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "metrics_mode": r.metrics_mode,
        "device": r.device,
        "judge": r.judge_info(),
        "upstream_commit": commit,
        "agent_resolved": manifest.get("agent_resolved"),
        "tasks": {},
    }
    t_all = time.time()
    asr_tot = {"model_load_s": 0.0, "transcribe_s": 0.0, "audio_s": 0.0}

    for (ver, task), ids in sorted(by_task.items()):
        key = f"{ver}/{task}"
        root = run / ver / task
        logdir = run / "eval" / f"{ver}__{task}"
        logdir.mkdir(parents=True, exist_ok=True)
        for f in logdir.glob("*.log"):
            f.unlink()
        print(f"== {key}  ({len(ids)} samples)", flush=True)
        t0 = time.time()
        err = None
        try:
            if ver == "v1" and (ver, task) in V1_TASKS:
                up, asr_task = V1_TASKS[(ver, task)]
                if args.force:
                    for sid in ids:
                        for fn in ("rating.json",):
                            (root / sid / fn).unlink(missing_ok=True)
                stages, metrics, scored, printed, ok = v1_task(
                    r, ver, task, up, asr_task, ids, root, logdir
                )
                printed_extra = {}
            elif ver == "v1.5" and task in V15_TASKS:
                up = "timing+general_before_after" + (
                    "+behavior" if r.metrics_mode == "all" else ""
                )
                stages, metrics, scored, printed, ok = v15_task(r, ver, task, ids, root, logdir)
                printed_extra, printed = printed, {}
            else:
                print(f"   unknown task {key}, skipping")
                continue
            if not ok:
                err = "one or more upstream stages failed; see logs in " + str(logdir)
        except Exception as e:
            err = repr(e)
            stages, metrics, scored, printed, printed_extra, up = {}, {}, [], {}, {}, "?"
            print("   ERROR", err)

        if key == "v1/candor_pause_handling" and err is None:
            metrics.update(pause_metrics(root, ids))
        system1 = system1_task(root, ids) if root.is_dir() else None
        mout = {}
        for m, vals in metrics.items():
            s = stats(list(vals.values()))
            s["values"] = vals
            mout[m] = s
        warns = []
        if up == "user_interruption" and r.metrics_mode == "all" and "score" in mout:
            nnull = sum(
                1
                for sid, v in metrics["score"].items()
                if v is None and metrics["TOR"].get(sid) == 1
            )
            if nnull:
                warns.append(
                    f"{nnull} TOR=1 samples have a null judge score "
                    "(unparseable output or API failure; see logs)"
                )
        asr_stage = stages.get("asr", [])
        for a in asr_stage:
            for k in asr_tot:
                asr_tot[k] += a[k]
        overlap = None
        if ver == "v1.5":
            overlap = v15_overlap(root, ids)
            with_valid_only(mout, overlap)
            unknown = sorted(sid for sid, o in overlap.items() if o["overlap_valid"] is None)
            if unknown:
                warns.append(
                    f"{len(unknown)} samples have no usable events.json/metadata.json "
                    f"(overlap_valid=null, excluded from valid-only): {unknown[:10]}"
                )
        results["tasks"][key] = {
            "upstream_task": up,
            "n_expected": len(ids),
            "n_scored": len(scored),
            "missing": sorted(set(ids) - set(scored)),
            "scored_ids": scored,
            "metrics": mout,
            "crosscheck": crosscheck(metrics, printed),
            "upstream_printed_extra": printed_extra,
            "warnings": warns,
            "error": err,
            "overlap": overlap,
            "system1": system1,
            "n_valid_overlaps": (
                None
                if overlap is None
                else sum(o["overlap_valid"] is True for o in overlap.values())
            ),
            "timing": {
                "total_s": round(time.time() - t0, 1),
                "asr": [
                    {k: (round(v, 2) if isinstance(v, float) else v) for k, v in a.items()}
                    for a in asr_stage
                ],
                "eval_s": {k: round(v, 1) for k, v in stages.get("eval", {}).items()},
            },
        }
        dead = [m for m, s in mout.items() if s["n"] == 0 and m != "score"]
        if dead:
            warns.append(
                "metrics with no valid values (upstream swallows errors as NaN; "
                f"check logs in {logdir}): {dead}"
            )
        results["tasks"][key]["warnings"] = warns
        for w in warns:
            print("   WARNING:", w)
        for m in ("TOR", "latency", "score", "JSD", "stop_latency", "resp_latency"):
            if m in mout:
                print(f"   {m}: n={mout[m]['n']} mean={fmt(mout[m]['mean'], 4)}")
        for c in results["tasks"][key]["crosscheck"]:
            verdict = "OK" if c["match"] else "MISMATCH"
            print(
                f"   crosscheck {c['metric']}: per-sample {fmt(c['per_sample_mean'], 5)} "
                f"vs upstream {fmt(c['upstream_printed'], 5)} -> {verdict}"
            )

    results["timing"] = {
        "total_s": round(time.time() - t_all, 1),
        "asr": {k: round(v, 2) for k, v in asr_tot.items()},
    }
    if asr_tot["audio_s"]:
        results["timing"]["asr_s_per_audio_s"] = round(
            asr_tot["transcribe_s"] / asr_tot["audio_s"], 3
        )
    prev = read_json(run / "eval" / "results.json")
    if args.tasks and isinstance(prev, dict):  # partial re-run: keep the other tasks' results
        kept = {k: v for k, v in prev.get("tasks", {}).items() if k not in results["tasks"]}
        results["tasks"] = {**kept, **results["tasks"]}
    (run / "eval" / "results.json").write_text(json.dumps(results, indent=2))
    write_report(run, results, manifest)
    print(
        f"\ntotal {results['timing']['total_s']}s; ASR: {results['timing'].get('asr')}"
        f" ({results['timing'].get('asr_s_per_audio_s', 'n/a')} s per audio-s)"
    )
    print(f"wrote {run}/eval/results.json and report.md")
    return 1 if any(t["error"] for t in results["tasks"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
