"""Provider factory: one place to swap STT / TTS / LLM vendors.

Switch providers with STT_PROVIDER / TTS_PROVIDER / LLM_PROVIDER in `.env`. To add a vendor, add
a branch here and a key in config.py; nothing else in the app changes.
"""

from typing import Any

from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.assemblyai.stt import AssemblyAISTTService
from pipecat.services.assemblyai.tts import _DEFAULT_VOICE_ID as ASSEMBLYAI_DEFAULT_VOICE_ID
from pipecat.services.assemblyai.tts import AssemblyAITTSService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.llm_service import LLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.stt_service import STTService
from pipecat.services.tts_service import TTSService
from pipecat.transcriptions.language import Language

from hr_screener.config import Settings
from hr_screener.i18n import Lang
from hr_screener.llm.ratelimit import get_limiter
from hr_screener.llm.services import (
    AgentAnthropicLLMService,
    AgentOpenAILLMService,
    first_chunk_retry,
)

# Env var holding the API key for each provider name used in LLM_PROVIDER / STT_PROVIDER /
# TTS_PROVIDER.
_PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "assemblyai": "ASSEMBLYAI_API_KEY",
    "deepgram": "DEEPGRAM_API_KEY",
    "cartesia": "CARTESIA_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
}


def missing_keys(
    settings: Settings, *, text_only: bool = False, turn_model: bool = True
) -> list[str]:
    """Env vars required by the selected providers that are not set. A text-only call has
    no STT, TTS or turn-taking model, so it only needs the LLM key(s). The post-call summary is
    always an Anthropic call, so ANTHROPIC_API_KEY is also needed whenever the summary is
    enabled, even with Sofia on OpenAI. A voice call also needs the Cloudflare keys of the
    system-one turn-taking model; `turn_model=False` is for the eval, whose variants declare
    their own keys (the `baseline` one does not use the model)."""
    needed: list[str] = []
    if settings.llm_provider == "anthropic" or settings.summary_enabled:
        needed.append(_PROVIDER_KEYS["anthropic"])
    if settings.llm_provider == "openai":
        needed.append(_PROVIDER_KEYS["openai"])
    for provider in () if text_only else (settings.stt_provider, settings.tts_provider):
        key = _PROVIDER_KEYS[provider]
        if key not in needed:  # AssemblyAI for both STT and TTS needs one key, not two
            needed.append(key)
    if turn_model and not text_only:
        needed += ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"]
    return [key for key in needed if not getattr(settings, key.lower())]


def _lang(lang: Lang) -> Language:
    return Language.ES if lang == "es" else Language.EN


def require_keys(settings: Settings, *, text_only: bool = False, turn_model: bool = True) -> None:
    """Raise a clear error before a call starts if configuration is incomplete."""
    if missing := missing_keys(settings, text_only=text_only, turn_model=turn_model):
        raise RuntimeError(f"Missing required settings: {', '.join(missing)} (set them in .env)")


def stt_settings_for(settings: Settings, lang: Lang, *, start: bool = False) -> Any:
    """STT settings for `lang`. Used to build the service and, as a delta, to re-point it when
    the candidate switches the call language (`switch_language`).

    AssemblyAI `language_codes` pins transcription to one language (it needs a U3 Pro model,
    pipecat's default universal-3-6-pro). At `start` the call language comes first and the
    other one follows, so a request to switch made in the other language is still heard (order
    is significant, several codes steer toward that subset); the switch pins the new language
    alone. Deepgram's `language` (pipecat default en) is passed to the live API; whether the
    default model nova-3-general covers es has not been verified against Deepgram."""
    if settings.stt_provider == "assemblyai":
        codes = [_lang(lang)]
        if start:
            codes.append(_lang("es" if lang == "en" else "en"))
        return AssemblyAISTTService.Settings(language_codes=codes)
    return DeepgramSTTService.Settings(language=_lang(lang))


