# Full-Duplex-Bench for the HR screener

Measures turn-taking and interruption handling of the voice pipeline with
[Full-Duplex-Bench](https://github.com/DanielLin94144/Full-Duplex-Bench) v1 / v1.5 subsets. Each
sample is streamed in real time through the production voice pipeline over a telephony profile.
The agent is fixed (`evals/turn_taking/agent.py`: generic prompt, mock tools), so runs measure the
turn-taking design, not the prompt. Comparisons are paired A/B on the same samples, plus held-out
runs. Every run, number and decision is in [reports/SUMMARY.md](reports/SUMMARY.md).

## Current state

Design v3 is production (`hr_screener.turn_taking.design.SYSTEM_ONE_DESIGN`). The historical
designs v1, v2, v3 and `production` live in `evals/turn_taking/designs.py` and are selected with
`agent.design`. The old baseline (Silero VAD + Smart Turn) is no longer in the app but remains as
the `baseline` variant. The recorded results predate the promotion. `configs/production.yaml` is
prepared and has not been run yet.

## Layout

| Path | What | In git |
|---|---|---|
| `evals/turn_taking/*.py` | inference harness (`python -m evals.turn_taking.run`) | yes |
| `evals/turn_taking/configs/` | one YAML per run | yes |
| `evals/turn_taking/scoring/` | stage 2: own uv project, patched upstream scorer | yes (upstream clone in `scoring/third_party/` is not) |
| `evals/turn_taking/reports/` | `report.md` and comparisons per run, `SUMMARY.md` | yes (`results.json` and `manifest.json` are not) |
| `evals/turn_taking/data/` | Full-Duplex-Bench data | no |
| `evals/results/turn_taking/<run_name>/` | raw runs: audio, `events.json`, `bot.log`, `eval/` | no |

`reports/` is tracked because it is the evidence for the turn-taking design decision. The raw runs
behind it are too large and contain the licensed audio. Run folders are named by `run_name`, not
by timestamp, so runs are resumable and paired runs can refer to another run's manifest.

## Two stages, two environments

| Stage | Env | What it does |
|---|---|---|
| 1. inference: `evals/turn_taking/` | agent env (py3.12) | streams each `input.wav` through the pipeline, records `output.wav`. Uses cloud STT, LLM and TTS in real time. |
| 2. scoring: `evals/turn_taking/scoring/` | own uv project (py3.11, torch + NeMo) | Parakeet ASR on CPU plus the patched upstream scorer. Local. LLM judge only if `metrics: all`. |

The agent runs as configured by the `.env` named in `env_file` (relative to the repo root). Language
is forced to `en` and `LLM_PROVIDER` must be `anthropic`.

## Workflow

```bash
make eval-turn-taking-setup          # once: clone upstream at pinned SHA + patch + eval env
make eval-turn-taking-fetch-data     # once: ~705 MB download

# 1. pick the subset in the config (selection.tasks: {n: N} | {ids: [...]} | {all: true})
make eval-turn-taking ARGS=--dry-run # resolved settings and sample counts; no API calls
make eval-turn-taking                # CONFIG=evals/turn_taking/configs/baseline.yaml by default; resumable

# 2. score it
make eval-turn-taking-score RUN=baseline-env-telephony

# 3. paired comparison on the same samples
#    new config with variant: <name>, a new run_name,
#    selection.from_manifest: evals/results/turn_taking/baseline-env-telephony/manifest.json
make eval-turn-taking-compare A=baseline-env-telephony B=<new run_name>
```

Runs land in `evals/results/turn_taking/<run_name>/<version>/<task>/<id>/`: `output.wav`,
`events.json` (VAD, turn, interruption, transcript and LLM events; use it to debug one sample)
and `bot.log`. Scores land in `<run_name>/eval/report.md` and `results.json`. To publish a run,
copy `report.md` (and any comparison) into `reports/`; `results.json` and `manifest.json` stay with the raw run.

## Design parameters

The `system_one` variants use one parameter dict, `SYSTEM_ONE_DESIGN` in
`src/hr_screener/turn_taking/design.py`. Configs start from a design (`agent.design`) and may
override single values under `agent.variant_params`. The reason for each v2 and v3 value is a
comment next to it in `evals/turn_taking/designs.py`. The main parameters, with v1 values:

| Param | v1 | Effect |
|---|---|---|
| `complete_start` / `complete_floor` / `relax_secs` | 0.72 / 0.55 / 3.0 | `turn_complete` threshold, relaxing with silence |
| `quiet_confirm_secs` | 0.3 | quiet required before a turn may end |
| `fallback_secs` / `holding_fallback_secs` | 5.0 / 12.0 | end the turn after this silence regardless of scores |
| `addressed_threshold` | 0.5 | below this the speech is side talk |
| `taking_threshold` | 0.5 | `taking_floor` needed to interrupt the agent |

## Cost

`eval/report.md` ends with a Cost section, one row per component: LLM tokens, TTS characters, STT
audio seconds, classifier requests and the Claude judge. AssemblyAI and Cloudflare prices are not
stored in this repo, so those rows show the quantity and "price unknown". Add a price to
`UNIT_PRICES` in `evals/turn_taking/cost.py` to include it in the total.

## Adding a variant

Register a `Variant` in `evals/turn_taking/variants.py` (`VARIANTS`). Its builder gets
`(transport, settings, agent, telephony)` and returns a `ConversationPipeline`. Select it with
`agent.variant` in a new config. Variants share the fixed bench agent. Extra prompt text, if
needed, goes in `Variant.extra_instructions`, which is recorded in the manifest.

## Known caveats

- Not a production replica: generic agent, no greeting, mock tools.
- A cascaded STT -> LLM -> TTS design cannot backchannel, so expect backchannel JSD = 1 and freq = 0.
- Claude-judged scores are not comparable to published (GPT-judged) numbers. They are valid for A/B
  only when the judge is fixed.
- Output is truncated to the input length, so a reply that starts after the input ends does not
  count (same rule as upstream).
- Upstream code and the v1 Candor/ICC data are CC BY-NC 4.0, which is why the clone is gitignored,
  not vendored. See `evals/turn_taking/scoring/README.md` for the patch list.
