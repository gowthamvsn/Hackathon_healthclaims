"""Runs a smoke test for every mandated layer and prints one summary table.
Usage: python scripts/run_smoke_tests.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_layer import cognee_memory  # noqa: F401  (import-order guard, unused directly)
from agent.config import MissingCredential
from scripts.smoke_common import run_smoke


async def _cognee_check() -> str:
    import os
    from memory_layer import cognee_memory

    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        raise MissingCredential("LLM_API_KEY or OPENAI_API_KEY")
    dataset = "smoke_test_dataset"
    info = await cognee_memory.ingest_source(
        "The Transformer architecture relies entirely on attention mechanisms.",
        dataset_name=dataset,
    )
    results = await cognee_memory.recall_claims("What does the Transformer rely on?", dataset)
    return f"cognify took {info['cognify_seconds']:.2f}s, recalled {len(results)} result(s)"


async def _hydradb_check() -> str:
    from storage_layer import hydra_store

    client = hydra_store.make_client()
    database = "smoke_test_db"
    text = "HydraDB stores the graph Cognee constructs, durably, across sessions."
    out = hydra_store.persist_paper_graph(client, database, text, {"source": "smoke_test"})
    hydra_store.recall(client, database, "What does HydraDB store?")
    return f"ingested doc_id={out['doc_id']}"


async def _hotdata_check() -> str:
    from query_layer import hotdata_query

    client = hotdata_query.make_client()
    db = hotdata_query.ensure_claims_table(client)
    hotdata_query.load_claims(
        client, db, [{"paper_id": "smoke", "claim": "test claim", "topic": "smoke", "confidence": 1.0}]
    )
    result = hotdata_query.topic_trend_query(client, db, topic_like="%smoke%")
    return f"ran topic trend SQL, got: {str(result)[:80]}"


async def _rocketride_check() -> str:
    from orchestration_layer.rocketride_orchestrator import RocketRideOrchestrator, make_client

    client = make_client()
    orchestrator = RocketRideOrchestrator(client)
    connected = await orchestrator.connect()
    action = await orchestrator.decide_and_act(
        already_seen=False, paper_id="smoke", claims=["test claim"], topic_stats={}
    )
    return f"connected={connected}, executed_via={action['executed_via']}"


async def _rote_check() -> str:
    from muscle_memory.rote_hook import RotePlay, rote_cli_available, task_signature, _load_ledger, _save_ledger

    calls = {"n": 0}

    def step():
        calls["n"] += 1
        return {"value": 42}

    ledger = _load_ledger()
    ledger.pop(task_signature("smoke_test_task", "smoke-key"), None)
    _save_ledger(ledger)

    play = RotePlay("smoke_test_task")
    first = await play.run(["smoke-key"], step)
    second = await play.run(["smoke-key"], step)
    if calls["n"] != 1 or first["replayed"] or not second["replayed"]:
        raise AssertionError("replay semantics broken")
    cli = "on PATH" if rote_cli_available() else "NOT on PATH"
    return f"run1 executed, run2 replayed in {second['elapsed_seconds']*1000:.2f}ms; rote CLI {cli}"


async def main():
    checks = [
        ("Cognee.ai (memory)", _cognee_check),
        ("HydraDB (storage)", _hydradb_check),
        ("hotdata.dev (live query)", _hotdata_check),
        ("RocketRide.ai (orchestration)", _rocketride_check),
        ("Modiqo Rote (muscle memory)", _rote_check),
    ]

    results = []
    for layer, fn in checks:
        results.append(await run_smoke(layer, fn))

    print()
    print(f"{'LAYER':<32} {'STATUS':<6} {'TIME':>7}  MESSAGE")
    print("-" * 100)
    for r in results:
        print(f"{r.layer:<32} {r.status:<6} {r.seconds:>6.2f}s  {r.message}")
    print()

    n_pass = sum(1 for r in results if r.status == "PASS")
    n_skip = sum(1 for r in results if r.status == "SKIP")
    n_fail = sum(1 for r in results if r.status == "FAIL")
    print(f"{n_pass} passed, {n_skip} skipped (missing keys), {n_fail} failed")

    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
