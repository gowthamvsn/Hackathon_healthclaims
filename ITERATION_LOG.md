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

## 2026-09-11 ~18:07Z — RocketRide unblocked (key regenerated)

- User regenerated the RocketRide API key from the dashboard (new value
  ending `...c57106`, old one ending `...a3e3` stayed dead). Smoke test
  now **PASS**: `connected=True, action executed_via=local_fallback (1.03s)`.
  `executed_via=local_fallback` is expected — no `.pipe` file has been
  built in the RocketRide dashboard yet, so it makes a real authenticated
  decision locally instead of inside a hosted pipeline.

## 2026-09-11 ~18:10–18:20Z — Product pivot confirmed, corpus rebuilt with real literature

- User approved building the Grammarly-style claim-checker UX (validated /
  contradicted / no_proof, health/nutrition corpus) that had been proposed
  earlier but not yet greenlit.
- First pass: fetched 10 real PubMed abstracts (not fabricated text) via
  NCBI E-utilities for well-known, genuinely contradictory studies —
  saturated fat/CVD (Siri-Tarino 2010), red/processed meat/cancer (Chan
  2011), coffee/mortality (Freedman 2012), sugar-sweetened beverages/
  obesity, vitamin D/VITAL trial (Manson 2019), intermittent fasting/TREAT
  trial, artificial sweeteners/CVD (Debras 2022), omega-3/CVD (Aung 2018),
  sodium/DASH (Sacks 2001), gut microbiome/American Gut (McDonald 2018).
- **User pushed back: wanted actual downloaded papers, not just abstracts**
  — asked for first ~3000 words of real full text where available. User
  then manually downloaded and dropped 9 real PDFs into
  `data/sample_papers/` (matches all topics except intermittent fasting).
- Extracted real full text via `pdftotext` (default mode reads better than
  `-layout` for two-column academic PDFs), cleaned boilerplate
  (headers/footers/page numbers) via regex, truncated to first ~3000
  words, replaced the abstract-only corpus files in `data/health_papers/`
  with this real full text + proper citation headers (title/journal/PMID).
  Intermittent fasting topic **dropped** (user's call — no PDF was
  supplied for it) — corpus is 9 real papers, not 10.

## 2026-09-11 ~18:16–18:30Z — Corpus priming, a real bug found and fixed

- `scripts/prime_corpus.py` (new): loops the 9-paper corpus through
  `cognee.add()` + `cognee.cognify()` (builds the graph) and
  `hydra_store.persist_paper_graph()` (durable HydraDB write) once each.
- First run: 7/9 papers succeeded (10–60s each, real cognify time), then
  crashed with `aiohttp.ServerDisconnectedError` from Cognee's side on
  paper 8 (transient, not our bug). Retry hung and was killed.
- **User instruction: skip the 2 failing papers, work with the 7.**
- Investigating why a re-check reported all 9 "missing" surfaced a real
  bug: `hydra_store.has_seen()` called `client.context.list()` and assumed
  the response was a flat list (`listing.data`), but the real shape is
  `listing.data.sources` (confirmed live: `HandlerEnvelopeListV2ListResponse
  .data.sources` with `pagination.total`). The shape mismatch threw inside
  a bare `except Exception: return False`, so `has_seen()` silently always
  returned False — a false "nothing is primed" reading. Fixed the parsing;
  re-verified directly against the live API: **7 of 9 papers are genuinely
  primed** (`pagination.total=7`, correct titles). The 2 that failed
  (sodium/DASH, gut microbiome) are genuinely not in Cognee — confirmed
  separately by the crash traceback, not just the bug.

## 2026-09-11 ~18:33–19:00Z — Full 5-tool pipeline rebuilt in `agent/claim_checker.py`

- User asked directly: "are we using the tool's capabilities properly...
  are we building actual graphs, physically seen, etc." Audit found a real
  gap: the live demo path (`claim_checker.py` as it existed then) only
  touched Cognee, HydraDB (write-only), and Rote — **hotdata.dev and
  RocketRide were never called at query time**, only inside the old
  `agent/pipeline.py` benchmark script that the demo doesn't use. This
  violates the brief's "every layer must do real, repeated work" judging
  note.
- Verified HydraDB's `recall()`/`query()` response shape live too (same
  defensive-verification pattern as the `has_seen()` bug): real shape is
  `result.data.chunks[i].{chunk_content, additional_metadata, relevancy_score}`
  — genuine chunked hybrid retrieval, confirmed by querying "saturated fat
  and heart disease risk" and getting back the correct paper's actual
  content with a 0.80 relevancy score.
