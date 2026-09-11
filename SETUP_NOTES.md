# Setup notes — what's confirmed vs. what to verify tomorrow

Everything below was checked on 2026-09-10 by actually `pip install`-ing the
real packages into a clean Python 3.12 venv and inspecting their live
`inspect.signature()` / `dir()` output — not just scraped docs. Where a
detail couldn't be independently confirmed that way, it's flagged `[verify]`
rather than presented as fact.

## Confirmed real (checked against the installed package)

- **Cognee** `cognee==1.5.4` — `cognee.add()`, `cognee.cognify()`,
  `cognee.search(query_type=SearchType.GRAPH_COMPLETION, ...)` are real, and
  `SearchType.CYPHER` / `GRAPH_COMPLETION` exist if you want raw-graph vs.
  LLM-summarized recall.
- **HydraDB** `hydradb-sdk==2.1.4`, imported as `hydra_db` — 
  `HydraDB(token=..., base_url=...)`, `client.context.ingest(...)`,
  `client.query(...)`, `client.context.subgraph(...)`,
  `client.context.relations(...)` are real bound methods with the exact
  kwargs used in `storage_layer/hydra_store.py`.
- **hotdata.dev** `hotdata-framework==0.14.0` — `HotdataClient.from_env()`
  reads `HOTDATA_API_KEY` / `HOTDATA_WORKSPACE` / `HOTDATA_API_URL`
  (confirmed straight from `hotdata_framework/env.py` source, default host
  `https://api.hotdata.dev`). `execute_sql`, `create_managed_database`,
  `load_managed_table` are real.
- **RocketRide** `rocketride==1.3.0` — **requires Python 3.11+** (imports
  `typing.NotRequired`, which doesn't exist on 3.10 — this bit us during
  setup, hence the `py -3.12` venv). `RocketRideClient(uri=, auth=)`,
  `.connect()`, `.use()`, `.send()`, `.tool()`, `.terminate()`,
  `.get_dashboard()` are all real.
- **Modiqo Rote** — no pip package. Ships as a local CLI at
  github.com/modiqo/rote-releases. Confirmed real subcommands from Modiqo's
  own docs: `rote start`, `rote how`, `rote guidance`,
  `rote adapter new` (builds an API adapter from an OpenAPI/Swagger spec or
  an MCP endpoint), `rote registry adapter search|pull|push`. The "hello
  world" warm-up is `$play run hello`, typed inside a Rote-attached coding
  assistant session (Claude/Cursor/Codex/etc.), not a bare shell command.

## Flagged `[verify]` — confirm at the venue, budget ~15-20 min total

1. **RocketRide `.pipe` node catalog.** `PipelineConfig`/`PipelineComponent`
   schema is confirmed (`components[].provider`, `.config`, `.input`,
   `.control`), but the actual `provider` string catalog (50+ node types —
   LLM providers, vector DBs, etc.) is only visible in the RocketRide
   dashboard/VS Code extension's node picker, not in any static docs page I
   could fetch. `orchestration_layer/rocketride_orchestrator.py` makes a
   real authenticated connection and a real decision either way; it just
   runs the action locally until you drop a built `research_finding.pipe`
   into `data/pipelines/` (see the README there for the suggested shape).
2. **RocketRide staging vs. cloud engine URL** (`ROCKETRIDE_ENGINE_URL`).
   The hackathon guide points at `staging.rocketride.ai` with a private
   step-by-step setup doc — grab the exact engine URL + API key flow from
   that doc when you sign up.
3. **Rote's programmatic record/replay commands.** Confirmed CLI verbs
   above are real, but I could not confirm a documented "record this
   specific run" / "replay play X" invocation you can shell out to from
   Python (Modiqo's flow is designed to be driven from inside a coding
   assistant chat). Run `rote --help` after installing tonight and wire the
   real command into `muscle_memory/rote_hook.py::_rote_cli()` — the
   deterministic-replay *mechanics* (the actual compounding-proof
   speedup) already work via the local ledger regardless.
4. **HydraDB / hotdata org & workspace setup.** `HYDRADB_DATABASE` and
   `HOTDATA_WORKSPACE` are placeholders — create the actual
   database/workspace in each dashboard and drop the real names in `.env`.

## Snyk (scored, not a pipeline layer)

Not one of the five stacked layers, but the hackathon brief scores it
separately: "security vulnerabilities found will reduce points from the
final score." Sign up at snyk.io, connect it to your coding tool, and run a
scan before submitting — `SNYK_TOKEN` is in `.env.template` if you want to
script `snyk test` into a CI step.

## Why Python 3.12, not 3.10

The first venv was created on the machine's default Python 3.10 and
`rocketride` failed to import (`ImportError: cannot import name
'NotRequired' from 'typing'`). Confirmed as a real Python-version
requirement, not a bad install — 3.12 was already on the machine
(`py -3.12`), so the venv was rebuilt on that instead.
