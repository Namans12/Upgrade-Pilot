import time

import pytest

import helpers
from upgradepilot import sandbox


@pytest.fixture(autouse=True)
def fake_keys(monkeypatch):
    """No test may reach a paid API: keys are dummies and every model/search call is patched out."""
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.delenv("UP_SANDBOX_UID", raising=False)


@pytest.fixture
def work():
    w = sandbox.new_workdir(helpers.FIXTURE)
    yield w
    sandbox.remove_workdir(w)


@pytest.fixture
def server(monkeypatch):
    from upgradepilot import server as s
    s.RUNS.clear()
    s._day.update(date=time.strftime("%Y-%m-%d"), count=0)
    monkeypatch.setattr(s, "FAIL_DELAY_SECONDS", 0)
    yield s
    deadline = time.time() + 5
    while s._lock.locked() and time.time() < deadline:
        time.sleep(0.02)
    s.RUNS.clear()
