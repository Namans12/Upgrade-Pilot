import os
import subprocess
from pathlib import Path

import pytest

import helpers
from helpers import needs_envs
from upgradepilot import sandbox, verify

FAKE_GREEN_CONFTEST = "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n"


@pytest.mark.parametrize("out,expected", [
    ("21 passed in 0.07s", 21),
    ("21 passed, 3 warnings in 0.30s", 21),
    ("21 passed in 61.2s (0:01:01)", 21),
    ("1 failed, 20 passed in 0.1s", None),
    ("20 passed, 1 skipped in 0.1s", None),
    ("21 passed, 1 deselected in 0.1s", None),
    ("20 passed, 1 error in 0.1s", None),
    ("20 passed, 1 xfailed in 0.1s", None),
    ("no tests ran in 0.01s", None),
    ("21 passed", None),
    ("", None),
])
def test_clean_pass_count(out, expected):
    assert sandbox.clean_pass_count("noise\n" + out if out else out) == expected


def test_hash_tree_ignores_caches_and_records_symlinks(work):
    (work / "__pycache__").mkdir()
    (work / "__pycache__" / "x.pyc").write_bytes(b"junk")
    (work / "tests" / "__pycache__").mkdir()
    (work / "tests" / "__pycache__" / "y.pyc").write_bytes(b"junk")
    (work / ".pytest_cache").mkdir()
    (work / ".pytest_cache" / "z").write_text("junk")
    (work / "dangling").symlink_to("/nonexistent")
    h = sandbox.hash_outside_app(work)
    assert not any("__pycache__" in k or ".pytest_cache" in k or k.startswith("app/") for k in h)
    assert "tests/test_models.py" in h and "requirements.txt" in h
    assert h["dangling"] == "symlink:/nonexistent"


def test_sandbox_uid_only_for_root(monkeypatch):
    monkeypatch.setenv("UP_SANDBOX_UID", "65534")
    monkeypatch.setattr(sandbox.os, "geteuid", lambda: 1000)
    assert sandbox._sandbox_uid() is None
    monkeypatch.setattr(sandbox.os, "geteuid", lambda: 0)
    assert sandbox._sandbox_uid() == 65534
    monkeypatch.setenv("UP_SANDBOX_UID", "")
    assert sandbox._sandbox_uid() is None
    monkeypatch.setenv("UP_SANDBOX_UID", "nobody")
    assert sandbox._sandbox_uid() is None


