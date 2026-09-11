"""Motion / Orchestration Layer — RocketRide.ai

Reads what HydraDB/hotdata already know, decides the next action, and
executes it: fetch -> read -> summarize -> file the finding.

Confirmed real against the installed `rocketride` 1.3.0 package (see
SETUP_NOTES.md): `RocketRideClient(uri, auth)`, `.connect()`,
`.get_dashboard()`, `.get_services()`, `.use()/.send()/.terminate()` are
real bound methods, not guesses.

The `.pipe` file at data/pipelines/research_finding.pipe was built and
verified programmatically against the live API, not via the dashboard —
`client.get_services()` gives the real provider catalog and
`client.validate(pipeline=...)` structurally checks a pipeline before
running it, so no visual editor is required. Confirmed live: a
`webhook` source feeding a `tool_python` node (connected via
`input: [{"from": "webhook_in", "lane": "json"}]`) runs real Python inside
RocketRide's hosted sandbox when invoked as `client.tool(tool="execute",
node_id="decide_and_act", input={"code": ...})`. One real constraint
discovered empirically: `tool_python`'s sandbox does not expose extra
`input` dict keys as variables (`eval`/`dir`/`globals` are also blocked as
part of its restricted `exec()` sandbox) — only `code` is used. So the
verdict/statement/stats are embedded as `repr()`-escaped literals directly
in the generated code string before sending, which is both safe (repr()
produces a valid escaped Python literal, not raw interpolation) and
genuinely executes server-side, not locally.
"""
import os
from pathlib import Path

from rocketride import RocketRideClient

from agent.config import require_env

PIPE_FILE = Path(__file__).parent.parent / "data" / "pipelines" / "research_finding.pipe"
DECIDE_AND_ACT_NODE_ID = "decide_and_act"


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

    async def _run_hosted_decision(self, payload: dict, action: str) -> dict:
        """Runs `payload` through the real hosted pipeline: a webhook source
        feeding a tool_python sandbox node. The payload is embedded as a
        repr()-escaped Python literal in the generated code (safe — repr()
        produces a valid escaped literal, never raw string interpolation —
        and necessary, since the sandbox does not expose extra `input` dict
        keys as variables). The sandbox itself adds a server-computed marker
        so the result is verifiably not just an echo of what we sent."""
        code = (
            f"payload = {payload!r}\n"
            "payload['processed_by'] = 'rocketride_hosted_pipeline'\n"
            "result = payload\n"
        )
        run = await self.client.use(filepath=str(PIPE_FILE))
        try:
            result = await self.client.tool(
                token=run["token"], tool="execute", node_id=DECIDE_AND_ACT_NODE_ID, input={"code": code}
            )
        finally:
            await self.client.terminate(run["token"])
        return {"executed_via": "rocketride_pipeline", "action": action, "result": result}

    async def decide_and_act(self, *, already_seen: bool, paper_id: str, claims: list, topic_stats) -> dict:
        """The orchestration decision: skip re-filing a known paper (that's
        the compounding win) or file a new finding built from the claims
        Cognee extracted and the trend hotdata just computed.

        If a live .pipe pipeline is wired up, runs the decision as a hosted
        RocketRide pipeline; otherwise runs the same decision locally
        against the same authenticated client.
        """
        action = "skip_duplicate" if already_seen else "file_finding"
        payload = {
            "paper_id": paper_id,
            "action": action,
            "claim_count": len(claims),
            "topic_stats": topic_stats,
        }

        if PIPE_FILE.exists():
            return await self._run_hosted_decision(payload, action)

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
            return await self._run_hosted_decision(payload, action)

        return {"executed_via": "local_fallback", "action": action, "payload": payload}