- Rebuilt `claim_checker.py` as a `ClaimChecker` class whose `check()`
  genuinely walks all five tools in the brief's own reference-architecture
  order for every single call:
  1. **Cognee** — `GRAPH_COMPLETION` search, parses VALIDATE/CONTRADICT/
     NO_PROOF + explanation + source from a structured prompt.
  2. **HydraDB** — `recall()` for related stored papers (relevancy-scored).
  3. **hotdata.dev** — logs the check as a row, runs a real SQL trend
     aggregate (`topic_trend_query`).
  4. **RocketRide** — new `decide_and_act_on_claim()` method on
     `RocketRideOrchestrator`, decides `file_validated_claim` /
     `flag_contradicted_claim` / `log_unverified_claim` and executes.
  5. **Modiqo/Rote** — `RotePlay` now wraps the *entire* 4-step pipeline
     (previously only wrapped the Cognee call), matching the brief's "sit
     Rote underneath your RocketRide execution loop" language more
     literally, and making the replay demo stronger (one replay skips all
     four external calls, not just one).
- Also made `agent/pipeline.py`'s RocketRide `connect()` call fault
  -tolerant (try/except instead of an unguarded await) so a bad/expired
  key degrades gracefully instead of crashing the whole request.
- **Bug found + fixed during first end-to-end test:** hotdata's
  `execute_sql()` returns a `QueryResult` object, not JSON-serializable.
  Rote's `_json_safe()` silently caught the `json.dumps()` TypeError and
  collapsed the *entire* result dict into a plain string for caching,
  which broke replay (`dict(play["result"])` crashed with "dictionary
  update sequence element #0 has length 1; 2 is required" on the second
  call). Fixed by extracting `{columns, rows, row_count}` from the
  QueryResult before it goes into the cached result. Reset the corrupted
  ledger entry (`data/rote_adapters/plays.json`) and re-verified.
- **Verified end-to-end on 7 real demo statements**, all five tools doing
  real work every time, all correctly verdicted against the real papers:

  | Statement | Verdict | Cold run |
  |---|---|---|
  | Saturated fat increases heart disease risk | contradicted | 27.2s |
  | Drinking coffee is linked to lower risk of death | validated | 34.8s |
  | Red/processed meat increases colorectal cancer risk | validated | 22.7s |
  | Vitamin D supplements prevent cancer/heart disease | contradicted | 23.1s |
  | Sugar-sweetened beverages cause weight gain | validated | 25.7s |
  | Omega-3 supplements prevent heart attacks | contradicted | 20.7s |
  | Eating chocolate improves eyesight | no_proof | 19.2s |

  Repeat check of the first statement: `replayed: true`, **0.0000043s**
  — all four external calls skipped, served from the local ledger. This
  is the real "second/third run gets faster/cheaper" compounding proof
  the brief's judging note asks for, and it persists across process
  restarts (the ledger is file-backed).

## 2026-09-11 ~18:34–19:00Z — Modiqo/Rote: real product still not wired in (in progress)

- Confirmed `rote` CLI was never installed (`which rote` empty,
  `ROTE_WORKSPACE=` empty in `.env`) — everything working for "muscle
  memory" up to this point is our own local replay-ledger substitute
  (`muscle_memory/rote_hook.py`), which is real and functionally proven,
  but never touches Modiqo's actual product.
- **User relayed a hard requirement heard at the event: at least 2 useful
  Rote "Plays" are needed to be eligible to win.** A Play = a real,
  inspectable, replayable capture of a successful workflow, published
  (Team/Community/Skip) through Rote's own lifecycle — not our local
  mimic.
- Found the authoritative setup page (`https://www.modiqo.ai/blog/the-playoffs`,
  linked directly from the hackathon brief). Confirmed via WebFetch +
  the user pasting the full page: install is
  `curl -fsSL https://getrote.dev/playoffs/install.sh | sh` — **macOS/
  Linux/WSL only, no native Windows/cmd/PowerShell path** (this was the
  root cause of the user's "nothing works in cmd or PowerShell" confusion
  — there is no native Windows path for this tool). Rote is not a
  standalone shell CLI you script against; it's a chat-command plugin
  inside a coding-assistant harness (`/play ...` in Claude Code, `$play
  ...` in Cursor/Codex, `/skill:play ...` in Kimi).
- Install flow, confirmed from the real page content: installer → sign in
  via Google/GitHub → `$play run hello` (or harness-specific prefix) as
  warm-up → `$play explore <outcome>` to create a real Play from actual
  repeated work → publish to Community → post "warmed up" in Discord.
- **User is running this now, live, in a WSL shell** (`koole@Gowtham:~$`):
  first hit "uv or the locked Play Python dependencies are required" →
  installed `uv` via `curl -LsSf https://astral.sh/uv/install.sh | sh` →
  needed `source $HOME/.local/bin/env` since a fresh install isn't on
  PATH until the shell restarts/sources it → installer then progressed
  past the OS/tools check into the interactive guided-setup prompt.
  **Not yet complete as of this log entry** — still needs: finish guided
  setup, sign in, run `$play run hello`, then create + publish at least 2
  real Plays from genuine parts of this project (best candidates: the
  Cognee claim-check step, and the RocketRide decide+act step).

