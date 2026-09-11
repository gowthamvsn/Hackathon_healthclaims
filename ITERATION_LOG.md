# Setup & smoke-test iteration log

All timestamps are UTC, taken directly from Cognee's own log lines and from
`date:` headers in real API responses (HydraDB, Anthropic) — not estimated.
Local reference date: 2026-09-10 evening (America/Los_Angeles), hackathon is
2026-09-11 at AWS Builder Loft SF.

## 2026-09-10 21:39 — Repo discovery
- Found `Data and AI Hackathon_ From Memory to Muscle Memory.docx` in the
  working directory. Converted via `pandoc` to confirm it's the official
  builder guide — all 5 named tools (Cognee.ai, HydraDB, hotdata.dev,
  RocketRide.ai, Modiqo.ai/Rote) are real, mandated sponsor tech, and
  "Self-Improving Research Assistant" is one of their suggested project
  ideas verbatim.

## 2026-09-10 21:41–21:56 — SDK verification (no guessing)
- Installed all 4 pip packages (`cognee`, `hydradb-sdk`,
  `hotdata-framework`, `rocketride`) into a clean venv and inspected real
  `inspect.signature()` / `dir()` output rather than trusting scraped docs.
- **Finding:** `rocketride==1.3.0` fails to import on Python 3.10
  (`ImportError: cannot import name 'NotRequired' from 'typing'`) — it
  needs Python 3.11+. Rebuilt the venv on `py -3.12`.

## 2026-09-10 21:56–22:14 — Repo scaffold + first smoke run
- Built `agent/`, `memory_layer/`, `storage_layer/`, `query_layer/`,
  `orchestration_layer/`, `muscle_memory/`, `scripts/`, `benchmark/`.
- **05:13:22Z — first full smoke test:** `HydraDB`, `hotdata.dev`,
  `RocketRide`, `Cognee` → SKIP (no keys in `.env` yet). `Modiqo Rote` → PASS
  (local replay ledger works with zero external dependencies: run 1
  executes, run 2 replays in <1ms).

## 2026-09-10 ~23:00–23:02 (local) — Keys start arriving
- User pastes real API keys into `D:\hackthon_sept11\.env` (Snyk, Cognee,
  RocketRide, Anthropic — later HydraDB, then hotdata).
- Reformatted the free-text paste into proper `KEY=VALUE` syntax; verified
  `python-dotenv`'s `load_dotenv()` walks up parent directories, so a
  `.env` one level above `research_assistant/` is still picked up correctly
  (confirmed with a throwaway `TEST_VAR` round-trip).

## 06:09:55Z — Second smoke run (LLM_PROVIDER=anthropic set)
- `Cognee` → FAIL: `ProviderConfigMismatchError` — Cognee refused to
  silently default embeddings to OpenAI while `LLM_PROVIDER=anthropic`
  (Anthropic has no embeddings API). Correct, safe behavior on Cognee's
  part, not a bug.
- `RocketRide` → FAIL: `AuthenticationException: Invalid or revoked API key`.
- **Fix:** found Ollama already running locally
  (`http://localhost:11434`, models: llama3, gemma3:1b, llama3.2). Pulled
  `nomic-embed-text` (274MB) and set `EMBEDDING_PROVIDER=ollama`,
  `EMBEDDING_MODEL=nomic-embed-text`, `EMBEDDING_ENDPOINT=http://localhost:11434`
  in `.env` — free, local, no extra key needed.

## 06:11:13Z — Third smoke run
- `Cognee` → FAIL: `litellm.AuthenticationError: AnthropicException –
  "API key is invalid."` (embeddings config fixed; now a real Anthropic
  auth failure).
- `HydraDB` → FAIL: HTTP 404 `DATABASE_NOT_FOUND` for `smoke_test_db` — but
  this is a **successful auth**, just a missing database. Also resolved the
  earlier concern that `HYDRADB_API_KEY` and `HOTDATA_API_KEY` held an
  identical value (user had pasted the same key into both fields); user
  cleared the `hotdata.dev` field, confirming the key belongs to HydraDB.
