"""FastAPI backend: the briefing agent over HTTP, plus the built React app."""

import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

import db
import documents
from extract import extract_account
from graph import build_graph
from models import AccountData, Briefing
from nodes import MAX_ATTEMPTS, MODEL, PROMPTS_DIR
from portfolio import build_portfolio_graph
from validation import CHECKS

log = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

# ponytail: per-process, per-IP counter. Enough to stop one visitor draining the
# API key; swap for a shared store if this ever runs on more than one worker.
MAX_RUNS_PER_IP = 60
# Decks carry images we never read; the text inside is what costs anything.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_runs_by_ip: dict[str, int] = defaultdict(int)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    db.init_db()
    app.state.graph = build_graph()
    app.state.portfolio = build_portfolio_graph()
    yield


app = FastAPI(title="FieldAssist Pre-Call Briefing Agent", lifespan=lifespan)

# Only needed when the frontend is hosted separately from the API. A
# single-service deploy serves both from one origin and never triggers this.
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# A browser's Origin header carries scheme and host only — never a path, not
# even a bare slash. Trimming here means a URL copied out of a dashboard with a
# trailing slash still matches, instead of silently blocking every request.
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS + DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BriefingRequest(BaseModel):
    account_data: dict
    account_id: int | None = None
    input_source: str = "form"


class PortfolioRequest(BaseModel):
    manager_id: int


class ManagerRequest(BaseModel):
    name: str
    region: str | None = None


class ExtractRequest(BaseModel):
    notes: str


class AccountRequest(BaseModel):
    manager_id: int
    data: dict
    slug: str | None = None


def _slugify(name: str) -> str:
    """A filesystem- and URL-safe key for an account, e.g. 'Apex Logistics' -> 'apex_logistics'."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "account"


def _client_ip(request: Request) -> str:
    """The visitor's address, not the proxy's.

    Hosted behind a reverse proxy, `request.client.host` is the proxy for every
    visitor — which would put everyone in one shared quota bucket and 429 the
    whole app once any single person hit the cap.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_quota(request: Request) -> None:
    ip = _client_ip(request)
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


# Matched on class name rather than importing the OpenAI SDK's exception tree,
# which keeps this readable and survives the SDK reorganising itself.
FRIENDLY_ERRORS = {
    "AuthenticationError": "The server isn't configured with a valid API key.",
    "PermissionDeniedError": "The server's API key isn't allowed to use this model.",
    "RateLimitError": "The model is rate limited at the moment. Give it a few seconds.",
    "APITimeoutError": "The model took too long to answer. Worth trying again.",
    "APIConnectionError": "Couldn't reach the model service. It may be a passing outage.",
    "InternalServerError": "The model service returned an error. Worth trying again.",
    "BadRequestError": "The model rejected this request. The account data may be unusually large.",
}


def _friendly(exc: Exception) -> str:
    """A sentence a non-technical reader can act on. Never a traceback."""
    if isinstance(exc, ValueError):
        return str(exc)  # our own validation messages, written to be read
    return FRIENDLY_ERRORS.get(
        type(exc).__name__,
        "Something went wrong producing this. Nothing was saved — try again.",
    )


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
        yield _sse({"type": "error", "message": _friendly(e)})
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
            "evidence_gaps": state.get("evidence_gaps") or [],
            "provisional": state.get("provisional", False),
            "attempts": state.get("attempts", 1),
            "max_attempts": MAX_ATTEMPTS,
            "validation": {
                "passed": state.get("validation_passed", False),
                "errors": state.get("validation_errors") or [],
                "warnings": state.get("validation_warnings") or [],
            },
        }
    )


