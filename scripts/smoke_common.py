import time
from dataclasses import dataclass

from agent.config import MissingCredential


@dataclass
class SmokeResult:
    layer: str
    status: str  # PASS | FAIL | SKIP
    message: str
    seconds: float = 0.0


async def run_smoke(layer: str, coro_fn) -> SmokeResult:
    t0 = time.perf_counter()
    try:
        message = await coro_fn()
        return SmokeResult(layer, "PASS", message, time.perf_counter() - t0)
    except MissingCredential as e:
        return SmokeResult(layer, "SKIP", str(e), time.perf_counter() - t0)
    except Exception as e:  # noqa: BLE001 — smoke tests must report, never crash the runner
        return SmokeResult(layer, "FAIL", f"{type(e).__name__}: {e}", time.perf_counter() - t0)
