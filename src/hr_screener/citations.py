"""Deterministic checks on text a model claims to cite.

When a model quotes someone, the quote is checked in code against the source before anyone
relies on it. What happens on a failed check depends on the use: the summary drops the quote,
the eval judge blanks its evidence and counts it. Nothing here calls a model.

`quote_found` accepts a quote whose words appear in one source text, in order, ignoring case,
accents and punctuation (a model may fix those when it quotes, never a word); an ellipsis
marks an omission.
"""

import re
import unicodedata
from collections.abc import Iterable

_ELLIPSIS = re.compile(r"\.\.\.|…|\[\.\.\.\]")


def normalize(text: str) -> str:
    """Casefolded, without accents or punctuation, single-spaced."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    letters = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", letters).split())


def quote_found(quote: str, sources: Iterable[str]) -> bool:
    """True when every part of `quote` (split at an ellipsis) appears in one of `sources`,
    whole words only, in order."""
    parts = [n for part in _ELLIPSIS.split(quote) if (n := normalize(part))]
    return bool(parts) and any(_in_order(parts, normalize(source)) for source in sources)


def verified_quotes(quotes: Iterable[str], sources: Iterable[str]) -> list[str]:
    """The quotes `quote_found` accepts, in their original order and wording."""
    texts = list(sources)
    return [quote for quote in quotes if quote_found(quote, texts)]


def _in_order(parts: list[str], source: str) -> bool:
    padded, start = f" {source} ", 0
    for part in parts:
        found = padded.find(f" {part} ", start)
        if found < 0:
            return False
        start = found + len(part) + 1
    return True