async def _portfolio_events(graph, manager: dict, accounts: list[dict]) -> AsyncIterator[str]:
    """Stream per-account progress during the fan-out, then the portfolio brief."""
    done = 0
    total = len(accounts)
    state: dict = {}

    try:
        async for event in graph.astream(
            {"manager_name": manager["name"], "accounts": accounts}, stream_mode="debug"
        ):
            node = event.get("payload", {}).get("name")
            if event["type"] != "task_result" or not node:
                continue

            result = event["payload"].get("result") or {}
            if node == "brief_one":
                done += 1
                briefed = (result.get("briefings") or [{}])[0]
                yield _sse(
                    {
                        "type": "account",
                        "done": done,
                        "total": total,
                        "account_name": briefed.get("account_name"),
                        "status": briefed.get("status"),
                    }
                )
            state.setdefault("briefings", []).extend(result.get("briefings") or [])
            state.update({k: v for k, v in result.items() if k != "briefings"})
    except Exception as e:
        log.exception("Portfolio run failed")
        yield _sse({"type": "error", "message": _friendly(e)})
        return

    brief = state.get("portfolio_brief")
    if brief is None:
        yield _sse({"type": "error", "message": "The model did not return a portfolio brief."})
        return

    yield _sse(
        {
            "type": "result",
            "manager": manager["name"],
            "portfolio_brief": brief.model_dump(mode="json"),
            "briefings": sorted(state["briefings"], key=lambda b: b["account_name"]),
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


@app.post("/api/portfolio/stream")
def stream_portfolio(payload: PortfolioRequest, request: Request) -> StreamingResponse:
    manager = next((m for m in db.list_managers() if m["id"] == payload.manager_id), None)
    if manager is None:
        raise HTTPException(404, f"No manager #{payload.manager_id}")

    accounts = db.list_accounts(payload.manager_id)
    if not accounts:
        raise HTTPException(400, f"{manager['name']} has no accounts yet.")

    # One briefing run per account, so the cap has to cover all of them.
    for _ in accounts:
        _check_quota(request)

    return StreamingResponse(
        _portfolio_events(request.app.state.portfolio, manager, accounts),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/extract")
def extract(payload: ExtractRequest, request: Request) -> dict:
    """Messy notes to a structured draft. The caller reviews it before briefing."""
    _check_quota(request)
    if not payload.notes.strip():
        raise HTTPException(400, "Paste some notes first.")
    try:
        return extract_account(payload.notes).model_dump()
    except Exception as e:
        log.exception("Extraction failed")
        raise HTTPException(502, _friendly(e)) from e


@app.post("/api/extract/file")
def extract_file(request: Request, file: UploadFile) -> dict:
    """A PDF, deck, spreadsheet or notes file to a structured draft."""
    _check_quota(request)

    blob = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(blob) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"That file is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB.")

    try:
        extracted = documents.to_text(file.filename or "", blob)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if not extracted.text.strip():
        raise HTTPException(
            400, "No readable text in that file. A scanned PDF would need OCR first."
        )

    try:
        account = extract_account(extracted.text).model_dump()
    except Exception as e:
        log.exception("Extraction from file failed")
        raise HTTPException(502, _friendly(e)) from e

    return {
        "account": account,
        "truncated": extracted.truncated,
        "total_chars": extracted.total_chars,
        "used_chars": len(extracted.text),
    }


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": MODEL}


@app.get("/api/managers")
def managers() -> list[dict]:
    return db.list_managers()


@app.post("/api/managers")
def create_manager(payload: ManagerRequest) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "A manager needs a name.")
    try:
        return db.create_manager(name, (payload.region or "").strip() or None)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/accounts")
def accounts(manager_id: int | None = None) -> list[dict]:
    return db.list_accounts(manager_id)


@app.post("/api/accounts")
def create_account(payload: AccountRequest) -> dict:
    """Create the account, or update it if the slug already exists."""
    account = _validated(payload.data)
    slug = payload.slug or _slugify(account.account_name)
    return db.get_account(db.save_account(payload.manager_id, slug, payload.data))


@app.get("/api/runs")
def runs(limit: int = 50) -> list[dict]:
    return db.list_runs(limit)


@app.get("/api/runs/{run_id}")
def run_detail(run_id: int) -> dict:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"No run #{run_id}")
    return run


PROMPTS = [
    ("Briefing", "briefing_prompt.md", "Turns one account's data into the six-field briefing."),
    ("Extraction", "extraction_prompt.md", "Turns messy notes or an uploaded file into a record."),
    ("Portfolio", "portfolio_prompt.md", "Compares a manager's whole book and ranks the week."),
]


@app.get("/api/prompts")
def prompts() -> list[dict]:
    """Every prompt the system sends, with the version hash stamped on each run."""
    out = []
    for name, filename, purpose in PROMPTS:
        text = (PROMPTS_DIR / filename).read_text()
        out.append(
            {
                "name": name,
                "file": filename,
                "purpose": purpose,
                "version": hashlib.sha256(text.encode()).hexdigest()[:12],
                "text": text,
            }
        )
    return out


@app.get("/api/internals")
def internals() -> dict:
    """Model settings, the checks that run, and the shape the model must return."""
    return {
        "model": MODEL,
        "temperature": 0,
        "max_attempts": MAX_ATTEMPTS,
        "checks": CHECKS,
        "briefing_schema": Briefing.model_json_schema(),
    }


@app.get("/api/pipeline")
async def pipeline(request: Request) -> dict:
    """The compiled graph, as data. Drawn by the client, so it can't drift from the code."""
    graph = request.app.state.graph.get_graph()
    return {
        "nodes": [n for n in graph.nodes if not n.startswith("__")],
        "edges": [
            {"source": e.source, "target": e.target, "conditional": bool(e.conditional)}
            for e in graph.edges
            if not e.source.startswith("__") and not e.target.startswith("__")
        ],
    }


# Mounted last so /api/* always wins. Absent when the frontend is deployed
# separately, in which case the root just says what this service is.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:

    @app.get("/")
    def root() -> dict:
        return {"service": "FieldAssist Pre-Call Briefing Agent API", "health": "/api/health"}
