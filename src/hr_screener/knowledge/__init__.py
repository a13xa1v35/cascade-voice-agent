"""Knowledge base (RAG) for Sofia: markdown documents -> chunks -> hybrid search in Qdrant.

Design: "The knowledge base is an async tool" in the README.
Public API (import from the submodules):

Startup (the app calls this once; it never raises, see `service`)::

    kb = await open_knowledge_base(settings, redis=redis)   # service.py
    ...
    await kb.close()                                         # on shutdown

Search (`store.KnowledgeBase` protocol; the query is written in KB_LANGUAGE)::

    result = await kb.search(query, k=settings.kb_top_k)     # -> types.SearchResult
    result.hits          # list[Hit]: id, doc_id, kind, title, section, text, as_of, source
    result.no_match      # best dense cosine < KB_MIN_SCORE, or nothing found
    result.kb_version    # which knowledge base version answered
    # raises KnowledgeUnavailable (no key, empty or mismatched index) or any Embedding/Qdrant
    # error: the tool maps all of them to `kb_unavailable`, under asyncio.timeout.

Ingestion::

    chunks = load_chunks(settings.kb_dir)                    # chunking.py
    report = await kb.sync(chunks)                           # -> types.SyncReport
    make ingest                                              # same, from the command line

Modules: `chunking` (markdown -> Chunk), `embeddings` (Embedder / SparseEncoder protocols,
OpenAI, Voyage, local and fake implementations), `store` (Qdrant), `ingest` (sync + CLI), `cache`
(Redis query-embedding cache), `service` (startup factory), `types` (results and errors).
"""
