import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
FIXTURE = DEMO / "pydantic_service"
SOLUTION = DEMO / "pydantic_service_solution"
VENV_OLD, VENV_NEW = DEMO / ".venv-old", DEMO / ".venv-new"
PY_OLD, PY_NEW = VENV_OLD / "bin" / "python", VENV_NEW / "bin" / "python"
BASELINE_TESTS = 21

needs_envs = pytest.mark.skipif(not (PY_OLD.exists() and PY_NEW.exists() and FIXTURE.exists() and SOLUTION.exists()),
                                reason="demo/.venv-old, demo/.venv-new and the demo fixtures are required")


def apply_solution(work: Path) -> None:
    """Replace the project's app/ with the reference migration."""
    for f in (SOLUTION / "app").glob("*.py"):
        shutil.copy(f, work / "app" / f.name)
