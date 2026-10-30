"""FastAPI app: live runs (access-code gated, one at a time) and a recorded run for replay."""
import asyncio
import json
import os
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from .runner import ROOT, run_preset

load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

WEB = ROOT / "web"
RECORDING = ROOT / "recordings" / "pydantic_run.json"
MAX_LIVE_RUNS_PER_DAY = int(os.environ.get("UP_MAX_LIVE_RUNS", "15"))

app = FastAPI(title="UpgradePilot")
RUNS: dict = {}
_lock = threading.Lock()
_day = {"date": time.strftime("%Y-%m-%d"), "count": 0}


class StartRequest(BaseModel):
    access_code: str = ""


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/config")
def config():
    return {"live_enabled": bool(os.environ.get("UP_ACCESS_CODE")),
            "has_recording": RECORDING.exists(),
            "fixture": {"package": "pydantic", "from": "1.10.27", "to": "2.14.2"}}


@app.get("/api/recording")
def recording():
    if not RECORDING.exists():
        raise HTTPException(404, "no recording bundled")
    return FileResponse(RECORDING, media_type="application/json")


@app.post("/api/run")
def start(req: StartRequest):
    expected = os.environ.get("UP_ACCESS_CODE", "")
    if not expected or req.access_code != expected:
        raise HTTPException(403, "live runs need the access code (see the README); the recorded run needs none")
    today = time.strftime("%Y-%m-%d")
    if _day["date"] != today:
        _day.update(date=today, count=0)
    if _day["count"] >= MAX_LIVE_RUNS_PER_DAY:
        raise HTTPException(429, "daily live-run limit reached; use the recorded run")
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "a live run is already in progress")
    _day["count"] += 1
    run_id = uuid.uuid4().hex[:8]
    RUNS[run_id] = {"events": [], "done": False}

    def work():
        try:
            run_preset(RUNS[run_id]["events"].append)
        except Exception as e:  # surface infrastructure errors; never present them as a pass
            RUNS[run_id]["events"].append({"t": 0, "kind": "error", "data": {"message": f"{type(e).__name__}: {e}"}})
        finally:
            RUNS[run_id]["done"] = True
            _lock.release()

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/run/{run_id}/events")
async def events(run_id: str):
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")

    async def stream():
        sent = 0
        while True:
            while sent < len(run["events"]):
                yield f"data: {json.dumps(run['events'][sent], default=str)}\n\n"
                sent += 1
            if run["done"] and sent >= len(run["events"]):
                yield "event: end\ndata: {}\n\n"
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.exception_handler(Exception)
async def unhandled(_, exc):
    return JSONResponse({"detail": f"{type(exc).__name__}"}, status_code=500)
