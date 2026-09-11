"""Prime the demo corpus: ingest every paper in data/health_papers/ through
Cognee (extract + cognify) and persist it in HydraDB.

This is "run 1, cold" for the claim-checker demo — real Cognee Cloud calls,
real HydraDB writes. Run once before the demo so the graph is warm; the demo
itself only ever queries it (fast) via agent/claim_checker.py.

Usage: .venv/Scripts/python.exe scripts/prime_corpus.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_layer import cognee_memory
from storage_layer import hydra_store

CORPUS_DIR = Path(__file__).parent.parent / "data" / "health_papers"
DATASET_NAME = "health_papers"
HYDRA_DATABASE = "research_assistant"


async def main():
    paper_paths = sorted(CORPUS_DIR.glob("*.txt"))
    if not paper_paths:
        print(f"No papers found in {CORPUS_DIR}")
        return

    hydra = hydra_store.make_client()
    hydra_store.ensure_database(hydra, HYDRA_DATABASE)

    print(f"Priming {len(paper_paths)} papers into dataset '{DATASET_NAME}'...\n")
    total_t0 = time.perf_counter()

    for path in paper_paths:
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].removeprefix("Title:").strip()

        if hydra_store.has_seen(hydra, HYDRA_DATABASE, text):
            print(f"  [skip] {path.name} — already primed")
            continue

        t0 = time.perf_counter()
        info = await cognee_memory.ingest_source(text, DATASET_NAME)
        hydra_store.persist_paper_graph(
            hydra, HYDRA_DATABASE, text, {"topic": "health_nutrition", "dataset": DATASET_NAME, "title": title}
        )
        elapsed = time.perf_counter() - t0
        print(f"  [ok]   {path.name} — {elapsed:.2f}s — {title[:70]}")

    total_elapsed = time.perf_counter() - total_t0
    print(f"\nDone in {total_elapsed:.2f}s.")


if __name__ == "__main__":
    asyncio.run(main())
