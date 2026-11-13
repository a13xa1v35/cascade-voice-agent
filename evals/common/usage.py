"""Token accounting and pricing shared by every eval suite."""

from dataclasses import dataclass
from typing import Any, NamedTuple


class Price(NamedTuple):
    """$ per million tokens. `cache_read` None = not known: cache reads are then priced as
    plain input, which can only overstate the cost."""

    input: float
    output: float
    cache_read: float | None = None


# From the model price lists (paid tiers). Anthropic cache reads are 0.1x the input price.
# Cache writes are never priced separately (1.25x on Anthropic; not exposed by the metrics), so
# a cached run's cost is slightly understated.
PRICES: dict[str, Price] = {
    "claude-haiku-5-5": Price(0.10, 0.50, 0.01),
    "claude-sonnet-5-5": Price(2.00, 10.00, 0.20),
    "claude-opus-5-5": Price(4.00, 20.00, 0.40),
    "gpt-4.1-mini": Price(0.40, 1.60, 0.10),
}


@dataclass
class Usage:
    """Tokens of one component. `input_tokens` EXCLUDES `cache_read_tokens` (they are billed
    at a different rate), so `cost()` adds the two. Reasoning tokens are not a field: both
    Anthropic and OpenAI already count them in `output_tokens`."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0  # informational: already inside output_tokens, never priced twice

    def add(self, other: "Usage") -> None:
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.reasoning_tokens += other.reasoning_tokens


def add_usage(target: Usage, usage: Any) -> None:
    """Accumulate an Anthropic `response.usage` into a `Usage` (its input_tokens are net of
    the cache already)."""
    target.calls += 1
    target.input_tokens += getattr(usage, "input_tokens", 0) or 0
    target.output_tokens += getattr(usage, "output_tokens", 0) or 0
    target.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
    target.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0


def add_agent_usage(
    target: Usage,
    provider: str,
    *,
    calls: int,
    prompt_tokens: int,
    completion_tokens: int,
    cache_read_tokens: int | None,
    reasoning_tokens: int | None,
) -> None:
    """Accumulate the `call_metrics` token columns of one call into `target`.

    The stored `prompt_tokens` is what the provider reported: net of the cache for Anthropic,
    gross (cached tokens included) for OpenAI (docs/metrics.md). `Usage.input_tokens` is always
    net, so OpenAI's cache reads are taken out of it here."""
    cached = cache_read_tokens or 0
    target.calls += calls
    target.input_tokens += prompt_tokens - cached if provider == "openai" else prompt_tokens
    target.output_tokens += completion_tokens
    target.cache_read_tokens += cached
    target.reasoning_tokens += reasoning_tokens or 0


def cost(usage: Usage, model: str | None) -> float | None:
    price = PRICES.get(model or "")
    if price is None:
        return None
    cache_price = price.input if price.cache_read is None else price.cache_read
    return (
        usage.input_tokens * price.input
        + usage.cache_read_tokens * cache_price
        + usage.output_tokens * price.output
    ) / 1_000_000
