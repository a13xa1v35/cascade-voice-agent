# Evals

Scenario conversations between the real Sofia and a simulated candidate, with deterministic
checks on what ends up in the database. The point is the cross-call memory (a dropped call
resumes as a follow-up) and language behaviour, which unit tests cannot show because they
depend on what the model says.

## What it measures

Each run plays one scenario in one language, against a fresh SQLite file and Redis db (never
`DATABASE_URL` or `REDIS_URL`), through the real pipeline over text (`textcall.TextCall`): the
same prompt, tools, hang-up and `_finalize`.

- A Haiku-simulated candidate answers from a persona card (`personas/*.toml`). The harness, not
  the simulator, decides when the candidate hangs up (`drops.py`).
- Hard checks (`checks.py`, pure functions of the run record) test the database state. Their
  blind spots are documented in each check's docstring in `checks.py`.
- An LLM judge (Sonnet) answers a rubric of yes/no questions with a quoted turn. It only
  reports and never changes pass/fail.

The hard checks cover the call chain (modes, statuses, outcomes, end reasons, attempts),
`responsive`, booking iff expected, saved facts equal to the persona card, `tool_order_problems`,
no re-saved fact, language drift (`evals/common/language.py`) and `no_repeated_question` (lesson
17 in the root README). Per group:

- Knowledge scenarios: `kb_searched`, `kb_search_outcome`, `kb_chunks_retrieved`,
  `kb_query_spanish`, `kb_no_answer_from_memory`, `kb_no_doubled_holding_line`,
  `kb_question_referred`, `kb_screening_resumes`, `kb_end_call_after_pending`.
- `n1`: `language_switch`. `m1`, `m2`: `frustration_noted`, `no_frustration_note`,
  `no_resave_after_note`, `note_not_spoken`.

### Validity