def tts_settings_for(settings: Settings, lang: Lang, *, delta: bool = False) -> Any:
    """TTS settings (voice and language) for `lang`. Used to build the service and, with
    `delta=True`, as the update pushed when the candidate switches the call language.

    The service is built without a language for English, so a plain English call sends the
    same request as before; a switch back to English (`delta`) must name it, or the Spanish
    one would stay. AssemblyAI has a voice per language (all documented Spanish voices are
    Mexican Spanish, there is no Castilian one); an empty `assemblyai_voice_id` is pipecat's
    default voice, named explicitly because an update needs a value to go back to.
    ElevenLabs and Cartesia keep one voice and only change `language`; the voice should be
    one that speaks both well."""
    language = _lang(lang) if lang == "es" or delta else None
    if settings.tts_provider == "assemblyai":
        voice = (
            settings.assemblyai_voice_id_es
            if lang == "es"
            else settings.assemblyai_voice_id or ASSEMBLYAI_DEFAULT_VOICE_ID
        )
        tts: Any = AssemblyAITTSService.Settings(voice=voice)
    elif settings.tts_provider == "elevenlabs":
        tts = ElevenLabsTTSService.Settings(voice=settings.elevenlabs_voice_id)
    else:
        tts = CartesiaTTSService.Settings(voice=settings.cartesia_voice_id)
    if language:
        tts.language = language
    return tts


def make_stt(settings: Settings) -> STTService:
    # Input sample rate (8 kHz phone, 16 kHz web) comes from PipelineParams.
    stt = stt_settings_for(settings, settings.language, start=True)
    if settings.stt_provider == "assemblyai":
        # Default "pipecat mode" (vad_force_turn_endpoint=True): AssemblyAI returns final
        # transcripts as fast as it can and our own turn-taking (Silero VAD + the system-one
        # controller) still decides when the candidate has finished speaking. That keeps
        # turn-taking identical across STT vendors. Passing vad_force_turn_endpoint=False
        # would hand turn detection to AssemblyAI's model instead.
        return AssemblyAISTTService(api_key=settings.assemblyai_api_key, settings=stt)
    return DeepgramSTTService(api_key=settings.deepgram_api_key, settings=stt)


def make_tts(settings: Settings) -> TTSService:
    # The output sample rate (8 kHz for phone, 24 kHz for web) comes from
    # PipelineParams, so the same factory serves both channels.
    tts = tts_settings_for(settings, settings.language)
    if settings.tts_provider == "assemblyai":
        return AssemblyAITTSService(api_key=settings.assemblyai_api_key, settings=tts)
    if settings.tts_provider == "elevenlabs":
        return ElevenLabsTTSService(api_key=settings.elevenlabs_api_key, settings=tts)
    return CartesiaTTSService(api_key=settings.cartesia_api_key, settings=tts)


def make_llm(
    settings: Settings, system_prompt: str, *, fixed_prefix: str | None = None
) -> LLMService[Any]:
    """Sofia's LLM for the selected provider, with the request limiter when one is configured
    (LLM_MAX_RPM / LLM_MAX_TPM; shared by every call of the process, see ratelimit.py).
    `fixed_prefix` is the start of `system_prompt` that is the same for every call
    (`SystemPrompt.fixed`): Anthropic caches it under its own breakpoint. OpenAI caches the
    longest identical prefix by itself, so it ignores it."""
    limiter = get_limiter(
        settings.llm_provider, settings.agent_model, settings.llm_max_rpm, settings.llm_max_tpm
    )
    retry = first_chunk_retry(settings.llm_first_chunk_timeout_secs)
    if settings.llm_provider == "openai":
        return AgentOpenAILLMService(
            api_key=settings.openai_api_key,
            settings=OpenAILLMService.Settings(
                model=settings.openai_model, system_instruction=system_prompt
            ),
            limiter=limiter,
            **retry,
        )
    return AgentAnthropicLLMService(
        api_key=settings.anthropic_api_key,
        settings=AnthropicLLMService.Settings(
            model=settings.anthropic_model,
            system_instruction=system_prompt,
            enable_prompt_caching=settings.anthropic_prompt_caching,
        ),
        limiter=limiter,
        fixed_prefix=fixed_prefix,
        fixed_prefix_ttl=settings.anthropic_fixed_prompt_cache_ttl,
        **retry,
    )
