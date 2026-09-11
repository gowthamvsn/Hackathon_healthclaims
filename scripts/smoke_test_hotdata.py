"""Smoke test — hotdata.dev query layer: create the claims table, load one
row, run a SQL aggregate. Requires HOTDATA_API_KEY in .env."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from query_layer import hotdata_query
from scripts.smoke_common import run_smoke


async def _check() -> str:
    client = hotdata_query.make_client()
    db = hotdata_query.ensure_claims_table(client)
    hotdata_query.load_claims(
        client, db, [{"paper_id": "smoke", "claim": "test claim", "topic": "smoke", "confidence": 1.0}]
    )
    result = hotdata_query.topic_trend_query(client, db, topic_like="%smoke%")
    return f"loaded 1 row, ran topic trend SQL, got: {str(result)[:120]}"


async def main():
    result = await run_smoke("hotdata.dev (live query)", _check)
    print(f"[{result.status}] {result.layer}: {result.message} ({result.seconds:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
