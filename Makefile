.PHONY: prompts port install migrate redis seed reseed dev chat eval test lint fmt typecheck check report messages compile-messages ingest eval-kb eval-e2e eval-turn-taking eval-turn-taking-setup eval-turn-taking-fetch-data eval-turn-taking-score eval-turn-taking-compare

install:
	uv sync

redis:
	docker compose up -d redis

migrate:
	uv run alembic upgrade head

seed: migrate
	uv run python -m hr_screener.app.seed

reseed: migrate
	uv run python -m hr_screener.app.seed --reset --name "Alex"

report:
	uv run python -m hr_screener.observability.report $(ID)

# Port for `make dev`: the main checkout keeps 7860 (ngrok/Twilio point at it); every other git
# worktree gets a stable port in 7861-7960 derived from its path. PORT=8000 make dev overrides.
# (make does not read .env, and uvicorn gets --port explicitly, so .env's PORT is not used here.)
ifeq ($(shell git rev-parse --git-common-dir 2>/dev/null),.git)
PORT ?= 7860
else
PORT ?= $(shell echo $$((7861 + $(shell printf '%s' '$(CURDIR)' | cksum | cut -d' ' -f1) % 100)))
endif

# Print the port `make dev` would use.
port:
	@echo $(PORT)

dev: migrate
	@echo "Web UI: http://localhost:$(PORT)"
	uv run uvicorn hr_screener.app.api:create_app --factory --reload --host 0.0.0.0 --port $(PORT)

# Sync the knowledge base (KB_DIR) into Qdrant; stop the server first when Qdrant is embedded.
ingest:
	uv run python -m hr_screener.knowledge.ingest

# Text-only chat with Sofia in the terminal; ID=<candidate id> optional (see README).
chat: migrate
	uv run python -m hr_screener.cli.chat $(if $(ID),--candidate $(ID))

# Eval harness (REAL API calls: Sofia, simulated candidate, summary, judge). Cheap defaults:
# one run, Spanish, every scenario. E.g. make eval-e2e SCENARIOS=c,l2 LANGS=es,en RUNS=3
# See evals/README.md. Each suite gets an `eval-<suite>` target.
# Sofia's provider and the request limits come from the environment like in the app, e.g.
#   LLM_PROVIDER=openai make eval-e2e LANGS=es,en   (see evals/e2e/README.md)
SCENARIOS ?= all
LANGS ?= es
RUNS ?= 1
eval-e2e:
	uv run python -m evals.e2e.run --scenarios $(SCENARIOS) --langs $(LANGS) --runs $(RUNS) \
		$(if $(CONCURRENCY),--concurrency $(CONCURRENCY)) \
		$(if $(NO_SUMMARY),--no-summary) $(if $(NO_JUDGE),--no-judge) \
		$(if $(KB_PROVIDER),--kb-provider $(KB_PROVIDER))

# Retrieval eval of the knowledge base (in-memory Qdrant; calls the embedding API when the
# provider is openai or voyage, cached on disk). E.g. make eval-kb PROVIDER=local K=4
eval-kb:
	uv run python -m evals.kb.run $(if $(PROVIDER),--provider $(PROVIDER)) $(if $(K),--k $(K))

# Translations (gettext via Babel). The .po files are the source of truth; the compiled .mo
# files are checked in and tests/test_i18n.py fails when one is stale.
# messages: extract the msgids from the code into the .pot and merge them into every .po.
LOCALE_DIR = src/hr_screener/i18n/locale
messages:
	uv run pybabel extract -F babel.cfg --add-comments=Translators: --no-location \
		--project=hr-screener --version=0.1.0 --copyright-holder="hr-screener" \
		-o $(LOCALE_DIR)/messages.pot src
	uv run pybabel update -i $(LOCALE_DIR)/messages.pot -d $(LOCALE_DIR) --no-fuzzy-matching

# compile-messages: .po -> .mo (run after editing a .po).
compile-messages:
	uv run pybabel compile -d $(LOCALE_DIR) --statistics

# Render the system prompt of a few representative calls into docs/prompts/ (no API calls), so a
# prompt change is a readable diff in review. Commit the result with the change.
prompts:
	uv run python -m evals.prompts.render

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run ty check

# Everything CI would run: lint + format check, type check, tests.
check: lint typecheck test

# Turn-taking eval (Full-Duplex-Bench), see evals/turn_taking/README.md.
# Inference (REAL API calls: STT, LLM, TTS, Cloudflare): make eval-turn-taking CONFIG=evals/turn_taking/configs/baseline.yaml
CONFIG ?= evals/turn_taking/configs/baseline.yaml
eval-turn-taking:
	uv run python -m evals.turn_taking.run --config $(CONFIG) $(ARGS)

# Scoring runs in its own env (evals/turn_taking/scoring): torch + NeMo Parakeet ASR on CPU.
eval-turn-taking-setup:
	bash evals/turn_taking/scoring/setup.sh

eval-turn-taking-fetch-data:
	uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/fetch_data.py

# make eval-turn-taking-score RUN=baseline-env-telephony [ARGS="--tasks v1/candor_pause_handling"]
eval-turn-taking-score:
	uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/run_eval.py --run evals/results/turn_taking/$(RUN) $(ARGS)

# make eval-turn-taking-compare A=baseline-env-telephony B=system-one-telephony
eval-turn-taking-compare:
	uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/compare.py --a evals/results/turn_taking/$(A) --b evals/results/turn_taking/$(B)
