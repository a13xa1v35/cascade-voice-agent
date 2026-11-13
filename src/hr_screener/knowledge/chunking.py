"""Markdown knowledge base -> chunks ready to embed.

Each `*.md` file under the knowledge directory has YAML front matter (id, kind, title and,
for regulations, as_of and source) followed by markdown with `##` / `###` headings. A file
is one document; it is split at those headings into chunks of roughly 150 to 400 words
(words stand in for tokens: no tokenizer dependency, and Spanish text runs about 1.5 tokens
per word, so the real size is still well inside any embedding limit).

Design choices:

* Sizes are enforced per top-level section first: a short `###` subsection is folded into
  the text before it, a long unit is cut at paragraph boundaries (then sentences, then words
  as a last resort). A section that is still short after that joins the chunk before it.
  Folded headings stay in the text as `### Heading` lines so nothing is lost.
* Every chunk's *indexed* text starts with a context header, "Title > Section > Subsection",
  because a chunk like "the rate drops to 7%" cannot be found or understood alone. The
  *payload* text (what the model reads) has no header; title and section travel separately.
* Chunk ids are `{doc_id}#{section-slug}` (accents stripped), stable across edits so an
  update replaces the point instead of duplicating it. Duplicates inside a document get a
  `-2`, `-3` suffix, and split parts of one long section do too.
* `content_hash` covers everything that changes what is stored (indexed text, kind, title,
  as_of, source) plus a fingerprint of the models that produced the vectors, so changing the
  embedding model re-embeds everything without any other bookkeeping.
* An empty or missing directory is an error, never an empty list: an empty list would make
  the sync delete the whole index because of a mistyped KB_DIR.
"""

import hashlib
import math
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from hr_screener.knowledge.types import KnowledgeBaseContentError

KINDS = ("policy", "regulation")
MIN_WORDS = 150
MAX_WORDS = 400

