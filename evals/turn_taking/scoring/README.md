# evals/turn_taking/scoring: Full-Duplex-Bench scoring

Stage 2 of the FDB integration. Scores a stage-1 run directory (`evals/results/turn_taking/<run>/`) with the
upstream FDB evaluation code (slightly patched) and compares two runs.

Upstream: https://github.com/DanielLin94144/Full-Duplex-Bench, pinned in `UPSTREAM_COMMIT`
(`3e799c45a045256f47d5f1c9cda90157e2d2ec9e`).

**License caveat.** The upstream repo is CC BY-NC 4.0 (non-commercial). It is cloned at setup time into
`evals/turn_taking/scoring/third_party/` (gitignored) and is **not vendored**; only our own patch (`patches/fdb.patch`) and
scripts are in git. Datasets: Candor/ICC subsets CC BY-NC 4.0, synthetic and v1.5 data MIT. Do not use
these results/data commercially. The eval env is a separate uv project (`evals/turn_taking/scoring/pyproject.toml`,
Python 3.11), independent of the agent env.

## Setup (once, idempotent)

    bash evals/turn_taking/scoring/setup.sh

Clones upstream at the pinned SHA, applies the patch, `uv sync`s the eval env, and prefetches
Parakeet-TDT-0.6B-v2 (~2.4 GB) and UTMOSv2 weights (~0.8 GB; upstream shells out to `wget`, which is not on a
stock Mac, so we download them ourselves in `prefetch_models.py`). Re-running is a no-op.

## Fetch data

    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/fetch_data.py [--force] [--keep-zips] [--tasks v1/icc_backchannel,...]

Downloads ~705 MB from Google Drive into `evals/turn_taking/data/fdb/<v1|v1.5>/<task>/<id>/` and prints counts vs the
upstream README. See `evals/turn_taking/data/README.md` for the mapping and deviations (v1.5 `user_backchannel` has 98, not 99).

## Run

    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/run_eval.py --run evals/results/turn_taking/<run_name> [--tasks v1/candor_pause_handling,...] [--force]

Reads `manifest.json` (`config.eval.{device,metrics,judge}`); which tasks to score comes from `samples`.

| run task | upstream | ASR | metrics |
|---|---|---|---|
| v1 candor/synthetic_pause_handling | `pause_handling` | output.wav | TOR (lower better) |
| v1 candor_turn_taking | `smooth_turn_taking` | output.wav | TOR, latency |
| v1 icc_backchannel | `backchannel` | output.wav | TOR, JSD, freq |
| v1 synthetic_user_interruption | `user_interruption` | output.wav cropped after the interruption | TOR, latency, judge score (metrics=all) |
| v1.5 (4 tasks) | `get_timing.py` + `general_before_after` (+ `behavior` if metrics=all) | output.wav, clean_output.wav (input/clean_input only if their json is missing; the dataset ships them) | stop/resp latency, UTMOSv2/wpm/pitch/intensity pre/post/clean, C-axis behaviour labels |

