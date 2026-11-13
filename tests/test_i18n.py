"""Catalog hygiene for the gettext/Babel layer: a missing, stale or incomplete translation
fails here, not on a live call in that language."""

import io
from pathlib import Path

import pytest
from babel.messages.extract import DEFAULT_KEYWORDS, extract_from_file
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from hr_screener import i18n
from hr_screener.i18n import LANGS

LOCALE_DIR = Path(i18n.__file__).parent / "locale"
POT = LOCALE_DIR / "messages.pot"


def read_catalog(path: Path):
    with path.open("rb") as fh:
        return read_po(fh, locale=path.parent.parent.name if path.suffix == ".po" else None)


def po_files() -> list[Path]:
    return sorted(LOCALE_DIR.glob("*/LC_MESSAGES/messages.po"))


def test_every_supported_language_but_english_has_a_catalog():
    assert [p.parent.parent.name for p in po_files()] == [lang for lang in LANGS if lang != "en"]


@pytest.mark.parametrize("po_path", po_files(), ids=lambda p: p.parent.parent.name)
def test_the_mo_is_the_compiled_po(po_path: Path):
    buffer = io.BytesIO()
    write_mo(buffer, read_catalog(po_path))
    assert po_path.with_suffix(".mo").read_bytes() == buffer.getvalue(), (
        "stale messages.mo: run `make compile-messages`"
    )


@pytest.mark.parametrize("po_path", po_files(), ids=lambda p: p.parent.parent.name)
def test_the_po_is_complete_and_in_sync_with_the_pot(po_path: Path):
    po = read_catalog(po_path)
    template = read_catalog(POT)
    wanted = {(m.context, m.id) for m in template if m.id}
    have = {(m.context, m.id) for m in po if m.id}
    assert wanted == have, f"run `make messages`: missing {wanted - have}, stale {have - wanted}"
    for message in po:
        if not message.id:
            continue
        assert not message.fuzzy, f"fuzzy translation: {message.id!r}"
        strings = message.string if isinstance(message.string, tuple) else (message.string,)
        assert all(s.strip() for s in strings), f"empty translation: {message.id!r}"
        assert len(strings) == po.num_plurals if message.pluralizable else len(strings) == 1


def test_the_pot_matches_the_source():
    """`make messages` was run after the last change to a translatable string."""
    extracted = extract_from_file(
        "python", Path(i18n.__file__), keywords=DEFAULT_KEYWORDS, comment_tags=("Translators:",)
    )
    found = {(context, _first(message)) for _line, message, _comments, context in extracted}
    template = {(m.context, _first(m.id)) for m in read_catalog(POT) if m.id}
    assert found == template, "run `make messages`"


def _first(msgid: str | tuple[str, ...]) -> str:
    return msgid if isinstance(msgid, str) else msgid[0]
