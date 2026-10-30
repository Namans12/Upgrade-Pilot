"""python -m upgradepilot.cli  — run the pipeline on the bundled fixture and print the events."""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .agent import Pipeline

ROOT = Path(__file__).resolve().parent.parent
LIGHTNING = "nvidia/Nemotron-3_5-Lightning"


def main() -> None:
    load_dotenv(ROOT.parent / ".env")
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=LIGHTNING)
    ap.add_argument("--helper-model", default=LIGHTNING)
    ap.add_argument("--fallback", default="", help="model to escalate to when repairs stall")
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--budget", type=float, default=0.5)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    def emit(kind, **d):
        brief = {k: (v if len(str(v)) < 300 else str(v)[:300] + "…") for k, v in d.items()}
        print(f"[{kind}]", json.dumps(brief, ensure_ascii=False), flush=True)

    demo = ROOT / "demo"
    p = Pipeline(demo / "pydantic_service", demo / ".venv-old", demo / ".venv-new", a.model, a.helper_model,
                 emit=emit, max_turns=a.max_turns, budget_usd=a.budget, fallback_model=a.fallback or None)
    report = p.run()
    print("\n=== OUTCOME:", report["outcome"], "-", report["reason"])
    print(json.dumps(report["ledger"], indent=2))
    print(report["diff"])
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2))
    sys.exit(0 if report["outcome"] == "success" else 1)


if __name__ == "__main__":
    main()
