"""Checks that a green run is an honest one: nothing outside app/ touched, right version,
exactly the baseline number of tests passing, no pydantic.v1 escape hatch, no deprecated v1 APIs left."""
import re
from pathlib import Path

from . import sandbox

# Deprecated-in-v2 spellings; a migration that merely keeps them hasn't migrated.
BANNED = [
    (r"\.dict\(", ".dict() (use model_dump)"),
    (r"\.parse_obj\(", ".parse_obj() (use model_validate)"),
    (r"\.parse_raw\(", ".parse_raw() (use model_validate_json)"),
    (r"\.json\(", ".json() (use model_dump_json)"),
    (r"\.copy\(", ".copy() (use model_copy)"),
    (r"\.from_orm\(", ".from_orm() (use model_validate + from_attributes)"),
    (r"@validator\b", "@validator (use field_validator)"),
    (r"@root_validator\b", "@root_validator (use model_validator)"),
    (r"class Config\b", "class Config (use model_config)"),
    (r"__root__", "__root__ (use RootModel)"),
    (r"pydantic\.v1", "pydantic.v1 compatibility import"),
    # app/ is plain data-model code; anything that can reach the process, the OS or the import system
    # could fake a green test run, so it is rejected outright
    (r"^\s*(import|from)\s+(os|sys|ctypes|subprocess|importlib|builtins|socket|signal|atexit|threading|multiprocessing)\b", "import of a process/OS module"),
    (r"\b_exit\b|\bexec\s*\(|\beval\s*\(|__import__|\bcompile\s*\(|\bopen\s*\(|__builtins__|\bsetattr\s*\(\s*sys", "exec/eval/open/_exit-style escape"),
]


def check(work: Path, python: Path, original_hashes: dict, target_version: str, expected_tests: int) -> dict:
    """original_hashes: sandbox.hash_outside_app of the pristine copy; expected_tests: passed count of the baseline run."""
    results = []
    final = sandbox.run_tests(work, python)  # first, so anything the run itself writes is hashed below
    now = sandbox.hash_outside_app(work)
    changed = sorted(f for f in now.keys() | original_hashes.keys() if now.get(f) != original_hashes.get(f))
    results.append({"check": "tests and project files unchanged", "ok": not changed,
                    "detail": "" if not changed else "modified outside app/: " + ", ".join(changed[:10])})

    version = sandbox.installed_version(work, python)
    results.append({"check": f"pydantic == {target_version}", "ok": version == target_version, "detail": version})

    problems = []
    for f in sorted((work / "app").rglob("*.py")):
        text = f.read_text(errors="replace")
        for pattern, label in BANNED:
            if re.search(pattern, text, re.M):
                problems.append(f"{f.relative_to(work)}: {label}")
    results.append({"check": "no deprecated v1 APIs in app/", "ok": not problems, "detail": "; ".join(problems)})

    passed = sandbox.clean_pass_count(final["output"])
    ok = final["status"] == "passed" and passed == expected_tests
    detail = final["output"].splitlines()[-1] if final["output"] else ""
    if final["status"] == "passed" and not ok:
        detail = f"expected exactly {expected_tests} passed, none failed/skipped/deselected; got: {detail}"
    results.append({"check": "tests pass on target version", "ok": ok, "detail": detail})
    return {"ok": all(r["ok"] for r in results), "checks": results}