_HEADING = re.compile(r"^(#{2,3})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Document:
    id: str
    kind: str
    title: str
    as_of: date | None
    source: str | None
    body: str
    path: Path


@dataclass(frozen=True)
class Chunk:
    id: str  # "{doc_id}#{section-slug}"
    doc_id: str
    kind: str
    title: str
    section: str  # "" for text before the first heading
    subsection: str
    text: str  # the chunk body, without the context header
    as_of: date | None
    source: str | None

    @property
    def indexed_text(self) -> str:
        """The text that is embedded: context header, blank line, body."""
        header = " > ".join(p for p in (self.title, self.section, self.subsection) if p)
        return f"{header}\n\n{self.text}"

    def content_hash(self, fingerprint: str) -> str:
        """sha256 over the model fingerprint and everything stored for this chunk."""
        parts = [
            fingerprint,
            self.kind,
            self.title,
            self.as_of.isoformat() if self.as_of else "",
            self.source or "",
            self.indexed_text,
        ]
        return hashlib.sha256("\x00".join(parts).encode()).hexdigest()


_POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://hr-screener/knowledge")


def point_id(chunk_id: str) -> str:
    """Qdrant point id of a chunk: UUIDv5 of its id (points are integers or UUIDs only)."""
    return str(uuid.uuid5(_POINT_NAMESPACE, chunk_id))


def kb_version(chunk_hashes: list[str]) -> str:
    """Version of a whole knowledge base: sha256 over the sorted chunk hashes."""
    return hashlib.sha256("\n".join(sorted(chunk_hashes)).encode()).hexdigest()


def slugify(text: str) -> str:
    """Lowercase ASCII slug: accents stripped (ó -> o, ñ -> n), other symbols become '-'."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _words(text: str) -> int:
    return len(text.split())


# --- Loading and front matter ---


def load_chunks(directory: str | Path) -> list[Chunk]:
    """Every chunk of every `*.md` file under `directory` (recursive), in a stable order.

    Raises KnowledgeBaseContentError listing every problem found (all files are checked
    before it raises, so one run shows the whole list).
    """
    return [c for doc in load_documents(directory) for c in split_document(doc)]


def load_documents(directory: str | Path) -> list[Document]:
    root = Path(directory)
    if not root.is_dir():
        raise KnowledgeBaseContentError(f"knowledge directory not found: {root}")
    paths = sorted(root.rglob("*.md"))
    if not paths:
        raise KnowledgeBaseContentError(f"no .md files under {root}")

    docs: list[Document] = []
    errors: list[str] = []
    seen: dict[str, Path] = {}
    for path in paths:
        try:
            doc = parse_document(path.read_text(encoding="utf-8"), path)
        except KnowledgeBaseContentError as e:
            errors.append(str(e))
            continue
        if doc.id in seen:
            errors.append(f"{path}: duplicate id {doc.id!r} (also in {seen[doc.id]})")
            continue
        seen[doc.id] = path
        docs.append(doc)
    if errors:
        raise KnowledgeBaseContentError("invalid knowledge base:\n- " + "\n- ".join(errors))
    return docs


def parse_document(raw: str, path: Path) -> Document:
    """Parse one file's front matter and body. Raises KnowledgeBaseContentError."""
    text = raw.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise KnowledgeBaseContentError(f"{path}: missing YAML front matter (--- ... ---)")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise KnowledgeBaseContentError(f"{path}: front matter is not closed with ---") from None
    try:
        meta: Any = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as e:
        raise KnowledgeBaseContentError(f"{path}: invalid YAML front matter: {e}") from e
    if not isinstance(meta, dict):
        raise KnowledgeBaseContentError(f"{path}: front matter must be a mapping")

    def required(key: str) -> str:
        value = meta.get(key)
        if value is None or not str(value).strip():
            raise KnowledgeBaseContentError(f"{path}: front matter is missing {key!r}")
        return str(value).strip()

    doc_id = required("id")
    if slugify(doc_id) != doc_id:
        raise KnowledgeBaseContentError(
            f"{path}: id {doc_id!r} must be a lowercase slug (letters, digits, hyphens)"
        )
    title = required("title")
    kind = required("kind")
    if kind not in KINDS:
        raise KnowledgeBaseContentError(
            f"{path}: unknown kind {kind!r} (expected one of {', '.join(KINDS)})"
        )
    as_of = _parse_date(meta.get("as_of"), path)
    if kind == "regulation" and as_of is None:
        raise KnowledgeBaseContentError(f"{path}: a regulation needs 'as_of' (YYYY-MM-DD)")
    source = meta.get("source")
    return Document(
        id=doc_id,
        kind=kind,
        title=title,
        as_of=as_of,
        source=str(source).strip() if source else None,
        body=strip_comments("\n".join(lines[end + 1 :])).strip(),
        path=path,
    )


def strip_comments(body: str) -> str:
    """Remove `<!-- ... -->` comments (editor notes such as TODO verify), multi-line included.

    Done before splitting, sizing and hashing, so notes are never indexed, read by the model
    or spoken. Fenced code blocks are left alone. Blank lines a comment leaves behind are
    collapsed.
    """
    out: list[str] = []
    run: list[str] = []
    in_fence = False

    def flush() -> None:
        text = _COMMENT.sub("", "\n".join(run))
        out.append(re.sub(r"\n{3,}", "\n\n", text))
        run.clear()

    for line in body.splitlines():
        if _FENCE.match(line):
            if not in_fence:
                flush()
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
        else:
            run.append(line)
    flush()
    return "\n".join(out)


def _parse_date(value: Any, path: Path) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):  # YAML turns 2026-01-01 into a date by itself
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise KnowledgeBaseContentError(
            f"{path}: 'as_of' must be YYYY-MM-DD, got {value!r}"
        ) from None


# --- Splitting ---


@dataclass
class _Unit:
    """A run of text under one heading, before size rules are applied."""

    section: str
    subsection: str
    text: str


@dataclass
class _Piece:
    section: str
    subsection: str
    text: str
    part: int = 1  # 1 for a whole unit, 2.. for later parts of a split long unit
    merged: bool = False


def _units(body: str) -> list[_Unit]:
    """Cut the body at `##` / `###` headings (ignoring '#' lines inside code fences)."""
    units: list[_Unit] = []
    section = ""
    subsection = ""
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            units.append(_Unit(section, subsection, text))
        buf.clear()

    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m is None:
            buf.append(line)
            continue
        flush()
        if len(m.group(1)) == 2:
            section, subsection = m.group(2), ""
        else:
            subsection = m.group(2)
    flush()
    return units


