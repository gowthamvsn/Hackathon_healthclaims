# Self-Improving Research Assistant - Health Claims Verification

## Problem

People see a lot of health claims on public websites, and it's hard to
validate them - many users take these unverified statements as fact. This
project finds health claims (typed, or selected from a page), validates them
against real research literature, and cites the source.

Built for the **AWS Builder Loft SF** hackathon (Sep 11, 2026) - "Data and AI
Hackathon: From Memory to Muscle Memory." Type or select any health/nutrition
claim and it's checked live against a real research corpus - **validated**,
**contradicted**, or **no proof found**, with an actual paper cited - using
the hackathon's full 5-tool mandated stack, wired end-to-end and verified
live against real APIs throughout (not mocked).


## Try it

```
uvicorn agent.api:app --host 0.0.0.0 --port 8000
```

| Page | What it is |
|---|---|
| `/` | Manual tool - type any claim, get validated/contradicted/no_proof + citation |
| `/feed` | A Grammarly-style demo: select a claim inside a scrollable social-style feed, a "Check" button appears on plausibly health-related selections |
| `/trends` | Live SQL read straight from hotdata.dev - real accumulating trend data, no dashboard needed |

## The stack

| Layer | Tool | Role | Status |
|---|---|---|---|
| Structure/Memory construction | **Cognee.ai** | Builds a real knowledge graph per paper (`add`+`cognify`), then `GRAPH_COMPLETION` search at query time | ✅ Live, all 13 papers primed |
| Memory storage & serving | **HydraDB** | Durable store + hybrid graph/vector recall of related papers; also the source-of-truth allowlist for the grounding guard below | ✅ Live |
| Insight / live query | **hotdata.dev** | Logs every check as a row, runs a real SQL trend aggregate (`group by topic`) | ✅ Live - see `/trends` |
| Motion / orchestration | **RocketRide.ai** | Decides the next action (file/flag/log) and **executes it inside a real hosted pipeline** (a `webhook` → `tool_python` sandbox node, built and validated programmatically via the SDK, not the dashboard) | ✅ Live, `executed_via: rocketride_pipeline` |
| Muscle memory | **Modiqo.ai (Rote)** | The live app uses a local replay-ledger cache modeled on Rote's concept (real, working, but not the actual product - labeled honestly in the UI as "local muscle-memory cache"). Separately, 2 real Rote Community Plays are published for eligibility (links below) | ⚠️ Disclosed split - see note above |

Published Rote Community Plays:
- https://play.modiqo.ai/gowtham-healthclaims/health-claim-check@0.1.0
- https://play.modiqo.ai/gowtham-healthclaims/health-claim-grounding-check@0.0.1

## Corpus

13 real, peer-reviewed papers (not fabricated), covering genuinely
contradictory public health topics: saturated fat & CVD, red/processed meat &
cancer, coffee & mortality, sugar-sweetened beverages & obesity, vitamin D
supplementation, artificial sweeteners, omega-3 supplementation, sodium &
hypertension, gut microbiome diversity, alcohol & CVD, breakfast & weight,
MSG & headaches, and beta-carotene & lung cancer. Full text extracted from
real PDFs, cleaned, and cited with title/journal/DOI headers in
`data/health_papers/`.

## Repo layout

```
memory_layer/           Cognee - add/cognify/search
storage_layer/          HydraDB - ingest/recall the durable graph
query_layer/            hotdata.dev - ad-hoc SQL analytics
orchestration_layer/    RocketRide - decide + act (real hosted pipeline)
muscle_memory/          local replay-ledger cache (Rote-inspired, not the product)
agent/                  FastAPI app + the ClaimChecker pipeline
frontend/               index.html (manual tool), feed.html, trends.html
scripts/                corpus priming + cleaning scripts
data/health_papers/     cleaned, cited full text of the 13-paper corpus
data/sample_papers/     original PDFs the corpus was extracted from
data/pipelines/         research_finding.pipe - the real RocketRide pipeline definition
```
Results:

Not a health claim - so it doesnt highlight. 

<img width="417" height="896" alt="image" src="https://github.com/user-attachments/assets/7459da7d-500e-4b9f-8242-aba4fee26031" />



The below one is a health claim, so it shows the option to validate/contradict

![Uploading image.png…]()

