"""Smoke test — Cognee memory layer: add -> cognify -> search on one tiny
snippet. Requires LLM_API_KEY (or OPENAI_API_KEY) in .env."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.config import MissingCredential
from memory_layer import cognee_memory
from scripts.smoke_common import run_smoke


async def _check() -> str:
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        raise MissingCredential("LLM_API_KEY or OPENAI_API_KEY")

    dataset = "smoke_test_dataset"
    info = await cognee_memory.ingest_source(
        "The Transformer architecture relies entirely on attention mechanisms, "
        "with no recurrence or convolution.",
        dataset_name=dataset,
    )
    results = await cognee_memory.recall_claims("What does the Transformer rely on?", dataset)
    return f"cognify took {info['cognify_seconds']:.2f}s, recalled {len(results)} result(s)"


async def main():
    result = await run_smoke("Cognee (memory)", _check)
    print(f"[{result.status}] {result.layer}: {result.message} ({result.seconds:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
