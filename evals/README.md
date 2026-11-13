# Evals

An eval suite here is a set of automated runs against the real model that checks one kind of
behaviour. Unit tests cover what code does; evals cover what depends on what the model says.
Every suite **spends API money** (Sofia, plus whatever simulator, summary or judge the suite
uses), so none of them is part of `make check`.

## Suites

| Suite                                  | Status | What it covers                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| -------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`e2e`](e2e/README.md)                 | done   | Multi-call screening conversations through the real pipeline over the text channel, with a simulated candidate: follow-up memory, closed candidates, language, and knowledge-base questions (search called, Spanish query, no answer from memory, holding line, hand-off to a recruiter; slow and down knowledge bases). Hard checks on database state; an LLM judge that only reports. Does **not** cover audio, STT, TTS, VAD, latency or the phone channel.            |
| [`turn_taking`](turn_taking/README.md) | done   | Turn-taking and interruption handling of the voice pipeline (pauses, backchannels, interruptions, side talk) on a config-selected [Full-Duplex-Bench](https://github.com/DanielLin94144/Full-Duplex-Bench) subset, with paired A/B and held-out runs. Audio, VAD, STT and TTS are in the loop; English only; a generic bench agent, not the HR prompt. Real-time, spends STT/LLM/TTS (and Cloudflare, judge) money.                                                       |
| `kb`                                   | done   | Retrieval quality of the knowledge base: golden questions (English and Spanish, speech-recognition noise, code-switching, out-of-scope) against an in-memory Qdrant index. Recall@k, MRR and no-match precision/recall for hybrid, dense-only and BM25-only search, with Spanish queries and with raw questions; sweeps `KB_MIN_SCORE`. Calls only the embedding API (OpenAI by default, or Voyage; `--provider local` needs no key); vectors are cached on disk. No LLM. |

Run a suite with `make eval-<suite>`, for example `make eval-e2e`. `turn_taking` also has
`eval-turn-taking-setup`, `-fetch-data`, `-score` and `-compare` because scoring runs in its own
environment.

## Shared code

`common/` holds what more than one suite uses: `language.py` (stopword language detection)
and `usage.py` (token accounting and pricing: `Usage`, `add_usage`, `add_agent_usage`, `Price`, `PRICES`,
`cost`). Code
moves there when a second suite needs it, not before; `common/` must not import from a suite.
The likely next candidate is the conversation runner in `e2e/harness.py`.

## Results

`evals/results/<suite>/<timestamp>/` (git-ignored): `report.md`, `runs.jsonl` and whatever
else the suite writes. The runner prints the path of `report.md` at the end.

`turn_taking` deviates in two ways, on purpose (details in its README): its raw runs sit in
`evals/results/turn_taking/<run_name>/` (named by run, not timestamp, because runs are
resumable and paired runs refer to each other by name), and its per-run reports are **tracked**
in `evals/turn_taking/reports/` because they are the evidence for a design decision.

## Adding a suite

- Its own folder `evals/<suite>/` with `run.py`, started as `python -m evals.<suite>.run`, and
  a `make eval-<suite>` target.
- Results under `evals/results/<suite>/<timestamp>/`, with a `report.md` that shows cost per
  component using `common/usage.py`.
- Runs where the harness could not create the situation are reported as invalid, separately
  from failures.
