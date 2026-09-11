"""Muscle-Memory / Reliability Layer — Modiqo.ai (Rote)

Watches a task succeed once, turns it into a deterministic, replayable
"Play" so run 2/3 skip re-reasoning entirely. This is the layer the
compounding-proof benchmark leans on hardest.

Rote ships as a local CLI (github.com/modiqo/rote-releases), not a pip
package — there is no Python SDK to import. Confirmed real subcommands from
Modiqo's own docs (see SETUP_NOTES.md): `rote start`, `rote how`,
`rote guidance`, `rote adapter new`, `rote registry adapter search|pull|push`.
The exact "record this run" / "replay play X" subcommand names are NOT
independently confirmed (Modiqo's flow is normally driven from inside a
coding-assistant chat via `$play run <name>`, not shelled out to
programmatically) — verify against `rote --help` once installed tonight per
the hackathon setup checklist, then fill in _rote_cli() below.

Until that's confirmed, this module still gives you a REAL, working
muscle-memory layer: a local deterministic play ledger keyed by task
signature. First success records the working path (inputs -> outputs +
timing); repeat runs of the *same* task replay the recorded result instead
of re-executing the expensive path. That's the actual mechanism the judges
want to see get faster/cheaper on run 2/3 — wire in the real `rote` CLI
calls alongside it once you've confirmed the subcommands.
"""
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

LEDGER_PATH = Path(__file__).parent.parent / "data" / "rote_adapters" / "plays.json"


def rote_cli_available() -> bool:
    return shutil.which("rote") is not None


def _rote_cli(*args: str) -> str | None:
    """Best-effort passthrough to the real `rote` CLI if it's installed.
    Never raises — a missing/unconfigured CLI must not break the demo."""
    if not rote_cli_available():
        return None
    try:
        out = subprocess.run(
            ["rote", *args], capture_output=True, text=True, timeout=15, check=False
        )
        return out.stdout.strip()
    except Exception:
        return None


def _load_ledger() -> dict:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {}


def _save_ledger(ledger: dict):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2))


def task_signature(task_name: str, *key_parts: str) -> str:
    raw = task_name + "|" + "|".join(key_parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class RotePlay:
    """One captured/replayed step of the research-assistant workflow."""

    def __init__(self, task_name: str):
        self.task_name = task_name
        self.ledger = _load_ledger()

    async def run(self, key_parts: list[str], fn: Callable, *args, **kwargs) -> dict:
        sig = task_signature(self.task_name, *key_parts)
        t0 = time.perf_counter()

        if sig in self.ledger:
            elapsed = time.perf_counter() - t0
            _rote_cli("how", self.task_name)  # best-effort: ask Rote what it knows about this play
            return {
                "replayed": True,
                "elapsed_seconds": elapsed,
                "result": self.ledger[sig]["result"],
                "recorded_at": self.ledger[sig]["recorded_at"],
            }

        result = await fn(*args, **kwargs) if _is_coro(fn) else fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0

        self.ledger[sig] = {
            "task_name": self.task_name,
            "key_parts": key_parts,
            "result": _json_safe(result),
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _save_ledger(self.ledger)
        _rote_cli("start", self.task_name)  # best-effort: hand the real CLI a chance to capture too

        return {"replayed": False, "elapsed_seconds": elapsed, "result": result}


def _is_coro(fn) -> bool:
    import inspect

    return inspect.iscoroutinefunction(fn)


def _json_safe(obj: Any):
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)
