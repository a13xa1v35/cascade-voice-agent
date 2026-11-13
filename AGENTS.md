# AGENTS.md

Context and rules for coding agents working in this repository.

## Git: history belongs to the user

The user reviews every commit and often rewrites local history (squash, reorder, reword).

- **Never write to git history unless the user explicitly asks for that exact operation in
  the current request.** This covers commit, amend, rebase, squash, reset, cherry-pick,
  tag, stash, branch deletion and push. A request to commit one thing does not authorize
  later commits.
- Finish work in the working tree, run `make check`, report what changed, and stop. The
  user decides what gets committed, how it is grouped and what the message says.
- When asked to commit, commit exactly what was asked, then show `git log --oneline` and
  the commit's `--stat`. Do not stage unrelated files (local notes, `.DS_Store`).
- Commit hashes are not stable: re-read `git log` instead of trusting a hash from earlier
  in the session.
- Read-only git commands (`status`, `diff`, `log`, `show`, `blame`) are always fine.
- Subagents and delegated workers follow the same rule. State it in every brief:
  "do not commit; leave changes in the working tree".

## Testing: evals first, static tests only for invariants

Behaviour is measured by the evals (`evals/`), not by static tests. `tests/` is kept small
(~80 tests, a few seconds) on purpose.

- **Add a static test only if an eval run would stay green while the thing is broken.**
  That means core invariants: the qualification rule, booking integrity under concurrency,
  never re-screening a decided candidate (fail closed when the history cannot load),
  supersede/finalize races, hang-up safety, LLM-failure recovery, the summary fallback,
  migrations matching the models, translation catalogs in sync, webhook security, the demo's
  access control (admin password gate, access codes checked before any call), and for the
  knowledge base: no lost candidate question (searches and referrals to a recruiter are
  saved), index integrity.
- **Do not add tests for:** prompt wording or snapshots, conversation flow, turn-taking
  behaviour, metrics or report formatting, the eval harness, pipeline construction, library
  behaviour, constants or defaults, private internals. Cover these with an eval scenario.
- A bug found by an eval or a live call gets a regression test only if it breaks an
  invariant above; otherwise it is fixed and covered by an eval scenario.
