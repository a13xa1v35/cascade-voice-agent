"""Load and validate the golden set (`golden.yaml`)."""

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GOLDEN_PATH = Path(__file__).parent / "golden.yaml"
LANGS = ("en", "es")


@dataclass(frozen=True)
class GoldenItem:
    id: str
    lang: str  # language the candidate spoke
    question: str  # the candidate's words (the "model forgot to translate" query)
    query_es: str  # the Spanish query the model should write (the normal path)
    expected: tuple[str, ...]  # chunk ids; any of them counts as a hit
    out_of_scope: bool
    tags: tuple[str, ...] = ()


class GoldenError(ValueError):
    """The golden file is malformed; the message lists every problem."""


def parse_golden(data: Any) -> list[GoldenItem]:
    raw = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise GoldenError("golden file needs a non-empty top-level `items` list")
    items: list[GoldenItem] = []
    problems: list[str] = []
    seen: set[str] = set()
    for n, entry in enumerate(raw, 1):
        if not isinstance(entry, dict):
            problems.append(f"item #{n}: not a mapping")
            continue
        iid = str(entry.get("id", "")).strip()
        label = iid or f"#{n}"
        problems.extend(
            f"{label}: missing `{key}`"
            for key in ("id", "lang", "question", "query_es")
            if not str(entry.get(key, "")).strip()
        )
        if iid in seen:
            problems.append(f"{label}: duplicate id")
        seen.add(iid)
        lang = str(entry.get("lang", ""))
        if lang and lang not in LANGS:
            problems.append(f"{label}: lang {lang!r} not in {LANGS}")
        expected = entry.get("expected") or []
        if not isinstance(expected, list) or not all(isinstance(e, str) for e in expected):
            problems.append(f"{label}: `expected` must be a list of chunk ids")
            expected = []
        oos = bool(entry.get("out_of_scope", False))
        if oos and expected:
            problems.append(f"{label}: out_of_scope items must have no expected ids")
        if not oos and not expected:
            problems.append(f"{label}: in-scope items need at least one expected id")
        tags = entry.get("tags") or []
        items.append(
            GoldenItem(
                id=iid,
                lang=lang,
                question=str(entry.get("question", "")),
                query_es=str(entry.get("query_es", "")),
                expected=tuple(expected),
                out_of_scope=oos,
                tags=tuple(str(t) for t in tags),
            )
        )
    if problems:
        raise GoldenError("invalid golden set:\n  " + "\n  ".join(problems))
    return items


def load_golden(path: Path = GOLDEN_PATH) -> list[GoldenItem]:
    return parse_golden(yaml.safe_load(path.read_text(encoding="utf-8")))


def unknown_expected(items: list[GoldenItem], chunk_ids: Collection[str]) -> dict[str, list[str]]:
    """Item id -> expected chunk ids that are not in the knowledge base (empty when valid).

    Chunk ids depend on how the chunker merges short sections, so editing the knowledge files
    can silently invalidate the golden set; the runner refuses to start until this is empty.
    """
    known = set(chunk_ids)
    return {
        i.id: [e for e in i.expected if e not in known]
        for i in items
        if any(e not in known for e in i.expected)
    }
