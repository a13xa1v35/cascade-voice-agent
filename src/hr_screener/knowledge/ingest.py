"""Idempotent sync of the markdown knowledge base into Qdrant, plus its command line.

`sync_chunks` is the one code path, run at server startup (`service.open_knowledge_base`) and
by `make ingest`:

1. Read what the collection already holds (chunk id and content hash per point).
2. Embed only chunks that are new or whose content hash changed, in batches, and upsert them.
3. Delete points whose chunk no longer exists.
4. Compute `kb_version` (sha256 over the sorted chunk hashes), write it to the payload of
   every point (points that did not change get a cheap payload update) and return a report.

A second sync with no content change makes no embedding call. The content hash includes the
embedding model, the dimension and the sparse encoder, so changing any of them re-embeds
everything without extra bookkeeping. An empty chunk list is refused: it would delete the
whole index (a mistyped KB_DIR must not do that).

Embedded Qdrant takes an exclusive lock on its folder, so `make ingest` fails while a server
holds it; the CLI says so. Stop the server (it syncs by itself at startup) or point
QDRANT_URL at a Qdrant server, where a separate ingestion job is the production setup.
"""

import argparse
import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from hr_screener.knowledge.chunking import Chunk, kb_version, load_chunks, point_id
from hr_screener.knowledge.types import KnowledgeBaseContentError, KnowledgeError, SyncReport

if TYPE_CHECKING:
    from hr_screener.knowledge.store import QdrantKnowledgeBase

log = logging.getLogger(__name__)

BATCH_SIZE = 64


async def sync_chunks(
    kb: "QdrantKnowledgeBase", chunks: list[Chunk], *, batch_size: int = BATCH_SIZE
) -> SyncReport:
    if not chunks:
        raise KnowledgeBaseContentError("refusing to sync zero chunks (it would empty the index)")
    ids = [c.id for c in chunks]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise KnowledgeBaseContentError(f"duplicate chunk ids: {', '.join(dupes)}")

    recreated = await kb.prepare_for_sync()
    stored = {} if recreated else await kb.stored_points()

    hashes = {point_id(c.id): c.content_hash(kb.fingerprint) for c in chunks}
    version = kb_version(list(hashes.values()))

    todo: list[Chunk] = []
    added = updated = 0
    for c in chunks:
        existing = stored.get(point_id(c.id))
        if existing is None:
            added += 1
            todo.append(c)
        elif existing.content_hash != hashes[point_id(c.id)]:
            updated += 1
            todo.append(c)
    stale = [pid for pid in stored if pid not in hashes]
    unchanged = len(chunks) - added - updated

    embed_calls = 0
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        texts = [c.indexed_text for c in batch]
        dense = await kb.embedder.embed_documents(texts)
        embed_calls += 1
        if len(dense) != len(batch) or any(len(v) != kb.embedder.dim for v in dense):
            raise KnowledgeError(
                f"embedder returned vectors that do not match {len(batch)} texts x "
                f"{kb.embedder.dim} dims"
            )
        sparse = await asyncio.to_thread(kb.sparse.embed_documents, texts)
        await kb.upsert(batch, [hashes[point_id(c.id)] for c in batch], dense, sparse, version)
        log.info("ingested %d/%d changed chunks", min(i + batch_size, len(todo)), len(todo))

    if stale:
        await kb.delete(stale)
    changed = {point_id(c.id) for c in todo}
    relabel = [
        pid
        for pid, p in stored.items()
        if pid in hashes and pid not in changed and p.kb_version != version
    ]
    if relabel:
        await kb.set_kb_version(relabel, version)
    await kb.record_model()
    kb.remember_version(version)
    return SyncReport(
        added=added,
        updated=updated,
        deleted=len(stale),
        unchanged=unchanged,
        kb_version=version,
        embed_calls=embed_calls,
    )


# --- Command line ---


async def _run(kb_dir: str | None) -> int:
    from hr_screener.config import Settings
    from hr_screener.knowledge.embeddings import make_embedder, make_sparse_encoder
    from hr_screener.knowledge.store import QdrantKnowledgeBase, make_client

    settings = Settings()
    try:
        chunks = load_chunks(kb_dir or settings.kb_dir)
        embedder = make_embedder(settings)
        sparse = await asyncio.to_thread(make_sparse_encoder, settings)
        client = make_client(settings)
    except KnowledgeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    kb = QdrantKnowledgeBase(
        client,
        embedder,
        sparse,
        collection=settings.qdrant_collection,
        min_score=settings.kb_min_score,
        payload_index=bool(settings.qdrant_url),
    )
    try:
        report = await kb.sync(chunks)
    except KnowledgeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: sync failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        await kb.close()
    print(f"{len(chunks)} chunks from {kb_dir or settings.kb_dir}: {report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hr_screener.knowledge.ingest",
        description=(
            "Sync the markdown knowledge base (KB_DIR) into Qdrant: embed new and changed "
            "chunks, delete removed ones. Settings come from the environment / .env. With "
            "embedded Qdrant, stop the server first (the folder is locked); the server also "
            "syncs by itself at startup."
        ),
    )
    parser.add_argument("--dir", help="knowledge directory (default: KB_DIR)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return asyncio.run(_run(args.dir))


if __name__ == "__main__":
    raise SystemExit(main())
