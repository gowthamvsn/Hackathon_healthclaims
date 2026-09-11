"""Claim-checking — the demo product surface.

Given a short health/nutrition statement, this walks the full stack in the
order the hackathon brief's reference architecture describes:

  Cognee (graph recall + verdict) -> HydraDB (relationship-aware recall of
  related stored papers) -> hotdata.dev (log the check + ad-hoc trend query)
  -> RocketRide (decide + act on the verdict) -> Modiqo/Rote (cache the
  *whole* successful run, so a repeat check of the same statement replays
  everything above instantly instead of re-running it).

Response shapes below are confirmed against the live APIs (Cognee Cloud,
HydraDB), not guessed:
  - cognee.search(GRAPH_COMPLETION) -> list[{"search_result": [str], ...}]
  - hydra.context.list()            -> resp.data.sources: list[...]
  - hydra.query() / recall()        -> resp.data.chunks: list[{"chunk_content",
    "additional_metadata", "relevancy_score", ...}]
"""
import asyncio
import re

from memory_layer import cognee_memory
from muscle_memory.rote_hook import RotePlay
from orchestration_layer.rocketride_orchestrator import RocketRideOrchestrator, make_client as make_rocketride_client
from query_layer import hotdata_query
from storage_layer import hydra_store

DATASET_NAME = "health_papers"
HYDRA_DATABASE = "research_assistant"
COGNEE_TIMEOUT_SECONDS = 45
ROCKETRIDE_CONNECT_TIMEOUT_SECONDS = 15
ROCKETRIDE_ACTION_TIMEOUT_SECONDS = 20

_VERDICT_KEYWORDS = ("VALIDATE", "CONTRADICT", "NO_PROOF")
_VERDICT_LABELS = {
    "VALIDATE": "validated",
    "CONTRADICT": "contradicted",
    "NO_PROOF": "no_proof",
}


def _build_query(statement: str) -> str:
    return (
        f'A user claims: "{statement}". Based only on the evidence in this '
        "dataset, decide if the evidence VALIDATES this claim, CONTRADICTS "
        "it, or provides NO_PROOF either way (topic not covered by the "
        "dataset).\n\n"
        "Respond in exactly this format, nothing else:\n"
        "VERDICT: <VALIDATE, CONTRADICT, or NO_PROOF>\n"
        "EXPLANATION: <one sentence citing the specific finding>\n"
        "SOURCE: <the paper title this is based on, or NONE if NO_PROOF>"
    )


def _extract_cognee_text(results: list) -> str:
    parts = []
    for r in results or []:
        sr = r.get("search_result") if isinstance(r, dict) else r
        if isinstance(sr, list):
            parts.extend(str(x) for x in sr)
        elif sr:
            parts.append(str(sr))
    return " ".join(parts).strip()


def _parse_verdict(blob: str) -> dict:
    m = re.search(r"VERDICT:\s*(VALIDATE|CONTRADICT|NO_PROOF)", blob, re.IGNORECASE)
    keyword = m.group(1).upper() if m else None
    if not keyword:
        upper = blob.upper()
        positions = [(upper.find(k), k) for k in _VERDICT_KEYWORDS if k in upper]
        keyword = min(positions)[1] if positions else None
    verdict = _VERDICT_LABELS.get(keyword, "no_proof")

    m = re.search(r"EXPLANATION:\s*(.+?)(?:\n|$|SOURCE:)", blob, re.IGNORECASE | re.DOTALL)
    explanation = m.group(1).strip() if m else blob[:400].strip()

    m = re.search(r"SOURCE:\s*(.+)", blob, re.IGNORECASE)
    source = m.group(1).strip().strip(".") if m else None
    if source and source.upper().startswith("NONE"):
        source = None

    return {"verdict": verdict, "explanation": explanation, "source": source}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def _source_in_corpus(source: str | None, corpus_titles: list[str]) -> bool:
    """Cognee's GRAPH_COMPLETION is an LLM completion, not a strict
    retrieval-only lookup — for well-known topics it will confidently answer
    from its own training data and cite a plausible-sounding source even
    when that paper was never primed into our corpus (confirmed live: it
    cited a DASH-Sodium trial with specific numbers even though no sodium
    paper exists in our 7-paper corpus). This is the guard against that:
    only trust a verdict if its cited source is actually one of our primed
    papers; otherwise treat it as no evidence in our corpus."""
    if not source:
        return False
    ns = _normalize(source)
    if not ns:
        return False
    for title in corpus_titles:
        nt = _normalize(title)
        if not nt:
            continue
        if ns in nt or nt in ns:
            return True
        s_words, t_words = set(ns.split()), set(nt.split())
        if s_words and t_words and len(s_words & t_words) / min(len(s_words), len(t_words)) > 0.6:
            return True
    return False


def _hotdata_stats_to_dict(result) -> dict:
    """hotdata's execute_sql() returns a QueryResult object, not JSON-safe as
    -is — Rote's ledger needs plain data or it silently stringifies the whole
    cached result (breaking replay). Pull out just the useful fields."""
    if isinstance(result, dict):
        return result
    columns = getattr(result, "columns", None)
    rows = getattr(result, "rows", None)
    if columns is not None and rows is not None:
        return {"columns": columns, "rows": rows, "row_count": getattr(result, "row_count", len(rows))}
    return {"raw": str(result)}


