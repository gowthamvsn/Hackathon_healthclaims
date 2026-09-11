# Self-Improving Research Assistant

Built for the **AWS Builder Loft SF** hackathon (Sep 11, 2026) — "Data and AI
Hackathon: From Memory to Muscle Memory." This is the "Self-Improving
Research Assistant" idea from the official builder guide: extract claims,
sources, and contradictions from papers/articles; persist the evolving
research graph; run ad-hoc analytics over it; decide + act on findings; and
get measurably faster/cheaper on repeat runs.

| Layer | Tool | Role |
|---|---|---|
| Memory construction | **Cognee.ai** | ECL pipeline — extracts claims/sources into a knowledge graph |
| Memory storage & serving | **HydraDB** | Durable, cross-session home for that graph; relationship-aware recall |
| Live query & analytics | **hotdata.dev** | Ad-hoc SQL over extracted-claim metadata |
| Motion / orchestration | **RocketRide.ai** | Decides + executes the next action on a finding |
| Muscle memory / reliability | **Modiqo.ai (Rote)** | Captures a successful run, replays it deterministically on repeat |

## Quickstart

```bash
py -3.12 -m venv .venv          # rocketride requires Python 3.11+
.venv\Scripts\activate           # (PowerShell: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt
copy .env.template .env          # then fill in real keys
python scripts\run_smoke_tests.py
python benchmark\compounding_proof.py
```

Modiqo Rote is a separate local CLI (not pip-installable) — install it from
github.com/modiqo/rote-releases per the hackathon setup checklist. The
Python code works with or without it; see `muscle_memory/rote_hook.py`.

## Repo layout

```
memory_layer/          Cognee — add/cognify/search
storage_layer/          HydraDB — ingest/recall the durable graph
query_layer/            hotdata.dev — ad-hoc SQL analytics
orchestration_layer/    RocketRide — decide + act
muscle_memory/          Modiqo Rote — capture + replay
agent/pipeline.py       ties all five layers together
scripts/                one smoke test per layer + a runner
benchmark/              the compounding-proof demo (run 1 vs run 3)
data/sample_papers/     a tiny sample text so smoke tests work offline
data/pipelines/         drop your exported RocketRide .pipe file here
```

See **SETUP_NOTES.md** for exactly which API calls are confirmed against
real installed SDKs vs. what needs a 2-minute check against your dashboard
tomorrow, plus the required Snyk step (scored separately, not a pipeline
layer).
