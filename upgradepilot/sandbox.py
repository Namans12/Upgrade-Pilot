"""Runs the fixture's tests against a prebuilt virtualenv.

This is dependency isolation, not strong security isolation: only our fixed demo
fixture is ever executed, and the subprocess gets a scrubbed environment so
API keys are never visible to model-edited code. When the server runs as root
and UP_SANDBOX_UID is set, model-run code also drops to that unprivileged uid,
so it cannot read the server's /proc/<pid>/environ.
"""
import hashlib
import os
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

MAX_OUTPUT = 6000
CACHE_DIRS = {"__pycache__", ".pytest_cache"}


def _sandbox_uid() -> int | None:
    uid = os.environ.get("UP_SANDBOX_UID", "")
    return int(uid) if uid.isdigit() and os.geteuid() == 0 else None


def _chown_tree(root: Path, uid: int) -> None:
    os.lchown(root, uid, uid)
    for f in root.rglob("*"):
        os.lchown(f, uid, uid)


def new_workdir(fixture: Path) -> Path:
    """Copy the fixture into a fresh temp directory (never touches the original)."""
    work = Path(tempfile.mkdtemp(prefix="upgradepilot-")) / "project"
    shutil.copytree(fixture, work, ignore=shutil.ignore_patterns(*CACHE_DIRS))
    uid = _sandbox_uid()
    if uid is not None:  # mkdtemp's 0700 parent must be traversable by the sandbox uid too
        _chown_tree(work.parent, uid)
    return work


def remove_workdir(work: Path) -> None:
    shutil.rmtree(work.parent, ignore_errors=True)


def _env(home: Path) -> dict:
    return {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1"}


def _limits() -> None:
    """Runs in the child before exec: cap CPU time, open files, file size and address space."""
    for res, val in ((resource.RLIMIT_CPU, 150), (resource.RLIMIT_NOFILE, 256),
                     (resource.RLIMIT_FSIZE, 50 * 2**20), (resource.RLIMIT_AS, 3 * 2**30)):
        try:
            resource.setrlimit(res, (val, val))
        except (ValueError, OSError):  # e.g. RLIMIT_AS is not enforceable on macOS
            pass


def _run(cmd: list, work: Path, timeout: int) -> subprocess.CompletedProcess:
    kw = {}
    uid = _sandbox_uid()
    if uid is not None:
        kw = {"user": uid, "group": uid, "extra_groups": []}
    # own session so a timeout kills the whole process group, grandchildren included
    proc = subprocess.Popen(cmd, cwd=work, env=_env(work.parent), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True, preexec_fn=_limits, **kw)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.communicate()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _purge_caches(work: Path) -> None:
    """Nothing legitimate writes bytecode here (PYTHONDONTWRITEBYTECODE), so a stray cache could only be planted."""
    for d in [d for d in work.rglob("*") if d.name in CACHE_DIRS and d.is_dir() and not d.is_symlink()]:
        shutil.rmtree(d, ignore_errors=True)


def run_tests(work: Path, python: Path, timeout: int = 120) -> dict:
    _purge_caches(work)
    try:
        # --noconftest: model-written conftest.py files must not be able to steer collection or the exit status
        p = _run([str(python), "-m", "pytest", "tests", "--noconftest", "-q", "-p", "no:cacheprovider",
                  "--tb=short", "--no-header"], work, timeout)
        out = (p.stdout + p.stderr).strip()
        status = "passed" if p.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        out, status = f"pytest timed out after {timeout}s", "inconclusive"
    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT // 2] + "\n...[truncated]...\n" + out[-MAX_OUTPUT // 2:]
    return {"status": status, "output": out}


def clean_pass_count(output: str) -> int | None:
    """N from pytest's final '-q' summary line when it reports only passes (warnings aside), else None.
    Any failed/error/skipped/deselected/xfail count, or a missing summary, makes the run not clean."""
    lines = output.strip().splitlines()
    if not lines or not re.search(r"\bin [\d.]+s\b", lines[-1]):
        return None
    counts = {word: int(n) for n, word in re.findall(r"(\d+) (\w+)", lines[-1].split(" in ")[0])}
    if set(counts) - {"passed", "warning", "warnings"}:
        return None
    return counts.get("passed")


def run_python(work: Path, python: Path, code: str, timeout: int = 30) -> str:
    """Run a short diagnostic snippet in the project's target environment."""
    try:
        p = _run([str(python), "-c", code], work, timeout)
        out = (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        out = f"snippet timed out after {timeout}s"
    return out[:MAX_OUTPUT]


def installed_version(work: Path, python: Path, package: str = "pydantic") -> str:
    try:  # -I: ignore the cwd and PYTHON* variables, so a stray pydantic.py cannot answer for the real one
        p = _run([str(python), "-I", "-c", f"import {package}; print({package}.VERSION)"], work, 30)
    except subprocess.TimeoutExpired:
        return "version check timed out after 30s"
    return p.stdout.strip() or p.stderr.strip()[-200:]


def hash_tree(root: Path, skip: tuple = ()) -> dict:
    """{relative path: sha256} for every file under root, symlinks recorded by target.
    Bytecode/pytest caches and the top-level directories named in `skip` are ignored."""
    out = {}
    for dirpath, dirs, files in os.walk(root):
        here = Path(dirpath)
        dirs[:] = sorted(d for d in dirs if d not in CACHE_DIRS and (here / d).relative_to(root).as_posix() not in skip)
        for name in sorted(files + dirs):
            f = here / name
            rel = f.relative_to(root).as_posix()
            if f.is_symlink():
                out[rel] = "symlink:" + os.readlink(f)
            elif f.is_file():
                out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def hash_outside_app(work: Path) -> dict:
    """Everything the model must not change: tests, conftest/ini files, requirements, any stray file."""
    return hash_tree(work, skip=("app",))