def _extract_hydra_titles(recall_result, limit: int = 3) -> list[dict]:
    chunks = getattr(getattr(recall_result, "data", None), "chunks", None) or []
    seen_titles = set()
    out = []
    for chunk in chunks:
        meta = getattr(chunk, "additional_metadata", None) or {}
        title = meta.get("title")
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        out.append({
            "title": title,
            "relevancy_score": getattr(chunk, "relevancy_score", None),
        })
        if len(out) >= limit:
            break
    return out


class ClaimChecker:
    def __init__(self):
        self.hydra = hydra_store.make_client()
        self.hotdata = hotdata_query.make_client()
        self.hotdata_db = hotdata_query.ensure_claims_table(self.hotdata)
        self.orchestrator = RocketRideOrchestrator(make_rocketride_client())
        self._rocketride_connected = False
        self._rocketride_error: str | None = None
        self._corpus_titles: list[str] | None = None

    async def _ensure_rocketride(self):
        if self._rocketride_connected:
            return
        try:
            self._rocketride_connected = await asyncio.wait_for(
                self.orchestrator.connect(), timeout=ROCKETRIDE_CONNECT_TIMEOUT_SECONDS
            )
        except Exception as exc:
            self._rocketride_connected = False
            self._rocketride_error = str(exc)

    def _get_corpus_titles(self) -> list[str]:
        if self._corpus_titles is None:
            self._corpus_titles = hydra_store.list_paper_titles(self.hydra, HYDRA_DATABASE)
        return self._corpus_titles

    async def check(self, statement: str) -> dict:
        """Public entry point. Returns the full result dict plus
        replayed/elapsed_seconds from the Rote wrapper."""
        statement = statement.strip()
        rote = RotePlay("check_claim")
        play = await rote.run([statement.lower()], self._run_pipeline, statement)
        result = dict(play["result"])
        result["replayed"] = play["replayed"]
        result["elapsed_seconds"] = play["elapsed_seconds"]
        return result

    async def _run_pipeline(self, statement: str) -> dict:
        # 1. Cognee — graph-based recall over the primed corpus. Bounded by a
        # timeout: an unresponsive remote call must fail, not hang the
        # request forever (previously unbounded — a stalled Cognee Cloud
        # call would block indefinitely with no way to recover but killing
        # the server).
        timed_out = False
        try:
            cognee_results = await asyncio.wait_for(
                cognee_memory.recall_claims(_build_query(statement), DATASET_NAME, 5),
                timeout=COGNEE_TIMEOUT_SECONDS,
            )
            blob = _extract_cognee_text(cognee_results)
        except asyncio.TimeoutError:
            blob = None
            timed_out = True

        if timed_out:
            parsed = {
                "verdict": "no_proof",
                "explanation": f"Cognee didn't respond within {COGNEE_TIMEOUT_SECONDS}s — try again.",
                "source": None,
            }
        elif blob:
            parsed = _parse_verdict(blob)
        else:
            parsed = {
                "verdict": "no_proof",
                "explanation": "No related evidence found in the corpus.",
                "source": None,
            }

        # Grounding guard: only trust a validate/contradict verdict if its
        # cited source is actually one of our primed papers — otherwise the
        # LLM is answering from its own outside knowledge, not our corpus.
        if parsed["verdict"] != "no_proof" and not _source_in_corpus(parsed["source"], self._get_corpus_titles()):
            parsed = {
                "verdict": "no_proof",
                "explanation": "No matching evidence found in our primed corpus for this claim.",
                "source": None,
            }

        # 2. HydraDB — relationship-aware recall of related stored papers.
        related_papers: list[dict] = []
        try:
            hydra_hits = hydra_store.recall(self.hydra, HYDRA_DATABASE, statement, collection="papers", max_results=3)
            related_papers = _extract_hydra_titles(hydra_hits)
        except Exception:
            pass

        # 3. hotdata.dev — log this check, then run a real ad-hoc trend query.
        try:
            hotdata_query.load_claims(self.hotdata, self.hotdata_db, [{
                "paper_id": hydra_store.content_id(statement),
                "claim": statement[:500],
                "topic": parsed["verdict"],
                "confidence": 1.0,
            }])
            raw_stats = hotdata_query.topic_trend_query(
                self.hotdata, self.hotdata_db, topic_like=f"%{parsed['verdict']}%"
            )
            hotdata_stats = _hotdata_stats_to_dict(raw_stats)
        except Exception as exc:
            hotdata_stats = {"error": str(exc)}

        # 4. RocketRide — decide + act on the verdict, informed by hotdata's stats.
        # Now runs as a real hosted pipeline call (use -> tool -> terminate),
        # so it needs the same bounded timeout as the other external calls.
        await self._ensure_rocketride()
        try:
            rocketride_action = await asyncio.wait_for(
                self.orchestrator.decide_and_act_on_claim(
                    verdict=parsed["verdict"], statement=statement, hotdata_stats=hotdata_stats
                ),
                timeout=ROCKETRIDE_ACTION_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            rocketride_action = {"executed_via": "error", "error": str(exc)}

        return {
            "statement": statement,
            "verdict": parsed["verdict"],
            "explanation": parsed["explanation"],
            "source": parsed["source"],
            "related_papers": related_papers,
            "hotdata_stats": hotdata_stats,
            "rocketride_action": rocketride_action,
        }
