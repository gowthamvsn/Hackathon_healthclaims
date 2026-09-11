"""Self-Improving Research Assistant — full pipeline.

Cognee turns raw paper text into structured memory -> HydraDB stores/serves
that memory durably -> hotdata.dev adds fast ad-hoc analytics over the
claims it produced -> RocketRide decides + executes the next action ->
Modiqo Rote captures what worked so repeat runs replay instead of
rediscovering. The loop compounds.
"""
import os
import time

from memory_layer import cognee_memory
from storage_layer import hydra_store
from query_layer import hotdata_query
from orchestration_layer.rocketride_orchestrator import RocketRideOrchestrator, make_client as make_rocketride_client
from muscle_memory.rote_hook import RotePlay


class ResearchAssistantAgent:
    def __init__(self):
        self.database = os.environ.get("HYDRADB_DATABASE", "research_assistant")
        self.hydra = hydra_store.make_client()
        self.hotdata = hotdata_query.make_client()
        self.hotdata_db = hotdata_query.ensure_claims_table(self.hotdata)
        self.orchestrator = RocketRideOrchestrator(make_rocketride_client())
        self._rocketride_connected = False
        self._rocketride_error: str | None = None

    async def process_paper(self, text: str, dataset_name: str, topic: str) -> dict:
        run_started = time.perf_counter()
        stage_timings: dict[str, float] = {}

        if not self._rocketride_connected:
            try:
                self._rocketride_connected = await self.orchestrator.connect()
            except Exception as exc:
                self._rocketride_connected = False
                self._rocketride_error = str(exc)

        # --- Memory: Cognee extract, gated by HydraDB's "have we seen this" check ---
        rote_extract = RotePlay("ingest_and_extract")
        extract_play = await rote_extract.run(
            [hydra_store.content_id(text), dataset_name],
            self._extract_and_store,
            text,
            dataset_name,
            topic,
        )
        stage_timings["extract"] = extract_play["elapsed_seconds"]
        claims = extract_play["result"]["claims"]

        # --- Insight: hotdata ad-hoc analytics over what's been extracted so far ---
        rote_analytics = RotePlay("topic_analytics")
        analytics_play = await rote_analytics.run(
            [topic],
            self._load_and_query_trend,
            topic,
            claims,
        )
        stage_timings["analytics"] = analytics_play["elapsed_seconds"]
        topic_stats = analytics_play["result"]

        # --- Motion: RocketRide decides + executes (runs every time — the decision
        #     itself is what should get cheaper, since it can see "already seen") ---
        t0 = time.perf_counter()
        action_result = await self.orchestrator.decide_and_act(
            already_seen=not extract_play["result"]["cognify_ran"],
            paper_id=hydra_store.content_id(text),
            claims=claims,
            topic_stats=topic_stats,
        )
        stage_timings["orchestrate"] = time.perf_counter() - t0

        return {
            "dataset_name": dataset_name,
            "claims_found": len(claims) if isinstance(claims, list) else None,
            "replayed_extract": extract_play["replayed"],
            "replayed_analytics": analytics_play["replayed"],
            "rocketride_connected": self._rocketride_connected,
            "rocketride_error": self._rocketride_error,
            "action": action_result,
            "stage_timings_seconds": stage_timings,
            "total_seconds": time.perf_counter() - run_started,
        }

    async def _extract_and_store(self, text: str, dataset_name: str, topic: str) -> dict:
        seen = hydra_store.has_seen(self.hydra, self.database, text)
        if seen:
            claims = await cognee_memory.recall_claims(
                f"Summarize the key claims about {topic}", dataset_name
            )
            return {"claims": claims, "cognify_ran": False}

        cognify_info = await cognee_memory.ingest_source(text, dataset_name)
        claims = await cognee_memory.recall_claims(
            f"Summarize the key claims about {topic}", dataset_name
        )
        hydra_store.persist_paper_graph(
            self.hydra, self.database, text, {"topic": topic, "dataset": dataset_name}
        )
        return {"claims": claims, "cognify_ran": True, "cognify_info": cognify_info}

    async def _load_and_query_trend(self, topic: str, claims: list) -> dict:
        rows = [
            {
                "paper_id": hydra_store.content_id(str(c)),
                "claim": str(c)[:500],
                "topic": topic,
                "confidence": 1.0,
            }
            for c in (claims or [])
        ] or [{"paper_id": "none", "claim": "", "topic": topic, "confidence": 0.0}]

        hotdata_query.load_claims(self.hotdata, self.hotdata_db, rows)
        result = hotdata_query.topic_trend_query(self.hotdata, self.hotdata_db, topic_like=f"%{topic}%")
        return {"row_count": len(rows), "query_result": str(result)}