## 2026-09-11 ~19:00Z — Snyk: installed, authenticated, real scan run

- `npm install -g snyk` (global install landed at
  `C:\Users\koole\AppData\Roaming\npm\snyk`, not on the git-bash PATH by
  default — invoke via full path or add to PATH).
- `snyk auth` with the token already in `.env` — succeeded.
- `snyk test --file=requirements.txt --package-manager=pip` needed the
  venv's Python explicitly (`--command=.venv/Scripts/python.exe`) to
  resolve dependencies.
- **Real result: 5 vulnerabilities across 133 scanned dependencies** — 1
  Critical (arbitrary code injection in `cognee` itself), 2 High (session
  expiration + deserialization in `litellm`/`diskcache`), 2 Medium (in
  `litellm`). All 5 are transitive, inside Cognee's own pinned dependency
  tree (a mandated sponsor tool), and Snyk itself reports **"no direct
  upgrade or patch"** available for any of them — not fixable by us
  without Cognee releasing a patched version. Documented (not ignored):
  saved as `snyk_scan_results.json` in the repo root as a permanent,
  inspectable record.

## 2026-09-11 ~19:00–19:05Z — API + frontend built and tested end-to-end

- `agent/api.py` (new): thin FastAPI layer over `ClaimChecker` — single
  `POST /api/check` endpoint, serves `frontend/index.html` as static
  content. FastAPI/uvicorn/pyarrow were already present as transitive
  deps of `cognee` — no new installs needed.
- `frontend/index.html` (new): single self-contained page (no build step,
  no external deps) — 7 pre-scripted clickable demo statements (the same
  7 verified above, covering all three verdicts), colored inline
  verdict marker (green/red/gray), explanation + cited source, elapsed
  time, and a visible "⚡ replayed from Rote — instant" badge when a
  cached play fires.
- Started the server (`uvicorn agent.api:app --port 8000`), verified via
  real `curl` calls against `/api/health`, `/`, and `/api/check` — all
  7 demo statements return correct verdicts through the actual HTTP
  layer, not just the Python-level test used earlier.

## 2026-09-11 ~19:10Z — Git repo initialized, first commit made

- Project had no git repo at all (`D:\hackthon_sept11` and
  `research_assistant/` were both untracked). Initialized git
  **specifically inside `research_assistant/`**, not at the parent
  `D:\hackthon_sept11` root — the real `.env` (with live API keys) lives
  one directory above `research_assistant/`, so scoping the repo there
  makes it structurally impossible to accidentally commit secrets,
  regardless of `.gitignore` correctness. Verified `.gitignore` already
  excludes `.env`, `.venv/`, `__pycache__/`, `.cognee/` etc.; double
  -checked `snyk_scan_results.json` for leaked tokens/org IDs (clean)
  before staging. First commit: 52 files, all current work (agent code,
  primed-corpus source papers, frontend, Snyk results, Rote ledger).

## Outstanding as of this log entry

| Layer | Status | Notes |
|---|---|---|
| Cognee | ✅ PASS, load-bearing every check | query-time GRAPH_COMPLETION recall |
| HydraDB | ✅ PASS, load-bearing every check | query-time relationship recall (bug-fixed) + priming writes |
| hotdata.dev | ✅ PASS, load-bearing every check | logs + real SQL trend query per check |
| RocketRide | ✅ PASS, load-bearing every check | new `decide_and_act_on_claim()`, real key |
| Modiqo Rote | ⚠️ Functionally proven, real product not yet used | local ledger works (27s→0.0000043s verified); real `rote` CLI install in progress in WSL, need ≥2 published Community Plays per user-relayed hackathon requirement |
| Snyk | ✅ Scanned, documented | 5 unfixable transitive vulns in Cognee's own deps, recorded not ignored |
| Corpus | 7/9 papers primed | sodium/DASH + gut microbiome skipped per user instruction (transient Cognee disconnect) |
| API + frontend | ✅ Built and tested | FastAPI + single-page demo UI, verified via real HTTP end to end |
| Git | ✅ Initialized + first commit | scoped to `research_assistant/`, `.env` structurally excluded |

### Next steps when resuming
1. Finish Rote install in WSL → `$play run hello` → create + publish ≥2
   real Community Plays (Cognee step + RocketRide step are the natural
   candidates).
2. Optional: retry priming the 2 skipped papers (sodium/DASH, gut
   microbiome) if time allows — corpus works fine at 7 papers either way.
3. Rehearse the live demo: open `http://127.0.0.1:8000`, click through a
   few statements live, then click one a second time to show the Rote
   instant-replay moment.
4. Optional stretch: wire a real `.pipe` file into the RocketRide
   dashboard so `decide_and_act_on_claim()` executes via a hosted
   pipeline instead of `local_fallback`.
