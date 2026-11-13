"""Knowledge-base retrieval eval CLI.

    uv run python -m evals.kb.run                    # EMBEDDING_PROVIDER from settings
    uv run python -m evals.kb.run --provider local   # no key needed (fallback model)
    make eval-kb PROVIDER=local K=4

Builds the index from KB_DIR into an in-memory Qdrant (never QDRANT_PATH, which the running
server locks), runs every golden question as `query_es` and as the raw `question` in hybrid,
dense-only and BM25-only mode, and writes `evals/results/kb/<timestamp>/` (report.md,
runs.jsonl). Document and query vectors are cached under var/kb_eval_cache/ by model and text,
so a rerun makes no embedding calls. With `openai` or `voyage` the first run calls
that provider's API.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from evals.kb.embed_cache import DEFAULT_CACHE_DIR, CachedEmbedder
from evals.kb.golden import GOLDEN_PATH, GoldenItem, load_golden, unknown_expected
from evals.kb.report import ReportMeta, ks_for, render_report
from evals.kb.retrieval import QueryRecord, build_index, run_queries
from hr_screener.config import Settings
from hr_screener.knowledge.chunking import Chunk, load_chunks
from hr_screener.knowledge.embeddings import (
    Embedder,
    SparseEncoder,
    make_embedder,
    make_sparse_encoder,
)
from hr_screener.knowledge.types import KnowledgeError

RESULTS_ROOT = Path(__file__).parent.parent / "results" / "kb"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument(
        "--provider", choices=["openai", "voyage", "local"], help="override the setting"
    )
    parser.add_argument("--k", type=int, help="results the app returns (default KB_TOP_K)")
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--kb-dir", help="knowledge directory (default KB_DIR)")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--no-cache", action="store_true", help="do not read or write the cache")
    return parser.parse_args(argv)


def check_golden(items: list[GoldenItem], chunks: list[Chunk]) -> None:
    """Exit with the full list of expected ids that do not exist in the knowledge base."""
    bad = unknown_expected(items, [c.id for c in chunks])
    if bad:
        lines = [f"  {iid}: {', '.join(ids)}" for iid, ids in bad.items()]
        known = ", ".join(sorted(c.id for c in chunks))
        raise SystemExit(
            "golden.yaml expects chunk ids that do not exist (chunk ids depend on how the "
            "chunker merges sections):\n" + "\n".join(lines) + f"\nknown ids: {known}"
        )


async def run_eval(
    items: list[GoldenItem],
    chunks: list[Chunk],
    embedder: Embedder,
    sparse: SparseEncoder,
    *,
    depth: int,
) -> list[QueryRecord]:
    kb = await build_index(chunks, embedder, sparse)
    try:
        return await run_queries(kb, items, depth)
    finally:
        await kb.close()


def write_results(
    records: list[QueryRecord], meta: ReportMeta, results_dir: Path | None = None
) -> Path:
    results_dir = results_dir or RESULTS_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    results_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r.to_json(), ensure_ascii=False) for r in records]
    (results_dir / "runs.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (results_dir / "report.md").write_text(render_report(records, meta), encoding="utf-8")
    return results_dir / "report.md"


async def main_async(args: argparse.Namespace) -> Path:
    settings = Settings()
    if args.provider:
        settings = settings.model_copy(update={"embedding_provider": args.provider})
    k = args.k or settings.kb_top_k
    items = load_golden(args.golden)
    try:
        chunks = load_chunks(args.kb_dir or settings.kb_dir)
        check_golden(items, chunks)
        inner = make_embedder(settings)
        sparse = await asyncio.to_thread(make_sparse_encoder, settings)
    except KnowledgeError as e:
        raise SystemExit(f"error: {e}") from e
    embedder = CachedEmbedder(inner, None if args.no_cache else args.cache_dir)
    started = datetime.now()
    try:
        records = await run_eval(items, chunks, embedder, sparse, depth=max(ks_for(k)))
    finally:
        embedder.flush()
    meta = ReportMeta(
        started=started.isoformat(timespec="seconds"),
        args=" ".join(sys.argv[1:]) or "(defaults)",
        provider=settings.embedding_provider,
        model=embedder.model,
        dim=embedder.dim,
        kb_dir=args.kb_dir or settings.kb_dir,
        n_chunks=len(chunks),
        min_score=settings.kb_min_score,
        k=k,
        stats=embedder.stats,
        cache="off" if args.no_cache else str(args.cache_dir),
    )
    return write_results(records, meta, RESULTS_ROOT / started.strftime("%Y%m%d-%H%M%S"))


def main(argv: list[str] | None = None) -> None:
    path = asyncio.run(main_async(parse_args(argv)))
    print(f"\nreport: {path}")


if __name__ == "__main__":
    main()
