import re
import threading
import time

import pytest
from fastapi.testclient import TestClient

from helpers import needs_envs


@pytest.fixture
def client(server):
    return TestClient(server.app, raise_server_exceptions=False)


@pytest.fixture
def live(server, monkeypatch):
    """Access code set, preflight satisfied, the pipeline replaced by a quick fake."""
    monkeypatch.setenv("UP_ACCESS_CODE", "testcode")
    monkeypatch.setattr(server, "_preflight", lambda: None)

    def fake(sink):
        sink({"t": 0, "kind": "stage", "data": {"name": "baseline"}})
        sink({"t": 1, "kind": "report", "data": {}})
    monkeypatch.setattr(server, "run_preset", fake)
    return server


def wait_idle(server):
    deadline = time.time() + 5
    while server._lock.locked() and time.time() < deadline:
        time.sleep(0.02)
    assert not server._lock.locked()


def test_config_shape(client):
    body = client.get("/api/config").json()
    assert {"live_enabled", "has_recording", "fixture"} <= body.keys()
    assert body["fixture"] == {"package": "pydantic", "from": "1.10.27", "to": "2.14.2"}


def test_recording(client, server):
    assert client.get("/api/recording").status_code == (200 if server.RECORDING.exists() else 404)


def test_wrong_code_is_403(live, client):
    r = client.post("/api/run", json={"access_code": "nope"})
    assert r.status_code == 403
    assert not live._lock.locked() and live._day["count"] == 0


def test_too_many_wrong_codes_get_429_even_for_the_right_code(live, client):
    for _ in range(live.FAIL_LIMIT):
        assert client.post("/api/run", json={"access_code": "nope"}).status_code == 403
    assert client.post("/api/run", json={"access_code": "nope"}).status_code == 429
    assert client.post("/api/run", json={"access_code": "testcode"}).status_code == 429  # window still closed


def test_oversized_code_is_rejected(live, client):
    assert client.post("/api/run", json={"access_code": "x" * 5000}).status_code == 422


def test_security_headers_and_no_docs(client):
    r = client.get("/")
    assert r.headers["x-frame-options"] == "DENY" and "default-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404


def test_run_disabled_without_access_code(live, client, monkeypatch):
    monkeypatch.delenv("UP_ACCESS_CODE")
    assert client.post("/api/run", json={"access_code": ""}).status_code == 403


def test_non_ascii_access_codes(live, client, monkeypatch):
    assert client.post("/api/run", json={"access_code": "tëstcode✓"}).status_code == 403
    lone_surrogate = client.post("/api/run", content=b'{"access_code": "\\ud800"}', headers={"content-type": "application/json"})
    assert lone_surrogate.status_code == 403
    monkeypatch.setenv("UP_ACCESS_CODE", "pässwörd✓")
    assert client.post("/api/run", json={"access_code": "pässwörd✓"}).status_code == 200


@pytest.mark.parametrize("missing", ["NEBIUS_API_KEY", "TAVILY_API_KEY"])
def test_preflight_missing_key(server, client, monkeypatch, missing):
    monkeypatch.setenv("UP_ACCESS_CODE", "testcode")
    monkeypatch.setenv(missing, "  ")
    r = client.post("/api/run", json={"access_code": "testcode"})
    assert r.status_code == 503 and missing in r.json()["detail"]
    assert not server._lock.locked() and server._day["count"] == 0
    assert client.get("/api/config").json()["live_ready"] is False


def test_preflight_missing_venv(server, client, monkeypatch, tmp_path):
    monkeypatch.setenv("UP_ACCESS_CODE", "testcode")
    monkeypatch.setattr(server, "DEMO", tmp_path)
    r = client.post("/api/run", json={"access_code": "testcode"})
    assert r.status_code == 503 and ".venv-old" in r.json()["detail"]
    for name in (".venv-old", ".venv-new"):
        (tmp_path / name / "bin").mkdir(parents=True)
        (tmp_path / name / "bin" / "python").write_text("")
    assert server._preflight() is None


def test_run_streams_and_is_evicted(live, client, monkeypatch):
    monkeypatch.setattr(live, "RUN_TTL_SECONDS", 0.3)
    r = client.post("/api/run", json={"access_code": "testcode"})
    run_id = r.json()["run_id"]
    assert re.fullmatch(r"[0-9a-f]{16}", run_id)
    body = client.get(f"/api/run/{run_id}/events").text
    assert '"kind": "stage"' in body and '"kind": "report"' in body and body.rstrip().endswith("event: end\ndata: {}")
    wait_idle(live)
    assert live._day["count"] == 1
    deadline = time.time() + 5
    while run_id in live.RUNS and time.time() < deadline:
        time.sleep(0.05)
    assert run_id not in live.RUNS
    assert client.get(f"/api/run/{run_id}/events").status_code == 404


def test_internal_errors_are_not_echoed_to_viewers(live, client, monkeypatch):
    def boom(sink):
        raise RuntimeError("secret-path /srv/key=abc123")
    monkeypatch.setattr(live, "run_preset", boom)
    run_id = client.post("/api/run", json={"access_code": "testcode"}).json()["run_id"]
    body = client.get(f"/api/run/{run_id}/events").text
    assert "RuntimeError" in body and "abc123" not in body and "secret-path" not in body
    wait_idle(live)


def test_daily_cap_and_busy_lock_do_not_leak_counts(live, client, monkeypatch):
    live._lock.acquire()
    try:
        assert client.post("/api/run", json={"access_code": "testcode"}).status_code == 409
        assert live._day["count"] == 0
    finally:
        live._lock.release()
    monkeypatch.setattr(live, "MAX_LIVE_RUNS_PER_DAY", 1)
    assert client.post("/api/run", json={"access_code": "testcode"}).status_code == 200
    wait_idle(live)
    r = client.post("/api/run", json={"access_code": "testcode"})
    assert r.status_code == 429 and not live._lock.locked() and live._day["count"] == 1


def test_thread_start_failure_rolls_back(live, client, monkeypatch):
    def cannot_start(fn):
        raise RuntimeError("can't start new thread")
    monkeypatch.setattr(live, "_spawn", cannot_start)
    assert client.post("/api/run", json={"access_code": "testcode"}).status_code == 500
    assert not live._lock.locked() and live._day["count"] == 0 and not live.RUNS
    monkeypatch.undo()


def test_stream_sends_keepalive_pings(live, client, monkeypatch):
    monkeypatch.setattr(live, "PING_SECONDS", 0.1)
    run = live.RUNS["abc"] = {"events": [], "done": False}
    threading.Timer(0.8, lambda: run.update(done=True)).start()
    body = client.get("/api/run/abc/events").text
    assert ": ping\n\n" in body and body.rstrip().endswith("event: end\ndata: {}")


def test_unknown_run_404(client):
    assert client.get("/api/run/doesnotexist/events").status_code == 404
