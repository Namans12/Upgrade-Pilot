"""Runs the fixture's tests against a prebuilt virtualenv.

This is dependency isolation, not security isolation: only our fixed demo
fixture is ever executed, and the subprocess gets a scrubbed environment so
API keys are never visible to model-edited code.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_OUTPUT = 6000


def new_workdir(fixture: Path) -> Path:
    """Copy the fixture into a fresh temp directory (never touches the original)."""
    work = Path(tempfile.mkdtemp(prefix="upgradepilot-")) / "project"
    shutil.copytree(fixture, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return work


def _env(home: Path) -> dict:
    return {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1"}


def run_tests(work: Path, python: Path, timeout: int = 120) -> dict:
    try:
        p = subprocess.run(
            [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short", "--no-header"],
            cwd=work, env=_env(work.parent), capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr).strip()
        status = "passed" if p.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        out, status = f"pytest timed out after {timeout}s", "inconclusive"
    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT // 2] + "\n...[truncated]...\n" + out[-MAX_OUTPUT // 2:]
    return {"status": status, "output": out}


def run_python(work: Path, python: Path, code: str, timeout: int = 30) -> str:
    """Run a short diagnostic snippet in the project's target environment."""
    try:
        p = subprocess.run([str(python), "-c", code], cwd=work, env=_env(work.parent),
                           capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        out = f"snippet timed out after {timeout}s"
    return out[:MAX_OUTPUT]


def installed_version(work: Path, python: Path, package: str = "pydantic") -> str:
    p = subprocess.run([str(python), "-c", f"import {package}; print({package}.VERSION)"],
                       cwd=work, env=_env(work.parent), capture_output=True, text=True, timeout=30)
    return p.stdout.strip() or p.stderr.strip()[-200:]


def hash_tree(root: Path) -> dict:
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(root.rglob("*")) if f.is_file() and "__pycache__" not in f.parts}
