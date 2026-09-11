"""Smoke test — Modiqo Rote muscle-memory layer: record a fake task once,
then confirm the second run replays instead of re-executing. No API key
needed — also reports whether the real `rote` CLI is on PATH."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from muscle_memory.rote_hook import RotePlay, rote_cli_available, task_signature, _load_ledger, _save_ledger
from scripts.smoke_common import run_smoke

calls = {"n": 0}


def _expensive_step():
    calls["n"] += 1
    return {"value": 42}


async def _check() -> str:
    calls["n"] = 0

    # Smoke test must be idempotent across repeated invocations: clear any
    # ledger entry left over from a previous run of this same smoke test.
    ledger = _load_ledger()
    ledger.pop(task_signature("smoke_test_task", "smoke-key"), None)
    _save_ledger(ledger)

    play = RotePlay("smoke_test_task")

    first = await play.run(["smoke-key"], _expensive_step)
    second = await play.run(["smoke-key"], _expensive_step)

    if calls["n"] != 1:
        raise AssertionError(f"expected exactly 1 real execution, got {calls['n']}")
    if first["replayed"] or not second["replayed"]:
        raise AssertionError(f"expected run1 fresh + run2 replayed, got {first['replayed']=} {second['replayed']=}")

    cli = "found on PATH" if rote_cli_available() else "NOT on PATH — install per hackathon setup checklist"
    return f"run1 executed, run2 replayed ({second['elapsed_seconds']*1000:.2f}ms); rote CLI: {cli}"


async def main():
    result = await run_smoke("Modiqo Rote (muscle memory)", _check)
    print(f"[{result.status}] {result.layer}: {result.message} ({result.seconds:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
