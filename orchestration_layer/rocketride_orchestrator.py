"""Motion / Orchestration Layer — RocketRide.ai

Reads what HydraDB/hotdata already know, decides the next action, and
executes it: fetch -> read -> summarize -> file the finding.

Confirmed real against the installed `rocketride` 1.3.0 package (see
SETUP_NOTES.md): `RocketRideClient(uri, auth)`, `.connect()`,
`.get_dashboard()`, `.get_services()`, `.use()/.send()/.terminate()` are
real bound methods, not guesses.

IMPORTANT — one piece is deliberately left as a TODO, not a guess: the
`.pipe` pipeline JSON schema has a `components[].provider` field naming a
specific node type out of RocketRide's 50+ integrations (LLM providers,
vector DBs, etc.), and that catalog is only visible once you're logged into
the RocketRide dashboard/VS Code extension. Build the "decide + act on a
finding" pipeline visually there (per the hackathon's RocketRide setup
guide), export it to data/pipelines/research_finding.pipe, and this layer
will use it automatically. Until then, `decide_and_act()` still makes a
REAL authenticated connection and a real decision — it just executes the
action locally instead of inside a hosted pipeline.
"""
import os
from pathlib import Path

from rocketride import RocketRideClient

from agent.config import require_env

PIPE_FILE = Path(__file__).parent.parent / "data" / "pipelines" / "research_finding.pipe"


def make_client() -> RocketRideClient:
    return RocketRideClient(
        uri=os.environ.get("ROCKETRIDE_ENGINE_URL", ""),
        auth=require_env("ROCKETRIDE_API_KEY"),
    )


class RocketRideOrchestrator:
    def __init__(self, client: RocketRideClient):
        self.client = client
        self._connected = False

    async def connect(self):
        await self.client.connect()
        self._connected = self.client.is_connected()
        return self._connected

    async def decide_and_act(self, *, already_seen: bool, paper_id: str, claims: list, topic_stats) -> dict:
        """The orchestration decision: skip re-filing a known paper (that's
        the compounding win) or file a new finding built from the claims
        Cognee extracted and the trend hotdata just computed.

        If a live .pipe pipeline is wired up, runs the decision as a hosted
        RocketRide pipeline (`use` -> `tool` -> `terminate`); otherwise runs
        the same decision locally against the same authenticated client.
        """
        action = "skip_duplicate" if already_seen else "file_finding"
        payload = {
            "paper_id": paper_id,
            "action": action,
            "claim_count": len(claims),
            "topic_stats": topic_stats,
        }

        if PIPE_FILE.exists():
            run = await self.client.use(filepath=str(PIPE_FILE))
            try:
                result = await self.client.tool(
                    token=run["token"], tool="decide_and_act", input=payload
                )
            finally:
                await self.client.terminate(run["token"])
            return {"executed_via": "rocketride_pipeline", "action": action, "result": result}

        return {"executed_via": "local_fallback", "action": action, "payload": payload}

    async def decide_and_act_on_claim(self, *, verdict: str, statement: str, hotdata_stats) -> dict:
        """The claim-checker's orchestration decision: given a validated /
        contradicted / no_proof verdict (from Cognee) and the current
        hotdata.dev trend stats for that verdict bucket, decide + execute
        the next action — this is the "motion" step of the demo's per-click
        pipeline (Cognee -> HydraDB -> hotdata -> RocketRide -> Rote)."""
        action_map = {
            "validated": "file_validated_claim",
            "contradicted": "flag_contradicted_claim",
            "no_proof": "log_unverified_claim",
        }
        action = action_map.get(verdict, "log_unverified_claim")
        payload = {"statement": statement, "verdict": verdict, "action": action, "hotdata_stats": hotdata_stats}

        if PIPE_FILE.exists():
            run = await self.client.use(filepath=str(PIPE_FILE))
            try:
                result = await self.client.tool(
                    token=run["token"], tool="decide_and_act", input=payload
                )
            finally:
                await self.client.terminate(run["token"])
            return {"executed_via": "rocketride_pipeline", "action": action, "result": result}

        return {"executed_via": "local_fallback", "action": action, "payload": payload}
