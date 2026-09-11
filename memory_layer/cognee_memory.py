"""Memory Construction Layer — Cognee.ai

Runs the ECL (Extract, Cognify, Load) pipeline over raw paper/article text:
add() ingests raw text, cognify() extracts entities/relationships (claims,
sources, contradictions) into a knowledge graph, search() queries that graph.

Confirmed against the installed `cognee` 1.5.4 package (see SETUP_NOTES.md).

Runs against **Cognee Cloud**, not local self-hosted extraction: `add`,
`cognify`, and `search` all check a module-level remote-client singleton
(`cognee.api.v1.serve.state`) and transparently route to the connected cloud
tenant once `cognee.serve(url=..., api_key=...)` has been called — confirmed
by reading `add.py`/`cognify.py`/`search.py` directly, not assumed. This is
why no LLM_API_KEY/embedding config is needed here: the cloud tenant handles
extraction + embeddings itself.
"""
import os
import time

import cognee
from cognee import SearchType

_connected = False


async def connect():
    """Idempotent: connects this process to the Cognee Cloud tenant once.
    Uses COGNEE_SERVICE_URL (the tenant's API base URL from
    platform.cognee.ai -> API Keys -> Connection Details) + COGNEE_API_KEY."""
    global _connected
    if _connected:
        return
    service_url = os.environ.get("COGNEE_SERVICE_URL")
    api_key = os.environ.get("COGNEE_API_KEY")
    if service_url and api_key:
        await cognee.serve(url=service_url, api_key=api_key)
    _connected = True


async def ingest_source(text: str, dataset_name: str) -> dict:
    """Extract, Cognify, Load one paper/article into Cognee's knowledge graph.

    Returns timing + a rough token/LLM-call proxy so the compounding-proof
    benchmark can show run 1 (cold) vs. later runs (warm) doing real work.
    """
    await connect()
    t0 = time.perf_counter()
    await cognee.add(text, dataset_name=dataset_name)
    add_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    await cognee.cognify(datasets=[dataset_name])
    cognify_s = time.perf_counter() - t1

    return {
        "dataset_name": dataset_name,
        "add_seconds": add_s,
        "cognify_seconds": cognify_s,
        "total_seconds": add_s + cognify_s,
        "did_extract": True,
    }


async def recall_claims(query: str, dataset_name: str, top_k: int = 10) -> list[dict]:
    """Relationship-aware recall over the knowledge graph Cognee built.

    GRAPH_COMPLETION walks the entity/relationship graph (claims <-> sources
    <-> contradictions) instead of flat similarity search.
    """
    await connect()
    results = await cognee.search(
        query_text=query,
        query_type=SearchType.GRAPH_COMPLETION,
        datasets=[dataset_name],
        top_k=top_k,
    )
    return [r.model_dump() if hasattr(r, "model_dump") else r for r in results]


async def find_contradictions(dataset_name: str, top_k: int = 10) -> list[dict]:
    """Ask Cognee's graph directly for conflicting claims within a dataset."""
    await connect()
    results = await cognee.search(
        query_text="What claims in this dataset contradict each other, and why?",
        query_type=SearchType.GRAPH_COMPLETION,
        datasets=[dataset_name],
        top_k=top_k,
    )
    return [r.model_dump() if hasattr(r, "model_dump") else r for r in results]
