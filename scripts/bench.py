"""Repeat the preset migration with each repair model and tabulate outcome, cost and time.

Usage: uv run python scripts/bench.py [--super 5] [--lightning 5] [--ultra 2]
Each trial runs in its own temp copy of the fixture; trials run in parallel batches.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

from upgradepilot.runner import LIGHTNING, SUPER, run_preset  # noqa: E402

ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"


def trial(job):
    name, model = job
    try:
        rep = run_preset(lambda e: None, repair_model=model, budget_usd=0.8)
        l = rep["ledger"]
        return {"model": name, "outcome": rep["outcome"], "reason": rep["reason"], "calls": l["calls"],
                "cost": l["est_cost_usd"], "seconds": l["seconds"]}
    except Exception as e:
        return {"model": name, "outcome": "error", "reason": f"{type(e).__name__}: {e}", "calls": 0, "cost": 0, "seconds": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--super", type=int, default=5)
    ap.add_argument("--lightning", type=int, default=5)
    ap.add_argument("--ultra", type=int, default=2)
    a = ap.parse_args()
    jobs = [("super", SUPER)] * a.super + [("lightning", LIGHTNING)] * a.lightning + [("ultra", ULTRA)] * a.ultra
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(trial, jobs))
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs" / "bench.json").write_text(json.dumps(results, indent=1))
    for name in ("super", "lightning", "ultra"):
        rs = [r for r in results if r["model"] == name]
        if not rs:
            continue
        ok = [r for r in rs if r["outcome"] == "success"]
        print(f"{name}: {len(ok)}/{len(rs)} passed | cost ${min(r['cost'] for r in rs):.3f}-${max(r['cost'] for r in rs):.3f} "
              f"(mean ${sum(r['cost'] for r in rs) / len(rs):.3f}) | model time {min(r['seconds'] for r in rs):.0f}-"
              f"{max(r['seconds'] for r in rs):.0f}s | reasons: {sorted(set(r['reason'] for r in rs))}")


if __name__ == "__main__":
    main()
