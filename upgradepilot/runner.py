"""Shared entry point used by the web server and the recording script."""
import time
from pathlib import Path
from typing import Callable

from .agent import Pipeline

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
LIGHTNING = "nvidia/Nemotron-3_5-Lightning"
SUPER = "nvidia/nemotron-3-super-120b-a12b"


def run_preset(sink: Callable[[dict], None], repair_model: str = SUPER, helper_model: str = LIGHTNING,
               budget_usd: float = 0.35) -> dict:
    """Run the bundled Pydantic v1 -> v2 migration, sending timestamped events to `sink`."""
    t0 = time.time()

    def emit(kind: str, **data) -> None:
        sink({"t": round(time.time() - t0, 2), "kind": kind, "data": data})

    pipeline = Pipeline(DEMO / "pydantic_service", DEMO / ".venv-old", DEMO / ".venv-new", repair_model,
                        helper_model, emit=emit, max_turns=40, budget_usd=budget_usd)
    report = pipeline.run()
    sink({"t": round(time.time() - t0, 2), "kind": "report", "data": report})
    return report
