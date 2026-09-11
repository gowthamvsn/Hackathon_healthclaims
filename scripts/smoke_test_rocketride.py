"""Smoke test — RocketRide orchestration layer: authenticate and pull the
dashboard. Requires ROCKETRIDE_API_KEY (and ROCKETRIDE_ENGINE_URL) in .env."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration_layer.rocketride_orchestrator import RocketRideOrchestrator, make_client
from scripts.smoke_common import run_smoke


async def _check() -> str:
    client = make_client()
    orchestrator = RocketRideOrchestrator(client)
    connected = await orchestrator.connect()
    action = await orchestrator.decide_and_act(
        already_seen=False, paper_id="smoke", claims=["test claim"], topic_stats={}
    )
    return f"connected={connected}, action executed_via={action['executed_via']}"


async def main():
    result = await run_smoke("RocketRide (orchestration)", _check)
    print(f"[{result.status}] {result.layer}: {result.message} ({result.seconds:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
