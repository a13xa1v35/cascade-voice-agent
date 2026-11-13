# Turn-taking on Full-Duplex-Bench: from VAD to a system-one design

How Sofia's turn-taking design was chosen: three benchmark iterations, then manual calls. Design
v3, refined from those calls, is the one in production
(`hr_screener.turn_taking.design.SYSTEM_ONE_DESIGN`); it has not been benchmarked yet
(`configs/production.yaml` is ready). Wherever a table says "baseline" it means the production
design at the time of the runs.

Setup for every run: 60 samples, 10 per task, the same samples for every design
(`selection.from_manifest`); telephony profile (8 kHz, mu-law); AssemblyAI STT and TTS;
`claude-haiku-5-5` with a fixed bench agent; v1.5 behaviour labels judged by `claude-sonnet-5-5`.
Significance is paired (McNemar or Wilcoxon), n = 7-10 per task, from the `compare_*.md` files
next to this one.

| Design           | What decides end of turn                                                     | What decides barge-in                                          |
| ---------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `baseline`       | Silero VAD + Smart Turn v3                                                   | any VAD onset over 0.2 s                                       |
| `system_one_eot` | Smart Turn **and** the Clef flash model must both agree                      | unchanged: any VAD onset                                       |
| `system_one`     | Clef flash answers four yes/no questions about the transcript, plus silence | Clef `taking_floor` and `addressed_to_agent`; VAD alone never |

## Iteration 1: baseline vs. two system-one variants

| Measure                                               | baseline | system_one_eot | system_one |
| ----------------------------------------------------- | -------- | -------------- | ---------- |
| Pause: turn ended inside the pause (lower is better)  | 4/10     | 2/10           | 1/10       |
| Turn-taking: responded (higher is better)             | 8/10     | 8/10           | 1/10       |
| Turn-taking: latency to first word                    | 2.5 s    | 3.6 s          | n/a        |
| Interruption: judge says responded                    | 62%      | 67%            | 11%        |
| Backchannel: talked through                           | 51%      | 51%            | 100%       |
| Background speech: Sofia's speech vs. without it      | 394%     | 299%           | 97%        |
| Side talk: Sofia's speech vs. without it              | 382%     | 343%           | 101%       |

"Speech vs. without it" compares Sofia's total speech with the same sample without the overlap:
394% means she answered the chatter; 100% means she behaved as if it never happened.

- **The baseline has one signal: is there a voice.** It stops in about 0.4 s for anything, then
  answers background chatter and side talk as if they were requests.
- **`system_one_eot` is a small end-of-turn gain at a latency cost.** The model can only veto,
  never end a turn sooner, so turn-taking got about 0.9 s slower, and barge-in is unchanged.
- **`system_one` fixes the baseline's worst problems and creates two of its own.** It talks
  through backchannels, background speech and side talk. But its 1/10 on pauses came mostly from
  dropping the user's speech as side talk (26 of 44 drops happened mid-sentence), cold-start
  turns with no prior Sofia message were dropped or never judged complete (turn-taking 1/10,
  p = 0.016), and polite interruptions ("By the way…") rarely crossed the threshold.
- The model's latency was bimodal (about 30% of calls took 1.5-4.3 s). A duplicate request after
  0.45 s brought it to p50 about 290 ms; after that, question framing and thresholds were the
  limit, not latency.

## Iteration 2: system-one v2 (same 60 samples)

Question set v2: the assistant is the default listener, statements can be complete, polite topic
switches count as interruptions, and a new `new_request` question. Side talk is no longer dropped
mid-sentence and needs 2 confirmations. Thresholds were chosen from v1's failures and an offline
replay (`system-one-v2-replay.md`) on these same samples, so the numbers are optimistic until
held out.

| Measure                                          | baseline   | v1        | v2        |
| ------------------------------------------------ | ---------- | --------- | --------- |
| Pause: turn ended inside the pause               | 4/10       | 1/10      | 1/10      |
| Turn-taking: responded                           | 8/10       | 1/10      | 8/10      |
| Turn-taking: latency (mean)                      | 2.5 s      | n/a       | 2.1 s     |
| Interruption: judge says responded               | 62%        | 11%       | 60%       |
| Interruption: Sofia kept talking over it (mean)  | 0.39 s     | 2.53 s    | 1.56 s    |
| Backchannel: talked through                      | 51%        | 100%      | 100%      |
| Background speech: judge says responded          | 80%        | 14%       | 33%       |
| Side talk: judge says responded                  | 70%        | 0%        | 0%        |