- `eval.metrics == "local"`: no LLM judge, no API key (`FDB_SKIP_JUDGE=1`); user_interruption reports TOR/latency only and v1.5 `behavior` is skipped.
- `eval.metrics == "all"`: judges run through one helper (`fdb_common.judge_chat`) selected by `FDB_JUDGE_PROVIDER`
  (`openai`|`anthropic`) and `FDB_JUDGE_MODEL`, which run_eval sets from the manifest. Upstream prompts and parsing are unchanged;
  with the env vars unset the behaviour is upstream (OpenAI gpt-4-turbo for user_interruption, gpt-4o-2024-08-06 for behavior).
  Needs `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in the environment (run_eval does not read .env files).
  Anthropic call: messages API, model passed through, no temperature override (upstream passes none either), max_tokens 2048.
- ASR is skipped when the json exists unless `--force`. `--force` also clears cached derived files.
- Output: `<run>/eval/results.json` (per task: n, per-sample values, mean/median/p90/std, upstream-printed aggregate cross-check, timings),
  `<run>/eval/report.md`, and per-stage logs in `<run>/eval/<version>__<task>/`.
- Timing: each stage prints wall time; ASR prints seconds per audio second.

Gotchas: ASR writes `output.json` etc. into the run's sample folders (next to the symlinked sources); samples with no
`output.wav` are reported as `missing`, not silently dropped. UTMOSv2 failures are swallowed by upstream as NaN; run_eval warns when a
metric has no valid values.

## Compare

    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/compare.py --a evals/results/turn_taking/<baseline> --b evals/results/turn_taking/<variant> [--out file.md]

Pairs by (version, task, id). Per metric: mean A/B, diff (B - A), paired bootstrap 95% CI, McNemar exact (binary) or Wilcoxon
(continuous). Latency pairs only include samples where both runs took the turn. Warns if sample sets or judge config differ.
Writes `<b>/eval/compare.md`.

## Cost / time (Apple Silicon, CPU)

- `report.md` has a Cost section (LLM, TTS, STT, classifier, judge; see `evals/turn_taking/README.md`).
  Judge tokens are logged by the patched `judge_chat()` into `<run>/eval/judge_usage.jsonl`
  (`FDB_JUDGE_USAGE_LOG`, appended across invocations, so a resumed scoring keeps earlier spend); a `--force` re-score with the judge on therefore adds to it, and the total then counts both passes, which is the real spend).

- ASR: Parakeet-TDT 0.6B on CPU ran at about 0.04-0.08 s per audio second (12-25x real time); first model load
  is 2-3 s warm (137 s the first time, downloading). Full v1 (~214 min audio) is roughly 10-15 min; v1.5 (~113 min x 2 for output +
  clean_output) similar. Each ASR invocation reloads the model (~3 s).
- UTMOSv2 on CPU: a few seconds per sample (3 segments each).
- Judge calls: v1 user_interruption <= 200 calls/run (only TOR=1 samples; ~1k tokens each). v1.5 behavior <= 498 calls/run
  (each ~3-6k input tokens: instruction + 4 transcripts). Calls retry up to 3 times, then record null.

## Patch list (`patches/fdb.patch`, regenerate with `regen_patch.sh`)

1. `asr.py`: device cuda > cpu instead of `.cuda()` (no MPS); `--skip_existing`; prints model-load/transcribe timing.
2. `eval_backchannel.py`: TOR reset per sample (leaked when output.json missing / no VAD segments); `icc_gt_distribution.json` resolved
   relative to the file, not the cwd; sorted iteration; missing output.wav skipped (reported by run_eval).
3. `eval_user_interruption.py`: score appended once per sample (was twice); judge retries capped at 3, then null; latency recorded
   independent of the judge; division-by-zero guards; missing output.json skipped.
4. `eval_behavior.py`: retry loop capped at 3 (was infinite), null on failure; instruction path relative to the file.
5. Judge abstraction `fdb_common.py` (new): `judge_chat`, `FDB_JUDGE_PROVIDER`/`FDB_JUDGE_MODEL`, `FDB_SKIP_JUDGE`; `evaluate.py` only creates an
   OpenAI client when OpenAI is the judge.
6. Per-sample dumps: pause_handling, smooth_turn_taking, backchannel, user_interruption and behavior write `per_sample_<task>.json` to
   `$FDB_PER_SAMPLE_DIR` (default: root_dir); smooth_turn_taking pairs input/output per folder (was two independently-built lists).
7. `eval_general_before_after.py`: UTMOSv2 on cuda > cpu (`create_model` and `predict`, which defaults to `cuda:0`); SQUIM not loaded when unused;
   Silero from the pip package instead of `torch.hub`.
8. `get_timing.py`: Silero from the pip package instead of `torch.hub`.
9. pause_handling / smooth_turn_taking ignore stray files in root_dir.

Known upstream quirks left unchanged: in `eval_backchannel` TOR is overwritten by each later short VAD segment (a segment judged
TOR=1 can be reset by a following one; only `duration > 3 s` breaks out); TOR/latency thresholds are the upstream ones (>3 words or >=1 s).
`significance_test.py` is not wired in (use `compare.py`).

## Self-test

Copy the three upstream `evaluation/example_data/*/1` samples into `evals/results/turn_taking/_selftest/v1/<task>/1/` with a minimal manifest,
delete their `output.json`, and run `run_eval.py`; TOR/latency match the unpatched upstream `evaluate.py` on the same ASR output.

## v1.5 overlap validity and the compare guards

For every v1.5 sample `run_eval.py` reads `events.json` (input session) and checks that the bot was speaking at
`metadata.json` `timestamps[0]` (0.2 s tolerance before it; an interval still open at the end runs to the end of
`output.wav`). Result per sample: `overlap_valid` (null if events are missing, with a warning),
`bot_speaking_secs_before_overlap`, `bot_started_at`. Reports and `results.json` show every v1.5 metric over all
samples and over valid-only samples. No VAD cross-check on `output.wav` (it would need another model pass).
`compare.py` pairs v1.5 metrics only on samples valid in both runs and prints the dropped count; it warns
prominently if `agent_resolved.bench_agent_fingerprint` differs or is missing, and if both runs use the same variant.
Offline test (synthetic fixtures, no inference): `uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/selftest_overlap.py`.

## Event-derived diagnostics

From each sample's `events.json`: `candor_pause_handling` gets `premature_turn_end` (a `user_turn.stopped` in
[pause start - 0.3, pause end + 0.5]) and `premature_llm_start` (an `llm.text` after that stop, up to pause end + 2.5);
every task gets a "System one" block when `system1.*` events exist (judgment count, outcome classes ok/error/timeout/
cancelled/stale, p50/p90 latency over ok calls, hedged share, action counts). `compare.py` pairs the new metrics and adds a
System one table. A partial `run_eval --tasks ...` keeps the other tasks' previous results in `results.json`.
Test: `uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/selftest_diag.py`.