- `hotdata.dev` → SKIP (key cleared, not yet supplied).
- `RocketRide` → FAIL: still `Invalid or revoked API key`.
- `Modiqo Rote` → PASS.
- **Fix 1:** added `ensure_database()` to `storage_layer/hydra_store.py` —
  auto-creates the HydraDB database on first use instead of requiring a
  manual dashboard step.

## 06:13:13Z — Fourth smoke run (after ensure_database fix)
- `HydraDB` → FAIL: HTTP 400 `INVALID_INPUT` — `document_metadata` must be
  a JSON **array** of per-document objects, not a bare object.
- **Fix 2:** wrapped metadata as `[{"id": ..., "additional_metadata": ...}]`.

## 06:13:39Z — Fifth check (HydraDB only)
- `HydraDB` → FAIL: HTTP 400 `INVALID_INPUT` — `unsupported key(s)
  [source]`; the API listed its actual supported top-level keys
  (`additional_metadata`, `document_metadata`, `evidence_kind`,
  `evidence_subject`, `file_id`, `id`, `infer`, `metadata`, `relations`,
  `source_id`).
- **Fix 3:** nested all custom fields under `additional_metadata` per that
  error message.

## ~06:13:50Z — HydraDB confirmed working end-to-end
- `HydraDB` → **PASS** (7.16s): real ingest + real hybrid query against the
  live API. Fully working, not a mock.

## 06:1x–present — Cognee blocked on a bad key (confirmed independently)
- User updated `COGNEE_API_KEY` (a different, unused-by-our-code value) but
  `ANTHROPIC_API_KEY` — the one actually used for LLM auth — was unchanged.
  Re-ran the Cognee smoke test: same `"API key is invalid."` error.
- Verified independently with a raw `curl` straight to
  `https://api.anthropic.com/v1/models` using the same key, bypassing
  Cognee/litellm entirely — Anthropic itself returned
  `{"type":"authentication_error","message":"API key is invalid."}`.
- **Conclusion: this is a bad/revoked key, not a code issue.** Waiting on a
  fresh `ANTHROPIC_API_KEY` from the user.

## 2026-09-11 16:48Z — Sixth smoke run (hotdata key supplied)
- `HydraDB` → PASS again (12.14s — real ingest + query, confirms the earlier
  fix holds).
- `hotdata.dev` → FAIL: `ValueError: Managed table loads require a parquet
  file (got '...tmp....csv')`. Our loader was writing CSV; the SDK's
  managed-table load path only accepts Parquet.
- `Cognee` → FAIL: same Anthropic `"API key is invalid."` — user updated
  `COGNEE_API_KEY` (unused by our code) again but not `ANTHROPIC_API_KEY`.
- `RocketRide` → FAIL: still `Invalid or revoked API key`, key unchanged.
- **Fix 4:** rewrote `query_layer/hotdata_query.py::load_claims()` to build
  a real Parquet file with `pyarrow` (`pa.Table.from_pylist` +
  `pq.write_table`), upload it via `client.upload_parquet()`, then
  `client.load_managed_table(..., upload_id=..., mode="append")` — matches
  the confirmed `HotdataClient` method signatures.
- Retested `hotdata.dev` alone → **PASS** (6.18s): real Parquet upload,
  real managed-table load, real SQL aggregate returned
  `[['smoke', 1, 1.0]]`.

## 2026-09-11 ~16:50Z — Screenshot revealed the real integration path for Cognee
- User shared a screenshot of `platform.cognee.ai/api-keys` — Cognee's
  mandated hackathon integration is **Cognee Cloud** (a per-tenant hosted
  API at `https://tenant-<id>.aws.cognee.ai`, auth via `X-Api-Key` +
  `X-Tenant-Id`), not the self-hosted OSS pipeline hitting our own
  Anthropic key directly. This is why `ANTHROPIC_API_KEY` was a red
  herring — Cognee's own backend handles LLM/embeddings when using Cloud
  mode; we never needed our own LLM key.
- Read `cognee/api/v1/serve/serve.py`, `cloud_client.py`, and `state.py`
  directly: `add()`/`cognify()`/`search()` all check a module-level
  `get_remote_client()` singleton and transparently route to the connected
  cloud tenant once `cognee.serve(url=..., api_key=...)` has been called —
  confirmed by reading the source, not assumed.
