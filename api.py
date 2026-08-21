"""FastAPI backend: the briefing agent over HTTP, plus the built React app."""

import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

import db
from graph import build_graph
from models import AccountData
from nodes import BRIEFING_PROMPT, MAX_ATTEMPTS, MODEL, prompt_version

log = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

# ponytail: per-process, per-IP counter. Enough to stop one visitor draining the
# API key; swap for a shared store if this ever runs on more than one worker.
MAX_RUNS_PER_IP = 40
_runs_by_ip: dict[str, int] = defaultdict(int)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    db.init_db()
    app.state.graph = build_graph()
    yield


app = FastAPI(title="FieldAssist Pre-Call Briefing Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class BriefingRequest(BaseModel):
    account_data: dict
    account_id: int | None = None
    input_source: str = "form"


class AccountRequest(BaseModel):
    manager_id: int
    slug: str
    data: dict


def _check_quota(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if _runs_by_ip[ip] >= MAX_RUNS_PER_IP:
        raise HTTPException(429, "Run limit reached for this session.")
    _runs_by_ip[ip] += 1


def _validated(account_data: dict) -> AccountData:
    """Reject unusable input at the boundary so the client gets a 400, not a stream error."""
    try:
        return AccountData.model_validate(account_data)
    except ValidationError as e:
        raise HTTPException(400, _readable(e)) from e


def _readable(error: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors())


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _detail(node: str, result: dict, state: dict) -> tuple[str, str]:
    """Turn a node's returned state into (status, human-readable line)."""
    if node == "load_data":
        missing = len(result.get("missing_fields") or [])
        total = len(AccountData.model_fields)
        return "ok", f"validated {total - missing} of {total} fields"

    if node == "generate_briefing":
        attempt = result.get("attempts", 1)
        if attempt == 1:
            return "ok", f"{MODEL} returned a briefing"
        errors = len(state.get("validation_errors") or [])
        return "ok", f"regenerated with {errors} correction{'s' if errors != 1 else ''}"

    if node == "validate_output":
        if result.get("validation_passed"):
            return "ok", "all citations grounded in the source data"
        errors = result.get("validation_errors") or []
        return "failed", errors[0] if errors else "validation failed"

    if node == "persist_run":
        run_id = result.get("run_id")
        return "ok", f"run #{run_id} saved" if run_id else "not recorded"

    return "ok", "briefing ready"


async def _briefing_events(graph, payload: BriefingRequest) -> AsyncIterator[str]:
    """Stream one node event per pipeline step, then the finished briefing."""
    state: dict = {}
    initial = {
        "account_data": payload.account_data,
        "account_id": payload.account_id,
        "input_source": payload.input_source,
    }

    try:
        async for event in graph.astream(initial, stream_mode="debug"):
            node = event.get("payload", {}).get("name")
            if not node or node.startswith("__"):
                continue

            if event["type"] == "task":
                yield _sse({"type": "node", "node": node, "status": "running"})
            elif event["type"] == "task_result":
                result = event["payload"].get("result") or {}
                status, detail = _detail(node, result, state)
                state.update(result)
                yield _sse({"type": "node", "node": node, "status": status, "detail": detail})
    except Exception as e:
        log.exception("Briefing run failed")
        yield _sse({"type": "error", "message": str(e)})
        return

    briefing = state.get("briefing")
    if briefing is None:
        yield _sse({"type": "error", "message": "The model did not return a usable briefing."})
        return

    yield _sse(
        {
            "type": "result",
            "run_id": state.get("run_id"),
            "briefing": briefing.model_dump(mode="json"),
            "markdown": state.get("markdown", ""),
            "generated_at": state.get("generated_at"),
            "missing_fields": state.get("missing_fields") or [],
            "attempts": state.get("attempts", 1),
            "max_attempts": MAX_ATTEMPTS,
            "validation": {
                "passed": state.get("validation_passed", False),
                "errors": state.get("validation_errors") or [],
                "warnings": state.get("validation_warnings") or [],
            },
        }
    )


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Stops nginx-style proxies buffering the stream into one lump at the end.
    "X-Accel-Buffering": "no",
}


@app.post("/api/briefings/stream")
async def stream_briefing(payload: BriefingRequest, request: Request) -> StreamingResponse:
    _check_quota(request)
    _validated(payload.account_data)
    return StreamingResponse(
        _briefing_events(request.app.state.graph, payload),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": MODEL}


@app.get("/api/managers")
async def managers() -> list[dict]:
    return db.list_managers()


@app.get("/api/accounts")
async def accounts(manager_id: int | None = None) -> list[dict]:
    return db.list_accounts(manager_id)


@app.post("/api/accounts")
async def create_account(payload: AccountRequest) -> dict:
    _validated(payload.data)
    account_id = db.save_account(payload.manager_id, payload.slug, payload.data)
    return db.get_account(account_id)


@app.get("/api/runs")
async def runs(limit: int = 50) -> list[dict]:
    return db.list_runs(limit)


@app.get("/api/runs/{run_id}")
async def run_detail(run_id: int) -> dict:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"No run #{run_id}")
    return run


@app.get("/api/prompt")
async def prompt() -> dict:
    return {"version": prompt_version(), "text": BRIEFING_PROMPT.read_text()}


@app.get("/api/pipeline")
async def pipeline(request: Request) -> dict:
    graph = request.app.state.graph.get_graph()
    return {"mermaid": graph.draw_mermaid()}


# Mounted last so /api/* always wins. Absent until the frontend is built.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
