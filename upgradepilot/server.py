"""FastAPI app: live runs (access-code gated, one at a time) and a recorded run for replay."""
import asyncio
import json
import logging
import os
import secrets
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from .runner import DEMO, ROOT, run_preset
from .sandbox import _sandbox_uid as sandbox_uid

load_dotenv(ROOT / ".env")  # neither call overrides variables that are already set
load_dotenv(ROOT.parent / ".env")

WEB = ROOT / "web"
RECORDING = ROOT / "recordings" / "pydantic_run.json"
MAX_LIVE_RUNS_PER_DAY = int(os.environ.get("UP_MAX_LIVE_RUNS", "30"))
RUN_TTL_SECONDS = 300  # a finished run stays replayable this long, then is evicted
PING_SECONDS = 15  # SSE keep-alive so proxies don't drop an idle stream
FAIL_WINDOW_SECONDS, FAIL_LIMIT = 60, 10  # at most this many wrong codes per window, then 429 until it passes

log = logging.getLogger("upgradepilot")
app = FastAPI(title="UpgradePilot", docs_url=None, redoc_url=None, openapi_url=None)
RUNS: dict = {}
_lock = threading.Lock()  # held for the duration of a live run
_gate = threading.Lock()  # makes "check daily cap + take run lock + count" one step
_fails: list = []  # monotonic times of recent wrong codes
_day = {"date": time.strftime("%Y-%m-%d"), "count": 0}


class StartRequest(BaseModel):
    access_code: str = ""


def _preflight() -> str | None:
    """Why a live run cannot start on this server, or None."""
    missing = [k for k in ("NEBIUS_API_KEY", "TAVILY_API_KEY") if not os.environ.get(k, "").strip()]
    if missing:
        return f"live runs are not configured on this server (missing {', '.join(missing)})"
    if os.geteuid() == 0 and sandbox_uid() is None:  # root without the uid drop would expose the server's keys to model-run code
        return "live runs are disabled: running as root without UP_SANDBOX_UID"
    for name in (".venv-old", ".venv-new"):
        if not (DEMO / name / "bin" / "python").exists():
            return f"live runs are not available: demo/{name} is missing (run scripts/build_envs.sh)"
    return None


def _spawn(fn) -> None:
    threading.Thread(target=fn, daemon=True).start()


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.update({
        "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                   "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})
    return resp


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/favicon.svg")
def favicon():
    return FileResponse(WEB / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/config")
def config():
    return {"live_enabled": bool(os.environ.get("UP_ACCESS_CODE")),
            "live_ready": _preflight() is None,
            "has_recording": RECORDING.exists(),
            "fixture": {"package": "pydantic", "from": "1.10.27", "to": "2.14.2"}}


@app.get("/api/recording")
def recording():
    if not RECORDING.exists():
        raise HTTPException(404, "no recording bundled")
    return FileResponse(RECORDING, media_type="application/json")


@app.post("/api/run")
def start(req: StartRequest):
    if len(req.access_code) > 256:
        raise HTTPException(422, "access code too long")
    expected = os.environ.get("UP_ACCESS_CODE", "")
    now = time.monotonic()
    with _gate:
        _fails[:] = [t for t in _fails if now - t < FAIL_WINDOW_SECONDS]
        if len(_fails) >= FAIL_LIMIT:
            raise HTTPException(429, "too many wrong access codes; wait a minute")
    if not expected or not secrets.compare_digest(req.access_code.encode("utf-8", "surrogatepass"),
                                                    expected.encode("utf-8", "surrogatepass")):
        with _gate:
            _fails.append(now)
        raise HTTPException(403, "live runs need the access code (see the README); the recorded run needs none")
    problem = _preflight()
    if problem:
        raise HTTPException(503, problem)
    with _gate:
        today = time.strftime("%Y-%m-%d")
        if _day["date"] != today:
            _day.update(date=today, count=0)
        if _day["count"] >= MAX_LIVE_RUNS_PER_DAY:
            raise HTTPException(429, "daily live-run limit reached; use the recorded run")
        if not _lock.acquire(blocking=False):
            raise HTTPException(409, "a live run is already in progress")
        _day["count"] += 1
    run_id = uuid.uuid4().hex[:16]
    run = RUNS[run_id] = {"events": [], "done": False}

    def work():
        try:
            run_preset(run["events"].append)
        except Exception as e:  # surface infrastructure errors; never present them as a pass
            log.exception("run %s failed", run_id)
            run["events"].append({"t": 0, "kind": "error", "data": {
                "message": f"the run failed with an internal error ({type(e).__name__}); details are in the server log"}})
        finally:
            run["done"] = True
            _lock.release()
            evict = threading.Timer(RUN_TTL_SECONDS, RUNS.pop, (run_id, None))
            evict.daemon = True
            evict.start()

    try:
        _spawn(work)
    except Exception:  # the worker never started, so nothing will release the lock or count the run
        RUNS.pop(run_id, None)
        with _gate:
            _day["count"] -= 1
        _lock.release()
        raise
    return {"run_id": run_id}


@app.get("/api/run/{run_id}/events")
async def events(run_id: str):
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")

    async def stream():
        sent, last = 0, time.monotonic()
        while True:
            while sent < len(run["events"]):
                yield f"data: {json.dumps(run['events'][sent], default=str)}\n\n"
                sent += 1
                last = time.monotonic()
            if run["done"] and sent >= len(run["events"]):
                yield "event: end\ndata: {}\n\n"
                return
            if time.monotonic() - last >= PING_SECONDS:
                yield ": ping\n\n"
                last = time.monotonic()
            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.exception_handler(Exception)
async def unhandled(_, exc):
    return JSONResponse({"detail": f"{type(exc).__name__}"}, status_code=500)
