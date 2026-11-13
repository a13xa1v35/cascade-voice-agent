"""Sofia's LLM services: Pipecat's Anthropic and OpenAI services with a request limiter, and the
classification of a provider's rate-limit / quota errors.

Where the limiter hooks in, and why
-----------------------------------
Every request to the model goes through `_process_context(context)` of the Pipecat service, for
both a candidate's turn and the follow-up request after a tool result (the assistant aggregator
pushes that one upstream *to the LLM*, so a processor placed before the LLM would never see it).
The two subclasses below override it to wait for a slot from `ratelimit.SlidingWindowLimiter`
first, then call the original. Waiting before the original means the TTFB metric (started inside
it) does not include the wait. The wait is an ordinary await inside the service's frame
handling, so Pipecat's interruption handling should cancel it like any in-flight request (the
text channel has no interruptions; not verified on a live voice call).

`_process_context` is private to Pipecat. Verified against pipecat-ai 1.15.0 for
`AnthropicLLMService` and `OpenAILLMService` (`BaseOpenAILLMService._process_context`, called
from its `process_frame`). Both keep the system prompt in `_settings.system_instruction` and
their adapters have `from_standard_tools`. Re-check all of that after a Pipecat upgrade, or the
limiter is silently dropped.

Re-sending a stalled request
----------------------------
See `first_chunk_retry`. It sits inside Pipecat's request code, below `_process_context`, so a
re-sent request does not take a second limiter slot (the real request rate can be slightly
above LLM_MAX_RPM while a provider stalls).
"""

from collections.abc import Sequence
from typing import Any, Literal

from pipecat.adapters.llm.services.anthropic_adapter import AnthropicLLMAdapter
from pipecat.adapters.llm.services.open_ai_adapter import OpenAILLMAdapter
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    FunctionCallFromLLM,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.llm_service import LLMService, TAdapter
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.utils.errors import ErrorCategory

from hr_screener.llm.ratelimit import SlidingWindowLimiter, estimate_tokens


def first_chunk_retry(timeout_secs: float) -> dict[str, Any]:
    """Pipecat constructor arguments that re-send a request whose answer does not start within
    `timeout_secs` (0 = no retry). Verified against pipecat-ai 1.15.0. Each provider retries
    ONCE, and only the start of the answer:

    - OpenAI (`BaseOpenAILLMService.get_chat_completions`): `asyncio.wait_for` around
      `chat.completions.create(stream=True)`, i.e. until the HTTP response starts, not until
      the first text chunk. On a timeout the request is re-issued once with NO timeout, so a
      second stall waits for the SDK's own timeout (10 minutes), and a stall in the middle of
      the stream is not covered at all.
    - Anthropic (`AnthropicLLMService._create_message_stream`): `asyncio.wait_for` around
      opening the stream, i.e. until the HTTP response starts, not until the first text. On a
      timeout the request is re-issued once with NO timeout, so a second stall waits for the
      SDK's own timeout (10 minutes), and a stall in the middle of the stream is not covered
      at all.

    Neither covers every stall; the app-level recovery (llm/recovery.py) handles whatever
    still ends as an error.
    """
    if timeout_secs <= 0:
        return {"retry_on_timeout": False}
    return {"retry_on_timeout": True, "retry_timeout_secs": timeout_secs}


def is_quota_error(error: ErrorFrame) -> bool:
    """True when `error` is the provider refusing for rate / quota reasons (HTTP 429,
    `RateLimitError` of OpenAI and Anthropic, which carries `status_code` 429, also for
    `insufficient_quota`), not a fault of Sofia's. Decided from the exception first; Pipecat's
    category and the message are backups."""
    exc = error.exception
    if exc is not None and (
        getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429
    ):
        return True
    if error.category in (ErrorCategory.RATE_LIMIT, ErrorCategory.QUOTA):
        return True
    text = f"{error.error} {exc or ''}".lower()
    return "rate_limit_error" in text or "insufficient_quota" in text


async def _wait_for_slot(
    limiter: SlidingWindowLimiter | None, service: Any, context: LLMContext
) -> None:
    """Hold the request until the limiter admits it (no-op when there is none)."""
    if limiter is None or not limiter.enabled:
        return
    system = service._settings.system_instruction
    try:
        tools = service.get_llm_adapter().from_standard_tools(context.tools)
    except Exception:  # the estimate must never break a request
        tools = None
    await limiter.acquire(
        estimate_tokens(system if isinstance(system, str) else "", tools, context.messages)
    )