v2 keeps v1's wins and fixes its failures: turn-taking is back to 8/10 and faster, real
interruptions are answered as often as by the baseline, and no speech is dropped mid-sentence.
The cost is that Sofia keeps talking about 1.2 s longer on a real interruption (p = 0.008): the
words have to arrive before the model can judge them. Background speech stays the hard case,
because some lines ("I'm starving.") are plausible requests as text.

## Held-out confirmation: baseline vs. v2 on 60 fresh samples

New samples (seed 1, no overlap with the tuning set); v2 unchanged.

| Measure                                     | Tuning set: baseline → v2 | Held-out: baseline → v2 | Held-out p |
| ------------------------------------------- | ------------------------- | ----------------------- | ---------- |
| Side talk: judge says responded             | 70% → 0%                  | 90% → 20%               | 0.016      |
| Background speech: judge says responded     | 80% → 33%                 | 100% → 30%              | 0.016      |
| Backchannel: talked through                 | 51% → 100%                | 42% → 100%              |            |
| Turn-taking: responded                      | 8/10 → 8/10               | 7/10 → 10/10            | 0.25       |
| Turn-taking: latency (mean)                 | 2.5 → 2.1 s               | 3.3 → 2.2 s             | 0.20       |
| Pause: turn ended inside the pause          | 4/10 → 1/10               | 4/10 → 1/10             | 0.25       |
| Pause: audible takeover anywhere            | 1/10 → 2/10               | 1/10 → 3/10             | 0.50       |
| Interruption: judge says responded          | 62% → 60%                 | 62% → 50%               | 1.0        |
| Interruption: Sofia kept talking over it    | 0.39 → 1.56 s             | 0.34 → 1.85 s           | 0.008      |

**v2's gains hold on samples it was never tuned on**, and the largest are significant on the
held-out set alone. Its two costs hold too, so they belong to the design:

1. **A slower stop on real interruptions** (about +1.5 s): deciding on words means waiting for
   them.
2. **More takeovers inside long monologues.** v2 ends the turn at a complete-sounding statement
   ("That stuff's real helpful.") and the user goes on for 3-5 s. Text carries no intonation,
   which Smart Turn hears in the baseline.

Next idea, not built: feed an acoustic end-of-turn signal into the decision instead of replacing
it, for example require Smart Turn's verdict only when the model calls a statement complete.

## Iteration 3: v3 from manual calls (not benchmarked)

The bench is English, has no greeting and no tools, so three live calls, mostly in Spanish,
were the evidence for v3. Each finding and its change:

| Found on a live call                                                                 | Change in v3                                                                                       |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Cut off while thinking aloud ("A ver, experiencia… cuando hace años…"), though the model scored the turn clearly unfinished | a clearly unfinished turn waits up to 7 s instead of 3 s                                           |
| The candidate kept answering over Sofia right after that cut; it was dropped as a backchannel | speech within 3 s after a turn ended interrupts at once and is never dropped                      |
| A clear "Por cierto," took about 1 s to stop her                                      | stop phrases ("wait", "espera") interrupt without waiting for a judgment                          |
| A "No." to "¿Tienes alguna duda?" was dropped as side talk, and the caller hung up    | after Sofia asks a question, a lower bar for "addressed to Sofia"                                  |
| Answers said while Sofia still spoke ("Eso me va bien.") were dropped as backchannels | only speech of at most 2 words can be dropped as a backchannel                                     |
| A 7 s wait after "Sí, sí."                                                            | the long wait needs a transcript without final punctuation; the model is told when Sofia was cut off |

The same calls found two pipeline bugs, fixed for every design: a turn could end without having
started (the LLM never ran and the next two answers were swallowed), and dropping side talk left
the user turn open, so Sofia stayed silent for about 12 s.

An offline check on the 120 v2 benchmark samples showed the trade-off: the side-talk change would
have changed none of the bench's drops (the bench agent never asks first), and the backchannel
change would have kept 15 of 67 drops held, so a v3 bench run risks some of those becoming
answered side talk. That run is the next step.