- **Fix 5:** added `memory_layer/cognee_memory.py::connect()` — calls
  `cognee.serve(url=COGNEE_SERVICE_URL, api_key=COGNEE_API_KEY)` once per
  process; every public function calls it first. Set
  `COGNEE_SERVICE_URL=https://tenant-c6b1d85f-9046-435b-abc6-10e0115740e4.aws.cognee.ai`
  in `.env` from the screenshot's Connection Details.
- Retested → **PASS** (17.02s): "Connected to Cognee (remote) at
  https://tenant-...aws.cognee.ai", real cognify (2.48s), 1 real result
  recalled.

## 2026-09-11 ~17:00–17:27Z — Product-direction discussion (no code changes yet)

- **User asked "what are we trying to build with all these btw"** — reset
  context: a Self-Improving Research Assistant for the hackathon; extract
  claims from papers (Cognee), store the graph (HydraDB), query it
  (hotdata.dev), decide+act (RocketRide), remember successful runs (Rote);
  demo proof is run 1 vs run 3 timing.
- **User asked "what exactly will i show for the final demo"** — answered:
  (1) architecture mapped to the brief's Structure/Memory/Insight/Motion/
  Muscle-Memory framing, (2) live `benchmark/compounding_proof.py` run
  showing run 3 faster than run 1, (3) optionally the HydraDB/Cognee Cloud
  dashboards showing real (non-mocked) data.
- **User proposed a UX pivot:** a Grammarly-style flow — select/type text
  on a page, click a button, surface a relevant citation if one exists and
  show nothing otherwise. Assessed as a stronger demo than the CLI
  benchmark; recommended a single self-controlled web page with
  `window.getSelection()` over a real browser extension, to cut scope.
- **User refined further, scoped to health:** restrict to ~10 pre-loaded
  health/nutrition papers, pre-specified demo statements (not live-typed),
  and a 3-way output — **validated / contradicted / no proof** — with the
  colored inline marker only appearing when relevant. Assessed honestly:
  - Good call: scoping to a small corpus + pre-specified statements removes
    the "live NLP fails on stage" risk that kills most hackathon demos.
  - Good call: health/nutrition literature has genuine, real contradictions
    (sugar, saturated fat, coffee, red meat), so a "contradicted" result
    won't look fabricated.
  - Pushback given: no separate "is this about health" classifier is
    needed — always show the button on selection and let the 10-paper
    corpus scoping do that job for free; "no proof found" is the correct,
    honest answer for anything outside it.
  - Flagged: must deliberately script at least one "contradicted" and one
    "no proof" example alongside "validated" ones, or the demo only proves
    the easy case.
  - **Not yet implemented** — user has not said "build it" yet.
- **User asked whether Cognee is connected to this Claude Code session via
  MCP** (referencing "they said Cognee should come inside Claude Code").
  Checked directly: `ToolSearch("cognee")` found no matching deferred
  tools, and `~/.claude.json` shows `"mcpServers": {}` everywhere — **no
  MCP connection exists**; Cognee is wired in only via its Python SDK
  inside `memory_layer/cognee_memory.py`. Noted that the earlier
  platform.cognee.ai screenshot's "Use these with Claude, MCP, or any API
  client" line confirms Cognee does offer an MCP server (likely under its
  "Integrations" tab), and asked the user to confirm which of two distinct
  things "they" meant before wiring anything: (1) Cognee-as-MCP for this
  coding session (dev convenience), vs. (2) the research-assistant agent
  itself calling Cognee via MCP instead of the Python SDK at runtime (a
  real architecture change). Awaiting user's answer.

## Outstanding as of this log entry

| Layer | Status | Blocker |
|---|---|---|
| HydraDB | ✅ PASS | none |
| hotdata.dev | ✅ PASS | none |
| Cognee | ✅ PASS | none (routes through Cognee Cloud) |
| Modiqo Rote | ✅ PASS | CLI not yet installed locally (not required for the local-ledger fallback to work) |
| RocketRide | ❌ FAIL | `ROCKETRIDE_API_KEY` invalid/unactivated — possibly needs the hackathon coupon-code credits, only issued at the venue |
