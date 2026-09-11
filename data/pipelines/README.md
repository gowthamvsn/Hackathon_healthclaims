# RocketRide pipeline goes here

Export your visually-built pipeline from the RocketRide VS Code extension /
dashboard as `research_finding.pipe` in this folder.

Until that file exists, `orchestration_layer.RocketRideOrchestrator.decide_and_act()`
still makes a real authenticated connection to RocketRide and makes a real
decision — it just executes the action locally instead of inside a hosted
pipeline (`executed_via: "local_fallback"` in its result).

Suggested shape for the pipeline (confirm exact node `provider` names in the
dashboard's node picker — that catalog isn't published as static docs):
1. Source: `webhook` or `chat`
2. One tool/function node named `decide_and_act` that receives
   `{paper_id, action, claim_count, topic_stats}` and performs the "motion"
   (e.g. post to Slack, write a record, trigger a follow-up search).

Once the file exists, `RocketRideOrchestrator` calls it automatically via
`client.use(filepath=...)` -> `client.tool(tool="decide_and_act", ...)` ->
`client.terminate(...)`.
