import json
from types import SimpleNamespace

import pytest

import helpers
from helpers import needs_envs
from upgradepilot import agent, research, sandbox


def make_pipeline(**kw):
    return agent.Pipeline(helpers.FIXTURE, helpers.VENV_OLD, helpers.VENV_NEW, "repair-model", "helper-model", **kw)


def call(name, **args):
    raw = args.pop("_raw", None)
    return SimpleNamespace(id=f"c-{name}", function=SimpleNamespace(name=name, arguments=raw or json.dumps(args)))


def msg(*calls, content=""):
    m = SimpleNamespace(content=content, tool_calls=list(calls) or None)
    m.model_dump = lambda exclude_none=True: {"role": "assistant", "content": content}
    return m


def script(monkeypatch, p, turns):
    """Replace the model with a fixed list of assistant messages; returns the shared message history."""
    history, it = [], iter(turns)
    monkeypatch.setattr(research, "find_migration_guide",
                        lambda *a: {"query_hits": [], "source_url": "https://docs.example/x", "page": ""})
    monkeypatch.setattr(p, "_condense", lambda *a: "notes")

    def fake_chat(step, model, messages, **kw):
        history[:] = messages
        return next(it)
    monkeypatch.setattr(p, "_chat", fake_chat)
    return history


def test_client_has_bounded_timeout_and_retries():
    p = make_pipeline()
    assert p.client.max_retries == 1 and p.client.timeout == 90


@pytest.mark.parametrize("rel", ["app/models.py", "app/sub/new_module.py", "app/__init__.py"])
def test_safe_allows_app_python(work, rel):
    assert make_pipeline()._safe(work, rel, True) == (work / rel).resolve()


@pytest.mark.parametrize("rel", [
    "app/conftest.py", "app/Conftest.PY", "app/sitecustomize.py", "app/usercustomize.py",
    "app/pydantic.py", "app/pydantic_core.py", "app/pytest.py", "app/pytest_plugin.py", "app/_pytest.py",
    "app/data.json", "app/pytest.ini", "app/noext",
    "conftest.py", "pytest.ini", "pydantic.py", "sitecustomize.py", "tests/test_models.py", "tests/conftest.py",
    "requirements.txt", "../escape.py", "app/../conftest.py", "/etc/passwd",
])
def test_safe_rejects_hooks_shadows_and_non_app_writes(work, rel):
    with pytest.raises(PermissionError):
        make_pipeline()._safe(work, rel, True)


def test_safe_reads_unchanged(work):
    p = make_pipeline()
    for rel in ("app/models.py", "tests/test_models.py", "requirements.txt"):
        p._safe(work, rel, False)
    with pytest.raises(PermissionError):
        p._safe(work, "pytest.ini", False)


def test_write_file_tool_reports_rejection_to_the_model(work):
    out = make_pipeline()._tool(work, "write_file", {"path": "app/conftest.py", "content": "x"})
    assert out.startswith("ERROR: PermissionError") and not (work / "app" / "conftest.py").exists()


def test_report_diffs_added_and_deleted_files(work):
    original = agent.app_sources(work)
    (work / "app" / "brand_new.py").write_text("X = 1\n")
    (work / "app" / "tags.py").unlink()
    (work / "app" / "models.py").write_text("changed = True\n")
    diff = make_pipeline()._report(work, original, "inconclusive", "x")["diff"]
    assert "--- /dev/null\n+++ b/app/brand_new.py" in diff and "+X = 1" in diff
    assert "--- a/app/tags.py\n+++ /dev/null" in diff
    assert "--- a/app/models.py\n+++ b/app/models.py" in diff


@needs_envs
def test_non_dict_tool_arguments_do_not_crash_the_loop(monkeypatch):
    p = make_pipeline(max_turns=2)
    history = script(monkeypatch, p, [msg(call("write_file", _raw="[1, 2]"), call("read_file", _raw='"x"')),
                                      msg(content="done")])
    rep = p.run()
    tool_msgs = [m["content"] for m in history if m["role"] == "tool"]
    assert tool_msgs == ["ERROR: tool arguments must be a JSON object"] * 2
    assert rep["outcome"] == "inconclusive"


@needs_envs
def test_time_limit_ends_the_run_and_workdir_is_removed(monkeypatch):
    made = []
    real = sandbox.new_workdir
    monkeypatch.setattr(sandbox, "new_workdir", lambda f: made.append(real(f)) or made[-1])
    p = make_pipeline(max_seconds=0)
    script(monkeypatch, p, [])  # any model call would raise StopIteration
    rep = p.run()
    assert (rep["outcome"], rep["reason"]) == ("inconclusive", "time limit reached")
    assert not made[0].parent.exists()


def test_max_seconds_env_default(monkeypatch):
    assert make_pipeline().max_seconds == 300
    monkeypatch.setenv("UP_MAX_RUN_SECONDS", "42")
    assert make_pipeline().max_seconds == 42


@needs_envs
def test_scripted_honest_migration_goes_green(monkeypatch):
    p = make_pipeline(max_turns=4)
    writes = [call("write_file", path=f"app/{f.name}", content=f.read_text())
              for f in sorted((helpers.SOLUTION / "app").glob("*.py"))]
    script(monkeypatch, p, [msg(*writes, call("run_tests")), msg(content="migrated")])
    rep = p.run()
    assert (rep["outcome"], rep["reason"]) == ("success", "all checks passed"), rep["verification"]
    assert "+++ b/app/models.py" in rep["diff"]


@needs_envs
def test_scripted_fake_green_attempt_is_not_success(monkeypatch):
    p = make_pipeline(max_turns=3)
    hook = "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n"
    snippet = f"open('conftest.py', 'w').write({hook!r})"
    script(monkeypatch, p, [
        msg(call("write_file", path="app/conftest.py", content=hook), call("run_python", code=snippet),
            call("run_tests")),
        msg(content="all green, trust me"),
        msg(content="really"),
    ])
    rep = p.run()
    assert rep["outcome"] == "inconclusive" and not rep["verification"]["ok"]
    assert not rep["verification"]["checks"][0]["ok"]
