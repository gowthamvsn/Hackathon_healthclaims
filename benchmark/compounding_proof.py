"""The judged demo: run the SAME paper through the agent 3 times and show
run 3 doing measurably less work than run 1 — because HydraDB already has
the graph, and Rote already has the play.

Usage: python benchmark/compounding_proof.py [path/to/paper.txt] [topic]
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.pipeline import ResearchAssistantAgent

DEFAULT_PAPER = Path(__file__).parent.parent / "data" / "sample_papers" / "attention_is_all_you_need_abstract.txt"


async def main():
    paper_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PAPER
    topic = sys.argv[2] if len(sys.argv) > 2 else "transformer architecture"
    text = paper_path.read_text()

    agent = ResearchAssistantAgent()
    dataset_name = f"benchmark_{paper_path.stem}"

    runs = []
    for i in range(1, 4):
        t0 = time.perf_counter()
        result = await agent.process_paper(text, dataset_name=dataset_name, topic=topic)
        result["run_number"] = i
        result["wall_clock_seconds"] = time.perf_counter() - t0
        runs.append(result)

        label = "COLD (full extraction)" if not result["replayed_extract"] else "WARM (replayed)"
        print(f"Run {i} [{label}]: {result['wall_clock_seconds']:.3f}s total "
              f"(extract={result['stage_timings_seconds']['extract']:.3f}s, "
              f"analytics={result['stage_timings_seconds']['analytics']:.3f}s, "
              f"orchestrate={result['stage_timings_seconds']['orchestrate']:.3f}s)")

    run1, run3 = runs[0], runs[-1]
    speedup = run1["wall_clock_seconds"] / max(run3["wall_clock_seconds"], 1e-9)

    print()
    print("=" * 60)
    print("COMPOUNDING PROOF")
    print("=" * 60)
    print(f"Run 1 (cold):  {run1['wall_clock_seconds']:.3f}s — extracted claims fresh via Cognee/LLM")
    print(f"Run 3 (warm):  {run3['wall_clock_seconds']:.3f}s — replayed via HydraDB + Rote")
    print(f"Speedup:       {speedup:.1f}x faster on run 3")
    print(f"LLM extraction skipped on run 3: {run3['replayed_extract']}")

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"compounding_proof_{int(time.time())}.json"
    out_path.write_text(json.dumps({"runs": runs, "speedup_run1_vs_run3": speedup}, indent=2, default=str))
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
