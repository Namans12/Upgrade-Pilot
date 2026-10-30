"""Record a real live run so the web UI can replay it (clearly labelled as recorded)."""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT.parent / ".env")

from upgradepilot.runner import run_preset  # noqa: E402


def main() -> None:
    events: list = []
    report = run_preset(lambda e: (events.append(e), print(e["t"], e["kind"], flush=True)))
    out = ROOT / "recordings" / "pydantic_run.json"
    if report["outcome"] != "success":
        out = ROOT / "recordings" / f"failed_{len(events)}.json"
        print("NOT a success; saved separately:", out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"recorded": True, "events": events}, indent=1, default=str))
    print("saved", out, report["outcome"], report["ledger"]["est_cost_usd"])


if __name__ == "__main__":
    main()
