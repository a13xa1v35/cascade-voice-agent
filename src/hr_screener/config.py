"""Application settings, read from environment variables / a local `.env` file.

API keys default to empty strings so the package imports (and tests run) with no
configuration at all. Missing keys are reported when a call actually starts - see
`services.missing_keys`.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Dense embedding model per hosted provider, used when EMBEDDING_MODEL is empty.
DEFAULT_EMBEDDING_MODELS = {"openai": "text-embedding-3-large", "voyage": "voyage-4-lite"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Language of the call (STT, TTS, spoken dates and places, the Language rule in the
    # prompt, the summary). The prompt and tool texts are English for every call. Restart the
    # server to change. ---
    language: Literal["en", "es"] = "en"

    # --- Providers (swap with one env var each; see pipeline/providers.py) ---
    # AssemblyAI is the default for both STT and TTS and Anthropic for Sofia's LLM, so a first
    # run needs only two keys: ASSEMBLYAI_API_KEY and ANTHROPIC_API_KEY.
    # LLM_PROVIDER selects Sofia's model only: the post-call summary is always Anthropic.
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    stt_provider: Literal["assemblyai", "deepgram"] = "assemblyai"
    tts_provider: Literal["assemblyai", "cartesia", "elevenlabs"] = "assemblyai"

    # --- API keys ---
    anthropic_api_key: str = ""
    assemblyai_api_key: str = ""
    deepgram_api_key: str = ""
    cartesia_api_key: str = ""
    elevenlabs_api_key: str = ""
    # Cloudflare Workers AI: the turn-taking decision model (turn_taking/), required for every
    # voice call (web and phone); the text channel does not use it.
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    # In-call frustration check (pipeline/frustration.py): recorded per call. Uses the Cloudflare
    # keys above; off when they are empty. Minimum seconds between the starts of two requests:
    # shorter than a voice exchange, so every candidate turn is judged, but a cap on bursts.
    frustration_check_enabled: bool = True
    frustration_min_gap_secs: float = 3.0
    # Tell Sofia (a short note, one turn late) when the check finds the candidate frustrated. Off
    # until the m1/m2 evals support turning it on; needs the check to run.
    frustration_notes_enabled: bool = False

    # --- Models / voices ---
    # Haiku: the lowest latency and cost, and good enough for a scripted screening (the
    # rule, not the model, decides). Stronger: claude-sonnet-5-5, claude-opus-5-5 (Opus gets
    # `effort: low` from pipecat automatically).
    anthropic_model: str = "claude-haiku-5-5"
    # Anthropic prompt caching for Sofia: the system prompt and tools (~6k tokens) are re-sent on
    # every request of a call, so later requests read them from the cache (billed at a tenth of
    # the input price; the first write costs 1.25x). Default 5-minute cache lifetime: requests
    # within a call are seconds apart. The part of the prompt that is the same for every call
    # (the tools and `SystemPrompt.fixed`) has its own breakpoint, so a new call reads it from
    # the cache instead of writing it again; the rest differs per call (name, calendar).
    anthropic_prompt_caching: bool = True
    # Lifetime of that shared entry. "1h" costs 2x to write (5m: 1.25x) and only pays off when
    # calls are more than 5 minutes apart; with calls closer than that, 5m stays warm by itself.
    # A 1h TTL is valid only on this first block (longer TTLs must come before shorter ones).
    anthropic_fixed_prompt_cache_ttl: Literal["5m", "1h"] = "5m"
    # OpenAI model for Sofia when llm_provider=openai. A non-reasoning model on purpose: a
    # voice turn has no time for hidden thinking tokens. Prompt caching is automatic.
    openai_model: str = "gpt-4.1-mini"
    assemblyai_voice_id: str = ""  # English voice; empty = pipecat's default AssemblyAI voice
    # Spanish voice. All documented AssemblyAI Spanish voices are Mexican Spanish
    # (aai-antonioluis, aai-constanza, aai-malvina, aai-oriol); no Castilian voice exists.
    assemblyai_voice_id_es: str = "aai-constanza"
    cartesia_voice_id: str = "86e30c1d-714b-4074-a1f2-1cb6b552fb49"
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # --- Sofia's LLM requests: client-side rate limit ---
    # For quota-limited keys (free tiers, quotas shared with other services) and the eval.
    # Every request Sofia's LLM makes waits until it fits under both limits (sliding 60 s
    # window, see ratelimit.py). 0 = off, the default: a normal paid key needs no limiter,
    # and a wait adds latency to a live call. The limit is per process: several app
    # instances sharing one quota need a shared limiter (e.g. Redis), not built here.
    llm_max_rpm: float = 0  # requests per minute
    llm_max_tpm: int = 0  # input tokens per minute (estimated, ~4 characters per token)
    # Re-send a request whose answer does not start in time. 0 = off. What is
    # retried, once each, is spelled out at `llm_services.first_chunk_retry`. 5 s: a voice turn
    # that is silent for longer has failed anyway, and Haiku's TTFB (p95 0.8 s, max 1.8 s in
    # the benchmark) never reaches it. A slower healthy model is re-sent too, which costs its
    # input tokens twice; raise it if that matters more than latency.
    # Whatever still fails is handled by the app (llm/recovery.py): one more attempt, then an
    # apology and a clean end.
    llm_first_chunk_timeout_secs: float = 5.0

    # --- Post-call summary ---
    # One direct Anthropic call after the pipeline is down, whatever llm_provider is.
    # SUMMARY_MODEL empty = anthropic_model.
    summary_enabled: bool = True  # False = always the deterministic fallback, no API call
    # The summary runs after the call, off the latency path, so it can use a stronger model.
    summary_model: str = "claude-sonnet-5-5"
    summary_timeout_secs: float = 30.0

    # --- Storage ---
    # The database is the system of record (openings, candidates, screenings, facts,
    # transcripts, tool calls, call metrics, summaries, slots, bookings). SQLite by default;
    # for Postgres use "postgresql+asyncpg://user:pass@host/db" and install `asyncpg`.
    # Schema: `make migrate`.
    database_url: str = "sqlite+aiosqlite:///./var/hr_screener.storage.db"
    # Redis only holds the per-call event timeline (CallRecorder): telemetry, not a record.
    redis_url: str = "redis://localhost:6379/0"
    # The event timeline key expires this many days after the call's last flush. The scalar
    # scorecard and the tool calls stay in the database (call_metrics, tool_calls).
    events_ttl_days: int = 30

    # --- Knowledge base (RAG; design in the README) ---
    # Markdown documents in KB_DIR are split into chunks, embedded and stored in Qdrant.
    kb_dir: str = "knowledge"
    # Language of the knowledge base: picks the BM25 stemmer ("es" or "en") and is the
    # language the model writes search queries in.
    kb_language: Literal["es", "en"] = "es"
    # Qdrant: embedded in the QDRANT_PATH folder (one process only), or a server / Qdrant
    # Cloud when QDRANT_URL is set (then the path is ignored).
    qdrant_path: str = "var/qdrant"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "knowledge"
    # Dense embeddings. openai (default) and voyage need OPENAI_API_KEY / VOYAGE_API_KEY
    # (without it the knowledge base reports itself unavailable and the server still
    # starts); local runs a multilingual model through fastembed (no network, ~220 MB
    # download on first use). EMBEDDING_MODEL empty means the provider's default (see
    # `effective_embedding_model`). Changing the provider, the model or EMBEDDING_DIM means a
    # full re-ingest (`make ingest`, or the next startup sync does it).
    # Also Sofia's key when llm_provider=openai.
    openai_api_key: str = ""
    voyage_api_key: str = ""
    embedding_provider: Literal["openai", "voyage", "local"] = "openai"
    embedding_model: str = ""
    # openai / voyage output dimension; the local model is fixed at 384
    embedding_dim: int = 1024
    local_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # fastembed downloads its models here (its own default is the system temp dir).
    fastembed_cache_dir: str = "var/fastembed"
    kb_top_k: int = 4  # chunks returned to the model
    # Best dense cosine score below this = no match. From `make eval-kb` on text-embedding-3-large
    # at 1024 dims; re-tune for another model.
    kb_min_score: float = 0.45
    kb_timeout_secs: float = 5.0  # deadline for one lookup (query embedding + search)
    kb_tool_timeout_secs: float = 8.0  # Pipecat backstop around the whole tool call
    kb_sync_on_startup: bool = True  # sync KB_DIR into Qdrant before accepting calls

    # --- Twilio (phone channel only) ---
    # Public https URL that reaches this server (e.g. your ngrok URL).
    public_base_url: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # --- Business defaults ---
    agency_name: str = "TuTeacher"
    agent_name: str = "Sofia"  # the assistant's name, said in the greeting
    country: str = "Spain"
    timezone: str = "Europe/Madrid"  # used to read slot times aloud
    # A follow-up within this many minutes of the earlier call's start carries straight on
    # (no "is now a good time?"); later ones ask that once. Interest is never re-asked once
    # the earlier call got as far as the screening questions.
    followup_recent_minutes: int = 30
    demo_candidate_id: str = ""  # used by POST /start when no candidate is given
    demo_candidate_phone: str = "+15555550100"  # used by the seed script

    # --- Public demo (Fly.io; Dockerfile and fly.toml) ---
    # Admin password (HTTP Basic, any username) for the REST API, /docs and /client. The demo
    # pages (/, /demo, /demo/*) are public and /health and the Twilio webhooks stay open;
    # starting a call needs an access code. Empty = no gate. The REST API exposes candidate
    # data: set it when deployed.
    demo_password: str = ""
    # Comma-separated access codes (one or several) that POST /demo/call and the results
    # route require. Empty = nobody can start a demo call.
    demo_access_codes: str = ""
    # Shown on the home page; a link is hidden when its URL is empty.
    demo_author_name: str = "Alex Alves"
    demo_github_url: str = ""
    demo_linkedin_url: str = ""
    # False = phone-only: no browser UI (/client) and no WebRTC routes; / serves the demo page.
    web_ui_enabled: bool = True
    # Phone screenings POST /demo/call may start in 24 hours (0 = unlimited): caps the bill.
    demo_max_calls_per_day: int = 20
    # Twilio hangs up any call after this many seconds.
    call_time_limit_secs: int = 900

    # --- Observability ---
    # Per-turn latency breakdowns are always logged. DEBUG_PIPELINE=true also logs
    # every transcript, LLM request/response, tool call and service metric.
    debug_pipeline: bool = True
    call_log_dir: str = "logs/calls"  # one log file per call: {call_log_dir}/{screening_id}.log

    # --- Hang-up safety ---
    # After the goodbye finished playing, wait this long for the candidate to speak before
    # closing the line. If they start a turn in that window, the hang-up is cancelled.
    hangup_grace_secs: float = 3.0

    # --- Dead-connection handling ---
    # Browser calls only: end the call as `connection_lost` when no audio frame arrived for
    # this long after the client was ready (SmallWebRTC itself notices ~30 s later). 0 = off.
    audio_lost_secs: float = 5.0
    # A new call for a candidate ends their still-running one first; wait at most this long
    # for the old call to write its final status, then close it by force.
    supersede_wait_secs: float = 5.0

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 7860

    @property
    def agent_model(self) -> str:
        """The model of the active provider: the one Sofia talks with."""
        return self.openai_model if self.llm_provider == "openai" else self.anthropic_model

    @property
    def effective_embedding_model(self) -> str:
        """EMBEDDING_MODEL, or the default of the chosen provider when it is empty."""
        if self.embedding_provider == "local":
            return self.local_embedding_model
        return self.embedding_model or DEFAULT_EMBEDDING_MODELS[self.embedding_provider]

    @property
    def effective_summary_model(self) -> str:
        # The summary is always an Anthropic call (summary.py), so the fallback is the
        # Anthropic model even when Sofia runs on OpenAI.
        return self.summary_model or self.anthropic_model