def _split_long(text: str) -> list[str]:
    """Cut text over MAX_WORDS into balanced parts at paragraph boundaries.

    A paragraph that is itself too long is cut at sentence ends, and a sentence that is
    still too long at a word count. Parts aim at equal size so the last one is not a stub.
    """
    total = _words(text)
    target = math.ceil(total / math.ceil(total / MAX_WORDS))
    atoms: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if _words(para) <= MAX_WORDS:
            atoms.append(para)
            continue
        for sentence in _SENTENCE_END.split(para):
            words = sentence.split()
            atoms.extend(
                " ".join(words[i : i + MAX_WORDS]) for i in range(0, len(words), MAX_WORDS)
            )

    parts: list[str] = []
    current: list[str] = []
    count = 0
    for atom in atoms:
        n = _words(atom)
        if current and (count + n > MAX_WORDS or count >= target):
            parts.append("\n\n".join(current))
            current, count = [], 0
        current.append(atom)
        count += n
    if current:
        parts.append("\n\n".join(current))
    return parts


def _heading_line(section: str, subsection: str) -> str:
    if subsection:
        return f"### {subsection}"
    return f"## {section}" if section else ""


def _fold(piece: _Piece, nxt: _Piece) -> None:
    """Append `nxt` to `piece`, keeping nxt's heading as a line of text."""
    own = "" if piece.merged or piece.part > 1 else _heading_line("", piece.subsection)
    heading = ""
    if nxt.part == 1:
        heading = _heading_line(nxt.section, nxt.subsection)
        if nxt.section != piece.section and nxt.subsection:
            # Folded across `##` sections: the `###` line alone would lose the section name.
            heading = "\n".join(p for p in (_heading_line(nxt.section, ""), heading) if p)
    piece.text = "\n\n".join(p for p in (own, piece.text, heading, nxt.text) if p)
    # The chunk is no longer one subsection.
    piece.subsection = ""
    piece.merged = True


def split_document(doc: Document) -> list[Chunk]:
    """Split one document into chunks with unique, stable ids."""
    # Group units by top-level section, so size rules prefer merging inside a section.
    groups: list[list[_Unit]] = []
    for unit in _units(doc.body):
        if not groups or groups[-1][0].section != unit.section:
            groups.append([])
        groups[-1].append(unit)

    pieces: list[_Piece] = []
    for group in groups:
        pieces.extend(_pack_group(group))

    # A section still short after packing joins the chunk before it, when it fits.
    merged: list[_Piece] = []
    for piece in pieces:
        if (
            merged
            and _words(piece.text) < MIN_WORDS
            and _words(merged[-1].text) + _words(piece.text) <= MAX_WORDS
        ):
            _fold(merged[-1], piece)
            continue
        merged.append(piece)

    if not merged:
        raise KnowledgeBaseContentError(f"{doc.path}: document has no content after front matter")

    chunks: list[Chunk] = []
    used: set[str] = set()
    for piece in merged:
        # A chunk that folded several subsections is named after its section only.
        subsection = "" if piece.merged else piece.subsection
        base = slugify(piece.section) or "intro"
        if subsection:
            base = f"{base}-{slugify(subsection)}"
        if piece.part > 1:
            base = f"{base}-{piece.part}"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        chunks.append(
            Chunk(
                id=f"{doc.id}#{slug}",
                doc_id=doc.id,
                kind=doc.kind,
                title=doc.title,
                section=piece.section,
                subsection=subsection,
                text=piece.text,
                as_of=doc.as_of,
                source=doc.source,
            )
        )
    return chunks


def _pack_group(group: list[_Unit]) -> list[_Piece]:
    """Size rules inside one `##` section: split long units, fold short ones."""
    pieces: list[_Piece] = []
    for unit in group:
        if _words(unit.text) > MAX_WORDS:
            for i, part in enumerate(_split_long(unit.text), start=1):
                pieces.append(_Piece(unit.section, unit.subsection, part, part=i))
        else:
            pieces.append(_Piece(unit.section, unit.subsection, unit.text))

    packed: list[_Piece] = []
    for piece in pieces:
        if (
            packed
            and (_words(packed[-1].text) < MIN_WORDS or _words(piece.text) < MIN_WORDS)
            and _words(packed[-1].text) + _words(piece.text) <= MAX_WORDS
            and piece.part == 1
        ):
            _fold(packed[-1], piece)
            continue
        packed.append(piece)
    return packed
