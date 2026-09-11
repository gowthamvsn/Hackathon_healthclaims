"""Smoke test — HydraDB storage layer: ingest one tiny document, then a
hybrid query for it. Requires HYDRADB_API_KEY in .env."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage_layer import hydra_store
from scripts.smoke_common import run_smoke


async def _check() -> str:
    client = hydra_store.make_client()
    database = "smoke_test_db"
    text = "HydraDB stores the graph Cognee constructs, durably, across sessions."

    out = hydra_store.persist_paper_graph(client, database, text, {"source": "smoke_test"})
    result = hydra_store.recall(client, database, "What does HydraDB store?")
    return f"ingested doc_id={out['doc_id']}, query returned a result object"


async def main():
    result = await run_smoke("HydraDB (storage)", _check)
    print(f"[{result.status}] {result.layer}: {result.message} ({result.seconds:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