A run where the harness could not create the situation is invalid. It is reported separately
and never counted as a Sofia pass or failure: `trigger_missed` (a drop condition never fired),
`did_not_finish` (30 turns), `simulator_drift` (the candidate broke its persona) and
`provider_quota` (the provider refused Sofia's request with HTTP 429; wait, then re-run).

Silence is a Sofia failure, not an invalid run: no reply within `reply_timeout_secs` (120 s), or
a call that ended with end reason `llm_error`, fails `responsive`.

## Run

```bash
make eval-e2e                                  # all scenarios, es, 1 run
make eval-e2e SCENARIOS=c,l2 LANGS=es,en RUNS=3 NO_JUDGE=1
make eval-e2e SCENARIOS=k1,k2,k3,k4,k5,k6,k7,k8 LANGS=es,en CONCURRENCY=1   # knowledge base
LLM_PROVIDER=openai make eval-e2e SCENARIOS=a,b LANGS=es RUNS=1             # Sofia on OpenAI
```

This spends API money: Sofia, the simulator (`claude-haiku-5-5`), the post-call summary and the
judge (`claude-sonnet-5-5`). It needs `ANTHROPIC_API_KEY` in `.env` (the simulator and judge are
Claude whatever Sofia runs on), `OPENAI_API_KEY` when Sofia runs on OpenAI, and a Redis
(`make redis`). `m1` and `m2` also need `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`, and
the knowledge scenarios need an embedding key or `--kb-provider local`.

Output goes to `evals/results/e2e/<timestamp>/`: `report.md` (pass rates, failing checks,
invalid runs, judge, token usage and cost, time to first byte) and `runs.jsonl` (one conversation
per line). On a key with low rate limits, set `LLM_MAX_RPM` / `LLM_MAX_TPM` a bit under them.

## Scenarios

| id | what it proves |
|---|---|
| `a` | call dropped before any fact: the follow-up starts from scratch |
| `b` | dropped after 4 facts: the follow-up asks only what is missing |
| `c` | dropped after availability, before the teaching format |
| `c2` | dropped after subjects, before levels |
| `d` | dropped right after `record_experience` |
| `e` | busy candidate asks for a call-back |
| `f` | all facts, then a changed start date: qualified becomes not qualified and the booking goes |
| `g` | not authorized to work: rejected |
| `h` | supersede (a new call starts while one is live) after 3 facts |
| `i` | dropped after slots were offered |
| `j` | two drops in a row |
| `k` | stale start date, set up from the database |
| `l1` | closed and booked: the candidate calls back |
| `l2` | closed and rejected: no reason is revealed (judge) |
| `l3` | closed, booked, session already held: she neither calls it upcoming nor says if they attended (judge) |
| `k1` | real KB, pay question: one search, the answer, then screening resumes and books |
| `k2` | real KB, IVA question: the answer carries the `as_of` date and the *gestor* line (judge) |
| `k3` | real KB, two questions in a row: two searches, one at a time |
| `k4` | slow KB: the candidate keeps talking, the result arrives late, screening continues |
| `k5` | KB down: Sofia says a colleague will reply, refers the question once, screening carries on |
| `k6` | real KB, out of scope: `no_match`, nothing invented, referred to a recruiter |
| `k7` | booked candidate calls back with a question: answered, booking untouched |
| `k8` | slow KB, goodbye while the search runs: `end_call` is refused with `search_pending`, the answer is given, then the call ends |
| `m1` | `impatient` persona: at least one frustration note, no fact re-saved after it, note not spoken |
| `m2` | `curt_calm` persona: no frustration note (false-alarm control), the call books |
| `n1` | language switch: `switch_language` called once, Sofia's turns before the switch in the start language and after it in the new one, the call still books |

Definitions are in `scenarios.py`. The scenarios came from three sources: the branches of the
follow-up state (what is on file when the next call starts), past bugs (root README, "Lessons
from test calls") and business harm (booking someone who does not qualify, double-booking,
telling a rejected candidate why).

The knowledge bases (`kb.py`):

- real: the app's own `QdrantKnowledgeBase` over `knowledge/` in an in-memory Qdrant, with
  embeddings cached on disk (shared with `make eval-kb`).
- slow: the real index behind a wrapper that sleeps 10 s before it searches.
- down: every search raises `KnowledgeUnavailable`.

### Haiku vs gpt-4.1-mini

The suite doubles as a model benchmark: the same scenarios with only Sofia's model changed
(simulated candidate, summary and judge stay on Claude). Both arms ran all 24 scenarios (before
`c2` was added) in English and Spanish, 2 runs each (96 conversations per model), on the same
code and at the same time (2026-11-12, concurrency 4, prompt caching on for both):

| | `claude-haiku-5-5` | `gpt-4.1-mini` |
|---|---|---|
| Hard checks, screening scenarios (a-l3, m1, m2) | **55 / 56** | 48 / 53 |
| Hard checks, knowledge-base scenarios (k1-k8) | 9 / 31 | **14 / 30** |
| Conversations that saved teaching levels the candidate never gave | **0** | 5 (all English) |
| Invalid conversations (not counted) | 9 | 13 |
| Sofia LLM request errors | 0 | 0 |
| LLM time to first byte, p50 / p95, en | **0.57 / 0.84 s** | 0.69 / 0.95 s |
| LLM time to first byte, p50 / p95, es | 0.69 / 1.84 s | **0.67 / 0.97 s** |
| Sofia's LLM cost per conversation (list prices, cache reads at the cache rate) | **$0.0018** | $0.0114 |
| Sofia's output tokens, whole run | 112k | **50k** |
| Judge: narrated tools or saving | 38 / 87 | **15 / 83** |
| Judge: re-asked a question | **14 / 87** | 20 / 83 |
| Judge: re-asked the interest check | **1** | 5 |
| Judge: recap did not match the saved facts | **4** | 9 |
| Judge: knowledge answer not faithful to the documents | **5 / 23** | 9 / 28 |
| Judge: knowledge answer longer than two sentences | 15 / 23 | **9 / 27** |

Where they failed:

- gpt-4.1-mini, screening: in `h`, `j`, `k1` and `k5` it never asked about levels and then saved
  invented ones with the subjects. The benchmark predates lesson 19 in the root README, which
  splits the tool into `record_subjects` and `record_levels` (re-run below).
- Haiku, screening: one `f` run in Spanish missed the start-date correction and booked a
  candidate who no longer qualified (the recurring weak spot of lesson 18 in the root README).
- Knowledge base, both: `k6` found content and was never referred, and `k8` never searched, in
  almost every run. Haiku also doubled the holding line (8 runs against 1).
- Invalid runs are almost all the simulated candidate thinking aloud in Spanish
  (`simulator_drift`), the same on both arms.

### After splitting `record_subjects` (lesson 19 in the root README)

The scenarios that invented levels or depend on where a call drops (`b,c,c2,d,f,h,j,k1,k5,m1`)
were re-run on both models after the split, same day, 2 runs each in en + es (40 conversations
per model):

| | `claude-haiku-5-5` | `gpt-4.1-mini` |
|---|---|---|
| Hard checks, valid conversations | 31 / 36 | 31 / 35 |
| Conversations that saved levels the candidate never gave | 0 | **0** (was 5) |
| LLM time to first byte, p95, en / es | 0.93 / 0.77 s | 0.96 / 0.98 s |
| Sofia's LLM cost per conversation | **$0.0021** | $0.0136 |
| Judge: narrated tools or saving | 18 / 36 | **5 / 35** |
| Judge: re-asked a question | **4 / 36** | 10 / 35 |

The split removed the invented levels, and the pass rates are now level. What is left:

- Haiku: `f` in Spanish missed the start-date correction in both runs and kept the booking
  (lesson 18 in the root README, still open). `k5` doubled the holding line twice.
- gpt-4.1-mini: one `f` in English also kept the booking; in `k5` it ended the call as
  `not_interested`.

Decision: Sofia stays on Haiku, on cost. With the tool split, neither model is clearly more
reliable at the screening: both made an outcome error in `f` and a wrong record or tool order
here and there, at rates these runs cannot separate. Haiku's LLM cost per conversation is about a
sixth of gpt-4.1-mini's, and latency is comparable. gpt-4.1-mini's real advantage is that it
narrates far less (5 of 35 against 18 of 36), so Haiku's narration (lesson 10 in the root README)
is the thing to fix next. Re-open the choice if it cannot be fixed in the prompt.

Limitations of this comparison:

- Two runs per scenario and language. The screening gap (1 failure against 5, Fisher exact
  p ≈ 0.11) and the knowledge-base gap (p ≈ 0.19) are not significant. Only the narration gap is
  (p < 0.001), and it held in the re-run.
- The prompt and tool descriptions were tuned against Haiku; none were changed for gpt-4.1-mini.
- Text channel only. The arms ran at the same time but the load was not symmetric.
- The judge is uncalibrated, costs are list prices (Anthropic cache writes are not priced).

## What text mode does not cover

Turn-taking and VAD, barge-in, the hang-up grace window, STT errors, TTS, latency, audio-lost
handling and the phone channel. It tests what Sofia decides and saves, not how a conversation
feels. For `n1` it checks the model and the tool, not that the voice changes.

## Limits and caveats

- The judge is not calibrated, by decision. Read it as a pointer to turns worth reading, not as
  a score.
- The language check only sees the wrong language. When Sofia speaks her own reasoning in the
  call language, the stopword heuristic cannot tell it from a normal turn; only the judge or a
  transcript read finds it.
- The simulator is an LLM and can drift or invent a fact; every transcript is in `runs.jsonl`.
- One conversation is a sample of a stochastic system, and a few runs cannot separate small
  rates: 2 failures in 42 against 0 in 42 is within noise (telling 5% from 0% takes about 100
  conversations per arm). Use runs to find failure modes, read the failing transcripts, and only
  compare arms when the gap is large.
