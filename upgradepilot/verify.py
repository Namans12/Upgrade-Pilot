"""Checks that a green run is an honest one: tests untouched, right version,
no pydantic.v1 escape hatch, no deprecated v1 APIs left in the source."""
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
]


def check(work: Path, python: Path, original_tests: dict, target_version: str) -> dict:
    results = []
    now = sandbox.hash_tree(work / "tests")
    results.append({"check": "tests unchanged", "ok": now == original_tests,
                    "detail": "" if now == original_tests else "test files were modified"})

    version = sandbox.installed_version(work, python)
    results.append({"check": f"pydantic == {target_version}", "ok": version == target_version, "detail": version})

    problems = []
    for f in sorted((work / "app").rglob("*.py")):
        text = f.read_text()
        for pattern, label in BANNED:
            if re.search(pattern, text):
                problems.append(f"{f.relative_to(work)}: {label}")
    results.append({"check": "no deprecated v1 APIs in app/", "ok": not problems, "detail": "; ".join(problems)})

    final = sandbox.run_tests(work, python)
    results.append({"check": "tests pass on target version", "ok": final["status"] == "passed",
                    "detail": final["output"].splitlines()[-1] if final["output"] else ""})
    return {"ok": all(r["ok"] for r in results), "checks": results}