class ResponseTracker(LLMService[TAdapter]):
    """Remembers what the model wrote in the current response and how many tool calls it
    made, so a tool handler can see what was already said along with it (`params.llm`).

    Both are set in the service's own task: text frames are pushed while the stream is read,
    and the tool calls run after it, so a handler always sees the whole text before its call.
    Used by `agent/tools.py` to skip the follow-up reply after a save when Sofia already asked
    the next question in the same response (README, lesson 17)."""

    response_text: str = ""
    response_tool_calls: int = 0

    async def push_frame(self, frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        if isinstance(frame, LLMFullResponseStartFrame):
            self.response_text, self.response_tool_calls = "", 0
        elif isinstance(frame, LLMTextFrame) and direction is FrameDirection.DOWNSTREAM:
            self.response_text += frame.text
        await super().push_frame(frame, direction)

    async def run_function_calls(self, function_calls: Sequence[FunctionCallFromLLM]):
        self.response_tool_calls = len(function_calls)
        await super().run_function_calls(function_calls)


class AgentAnthropicLLMService(ResponseTracker[AnthropicLLMAdapter], AnthropicLLMService):
    """`AnthropicLLMService` that waits for a rate-limiter slot before each request, and caches
    the part of the system prompt that is the same for every call separately from the rest.

    `fixed_prefix` is the start of the system instruction that does not change between calls
    (`SystemPrompt.fixed`). Anthropic renders tools, then system, then messages, and a cache hit
    needs a byte-identical prefix up to a breakpoint, so a breakpoint right after the fixed part
    lets a new call read tools + fixed prompt from the cache instead of writing them again.
    `fixed_prefix_ttl` is that entry's lifetime; "1h" costs 2x to write against 1.25x for "5m",
    so it only pays off when calls are more than 5 minutes apart.
    """

    def __init__(
        self,
        *args: Any,
        limiter: SlidingWindowLimiter | None = None,
        fixed_prefix: str | None = None,
        fixed_prefix_ttl: Literal["5m", "1h"] = "5m",
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._limiter = limiter
        self._fixed_prefix = fixed_prefix
        self._fixed_prefix_ttl = fixed_prefix_ttl

    async def _get_llm_invocation_params(self, context: LLMContext):
        """Pipecat's parameters, with its one system block split in two when it starts with
        the fixed prefix: [fixed (breakpoint, ttl), per-call (breakpoint)]. Pipecat puts two
        more breakpoints on the last two user messages: four in total, the API maximum. A longer
        TTL must come before a shorter one, which the fixed block, first, always does. Without
        caching, or when the system text does not start with the prefix, pipecat's request is
        sent unchanged."""
        params = await super()._get_llm_invocation_params(context)
        system = params.get("system")
        prefix = self._fixed_prefix
        if not prefix or not isinstance(system, list) or len(system) != 1:
            return params
        text = system[0].get("text", "")
        rest = text[len(prefix) :]
        if not text.startswith(prefix) or not rest.strip():
            return params
        fixed_control: dict[str, str] = {"type": "ephemeral"}
        if self._fixed_prefix_ttl != "5m":  # 5 minutes is Anthropic's default
            fixed_control["ttl"] = self._fixed_prefix_ttl
        blocks: list[Any] = [
            {"type": "text", "text": prefix, "cache_control": fixed_control},
            # Starts with the separator, so the two blocks together are the original text.
            {"type": "text", "text": rest, "cache_control": {"type": "ephemeral"}},
        ]
        return {**params, "system": blocks}

    async def _process_context(self, context: LLMContext):
        await _wait_for_slot(self._limiter, self, context)
        await super()._process_context(context)


class AgentOpenAILLMService(ResponseTracker[OpenAILLMAdapter], OpenAILLMService):
    """`OpenAILLMService` that waits for a rate-limiter slot before each request."""

    def __init__(self, *args: Any, limiter: SlidingWindowLimiter | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._limiter = limiter

    async def _process_context(self, context: LLMContext):
        await _wait_for_slot(self._limiter, self, context)
        await super()._process_context(context)