def test_subprocess_drops_privileges_when_configured(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(sandbox.subprocess, "run", lambda *a, **kw: seen.append(kw) or subprocess.CompletedProcess(a, 0, "", ""))
    sandbox._run(["true"], tmp_path, 5)
    assert "user" not in seen[-1]
    monkeypatch.setattr(sandbox, "_sandbox_uid", lambda: 65534)
    sandbox._run(["true"], tmp_path, 5)
    assert (seen[-1]["user"], seen[-1]["group"], seen[-1]["extra_groups"]) == (65534, 65534, [])
    assert "NEBIUS_API_KEY" not in seen[-1]["env"]


def test_workdir_is_chowned_to_sandbox_uid(monkeypatch):
    calls = []
    monkeypatch.setattr(sandbox, "_sandbox_uid", lambda: 65534)
    monkeypatch.setattr(sandbox.os, "lchown", lambda p, u, g: calls.append((Path(p), u, g)))
    w = sandbox.new_workdir(helpers.FIXTURE)
    try:
        chowned = {p for p, u, g in calls if (u, g) == (65534, 65534)}
        assert w.parent in chowned and w in chowned and w / "tests" / "test_models.py" in chowned
    finally:
        sandbox.remove_workdir(w)


def test_remove_workdir(work):
    sandbox.remove_workdir(work)
    assert not work.parent.exists()


def test_timeouts_are_reported_not_raised(work, monkeypatch):
    def boom(*a, **kw):
        raise subprocess.TimeoutExpired("x", 1)
    monkeypatch.setattr(sandbox, "_run", boom)
    assert sandbox.run_tests(work, helpers.PY_NEW)["status"] == "inconclusive"
    assert "timed out" in sandbox.run_python(work, helpers.PY_NEW, "pass")
    assert "timed out" in sandbox.installed_version(work, helpers.PY_NEW)
    v = verify.check(work, helpers.PY_NEW, sandbox.hash_outside_app(work), "2.14.2", 21)
    assert v["ok"] is False and all(c["check"] for c in v["checks"])


@needs_envs
def test_baseline_counts_21_passed(work):
    res = sandbox.run_tests(work, helpers.PY_OLD)
    assert res["status"] == "passed"
    assert sandbox.clean_pass_count(res["output"]) == helpers.BASELINE_TESTS


@needs_envs
def test_conftest_cannot_fake_a_green_run(work):
    assert sandbox.run_tests(work, helpers.PY_NEW)["status"] == "failed"  # unmigrated source fails on v2
    for rel in ("conftest.py", "app/conftest.py", "tests/conftest.py"):
        (work / rel).write_text(FAKE_GREEN_CONFTEST)
    res = sandbox.run_tests(work, helpers.PY_NEW)
    assert res["status"] == "failed" and sandbox.clean_pass_count(res["output"]) is None


@needs_envs
def test_verify_accepts_the_reference_migration(work):
    original = sandbox.hash_outside_app(work)
    helpers.apply_solution(work)
    v = verify.check(work, helpers.PY_NEW, original, "2.14.2", helpers.BASELINE_TESTS)
    assert v["ok"], v


def _tamper_conftest(w): (w / "conftest.py").write_text(FAKE_GREEN_CONFTEST)
def _tamper_ini(w): (w / "pytest.ini").write_text("[pytest]\naddopts = --co\n")
def _tamper_shadow(w): (w / "pydantic.py").write_text("VERSION = '2.14.2'\n")
def _tamper_sitecustomize(w): (w / "sitecustomize.py").write_text("import os\n")
def _tamper_test(w): (w / "tests" / "test_models.py").write_text("def test_x():\n    pass\n")
def _tamper_new_test(w): (w / "tests" / "test_extra.py").write_text("def test_y():\n    pass\n")
def _tamper_delete_test(w): (w / "tests" / "test_errors.py").unlink()
def _tamper_requirements(w): (w / "requirements.txt").write_text("pydantic==2.14.2\n")
def _tamper_symlink(w): (w / "evil").symlink_to("/nonexistent")
def _tamper_pyc(w): (w / "pydantic.pyc").write_bytes(b"\0")


@needs_envs
@pytest.mark.parametrize("tamper", [_tamper_conftest, _tamper_ini, _tamper_shadow, _tamper_sitecustomize, _tamper_test,
                                    _tamper_new_test, _tamper_delete_test, _tamper_requirements, _tamper_symlink,
                                    _tamper_pyc])
def test_verify_rejects_any_change_outside_app(work, tamper):
    original = sandbox.hash_outside_app(work)
    helpers.apply_solution(work)
    tamper(work)
    v = verify.check(work, helpers.PY_NEW, original, "2.14.2", helpers.BASELINE_TESTS)
    assert not v["ok"] and not v["checks"][0]["ok"]


@needs_envs
def test_verify_ignores_cache_junk(work):
    original = sandbox.hash_outside_app(work)
    helpers.apply_solution(work)
    for d in ("__pycache__", "tests/__pycache__", "app/__pycache__", ".pytest_cache"):
        (work / d).mkdir(exist_ok=True)
        (work / d / "junk.pyc").write_bytes(b"junk")
    assert verify.check(work, helpers.PY_NEW, original, "2.14.2", helpers.BASELINE_TESTS)["ok"]


@needs_envs
@pytest.mark.parametrize("expected", [20, 22])
def test_verify_requires_baseline_test_count(work, expected):
    original = sandbox.hash_outside_app(work)
    helpers.apply_solution(work)
    v = verify.check(work, helpers.PY_NEW, original, "2.14.2", expected)
    assert not v["ok"] and not v["checks"][-1]["ok"]


@needs_envs
def test_snippet_cannot_plant_files_unnoticed(work):
    original = sandbox.hash_outside_app(work)
    helpers.apply_solution(work)
    sandbox.run_python(work, helpers.PY_NEW, "open('conftest.py', 'w').write('import os\\n')")
    assert (work / "conftest.py").exists()
    v = verify.check(work, helpers.PY_NEW, original, "2.14.2", helpers.BASELINE_TESTS)
    assert not v["ok"] and "conftest.py" in v["checks"][0]["detail"]


@needs_envs
def test_stray_pydantic_module_cannot_fake_the_version(work):
    (work / "pydantic.py").write_text("VERSION = '9.9.9'\n")
    assert sandbox.installed_version(work, helpers.PY_NEW) == "2.14.2"


@needs_envs
def test_planted_bytecode_is_purged_before_tests(work):
    (work / "tests" / "__pycache__").mkdir()
    (work / "tests" / "__pycache__" / "test_models.cpython-312.pyc").write_bytes(b"junk")
    sandbox.run_tests(work, helpers.PY_OLD)
    assert not (work / "tests" / "__pycache__").exists()
