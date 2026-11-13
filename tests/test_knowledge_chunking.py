"""Chunk ids are unique and stable, so a sync updates points instead of duplicating them."""

from knowledge_support import section, write_doc

from hr_screener.knowledge.chunking import (
    load_chunks,
)

# --- front matter ---


# --- splitting ---


def test_chunk_ids_are_unique_and_stable(tmp_path):
    body = section("Igual", 200, "a") + section("Igual", 200, "b") + section("Otra", 200, "c")
    write_doc(tmp_path, "pagos", body)
    write_doc(tmp_path, "otro", section("Igual", 200, "d"))
    ids = [c.id for c in load_chunks(tmp_path)]
    assert len(set(ids)) == len(ids) == 4
    assert "pagos#igual" in ids
    assert "pagos#igual-2" in ids
    assert "otro#igual" in ids
    assert ids == [c.id for c in load_chunks(tmp_path)]  # stable across loads


# --- hashes ---


# --- HTML comments ---
