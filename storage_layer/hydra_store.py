"""Memory Storage & Serving Layer — HydraDB

Durable, cross-session home for the research graph Cognee builds. Snapshot
-consistent, multi-hop, relationship-aware retrieval (not flat similarity
search) — this is what lets run 3 answer "have we already seen this claim?"
without re-asking an LLM.

Confirmed against the installed `hydradb-sdk` 2.1.4 package (see
SETUP_NOTES.md) — `client.context.ingest(...)` and `client.query(...)` are
real bound methods on `hydra_db.HydraDB`, not guesses.
"""
import hashlib
import os

from hydra_db import HydraDB

from agent.config import require_env


def make_client() -> HydraDB:
    return HydraDB(
        token=require_env("HYDRADB_API_KEY"),
        base_url=os.environ.get("HYDRADB_BASE_URL") or "https://api.hydradb.com",
    )


def content_id(text: str) -> str:
    """Stable id for a source document — used to detect "have we stored this
    before" without a round trip through Cognee's LLM extraction."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def ensure_database(client: HydraDB, database: str):
    """HydraDB requires a database/tenant to exist before you can ingest into
    it — `context.ingest` returns 404 DATABASE_NOT_FOUND otherwise. Create it
    on first use; a second call is a harmless no-op (already-exists errors
    are swallowed)."""
    try:
        client.databases.create(database=database)
    except Exception:
        pass  # already exists, or created by a concurrent run — fine either way


def persist_paper_graph(
    client: HydraDB,
    database: str,
    text: str,
    metadata: dict,
    collection: str = "papers",
) -> dict:
    """Store one paper's raw text + metadata as a knowledge-graph source.

    `upsert="true"` makes repeat runs on the same paper idempotent — this is
    what run 2/3 hits instead of re-extracting from scratch.
    """
    doc_id = content_id(text)
    ensure_database(client, database)
    result = client.context.ingest(
        database=database,
        collection=collection,
        type="knowledge",
        documents=(f"{doc_id}.txt", text.encode("utf-8"), "text/plain"),
        # API requires an array (one entry per document); custom fields must
        # nest under "additional_metadata" — top-level keys are a fixed set.
        document_metadata=_json([{"id": doc_id, "additional_metadata": metadata}]),
        upsert="true",
    )
    return {"doc_id": doc_id, "result": result}


def has_seen(client: HydraDB, database: str, text: str, collection: str = "papers") -> bool:
    """Cheap existence check — this is the read that makes run 2/3 fast:
    a single indexed lookup instead of an LLM extraction pass.

    Response shape confirmed against the live API: `context.list()` returns
    HandlerEnvelopeListV2ListResponse(data=ListV2ListResponse(sources=[...],
    pagination=...)) — sources, not data/items directly.
    """
    doc_id = content_id(text)
    try:
        listing = client.context.list(
            database=database,
            collection=collection,
            ids=[doc_id],
            type="knowledge",
        )
        sources = getattr(getattr(listing, "data", None), "sources", None) or []
        return len(sources) > 0
    except Exception:
        return False


def list_paper_titles(client: HydraDB, database: str, collection: str = "papers") -> list[str]:
    """All titles actually primed into this database — the ground truth
    allowlist for "is this source really from our corpus, or did the LLM
    make it up from outside knowledge?" checks."""
    try:
        listing = client.context.list(database=database, collection=collection, type="knowledge")
        sources = getattr(getattr(listing, "data", None), "sources", None) or []
        titles = []
        for s in sources:
            meta = getattr(s, "additional_metadata", None) or {}
            title = meta.get("title")
            if title:
                titles.append(title)
        return titles
    except Exception:
        return []


def recall(client: HydraDB, database: str, query: str, collection: str = "papers", max_results: int = 10):
    """Relationship-aware recall: hybrid graph + vector retrieval over the
    durable store, for "what changed", "who claims what", "what's blocking
    this" style questions."""
    return client.query(
        query=query,
        database=database,
        collection=collection,
        type="knowledge",
        query_by="hybrid",
        graph_context=True,
        max_results=max_results,
    )


def _json(obj: dict) -> str:
    import json

    return json.dumps(obj)
