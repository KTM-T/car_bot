import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (HTMLResponse, PlainTextResponse,
                               StreamingResponse)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai import stream_diagnosis

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]
SESSION_TTL: int = int(os.environ.get("SESSION_TTL_MINUTES", "30")) * 60
MAX_SESSIONS: int = int(os.environ.get("MAX_SESSIONS", "500"))
HISTORY_LIMIT: int = 20  # max turns kept per session (older dropped)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("cardiag")

# ── Session store ─────────────────────────────────────────────────────────────


class Session:
    def __init__(self):
        self.id: str = str(uuid.uuid4())
        self.history: list[dict] = []  # [{role, content}, ...]
        self.created_at: float = time.time()
        self.last_active: float = time.time()

    def touch(self):
        self.last_active = time.time()

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        # Keep only the last N turns to avoid bloating context
        if len(self.history) > HISTORY_LIMIT * 2:
            self.history = self.history[-(HISTORY_LIMIT * 2) :]

    def expired(self) -> bool:
        return (time.time() - self.last_active) > SESSION_TTL


_sessions: dict[str, Session] = {}


def get_session(sid: str) -> Session:
    s = _sessions.get(sid)
    if not s or s.expired():
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    s.touch()
    return s


def new_session() -> Session:
    if len(_sessions) >= MAX_SESSIONS:
        raise HTTPException(status_code=503, detail="Server at capacity.")
    s = Session()
    _sessions[s.id] = s
    log.info("New session %s | active=%d", s.id, len(_sessions))
    return s


# ── Background cleanup ────────────────────────────────────────────────────────


async def _cleanup():
    while True:
        await asyncio.sleep(120)
        expired = [sid for sid, s in _sessions.items() if s.expired()]
        for sid in expired:
            del _sessions[sid]
        if expired:
            log.info(
                "Cleaned %d expired sessions | active=%d", len(expired), len(_sessions)
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup())
    yield
    task.cancel()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="CarDiag API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class SessionCreated(BaseModel):
    session_id: str


# ── REST API endpoints ────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(_sessions)}


@app.post("/session", response_model=SessionCreated, status_code=201)
async def create_session():
    s = new_session()
    return {"session_id": s.id}


@app.post("/session/{session_id}/chat")
async def chat(session_id: str, body: ChatRequest):
    """
    Streaming chat endpoint. Returns text/event-stream (SSE).
    The full assistant reply is also stored in session history.

    Example:
        curl -N -X POST http://localhost:8000/session/<id>/chat \\
             -H "Content-Type: application/json" \\
             -d '{"message": "my car knocks when hot"}'
    """
    s = get_session(session_id)
    user_msg = body.message

    # Snapshot history before this turn (prior context)
    prior = list(s.history)

    async def generate():
        collected = []
        try:
            # Run the blocking Groq generator in a thread
            loop = asyncio.get_event_loop()
            gen = await loop.run_in_executor(
                None, lambda: list(stream_diagnosis(prior, user_msg, GROQ_API_KEY))
            )
            for chunk in gen:
                collected.append(chunk)
                yield f"data: {chunk}\n\n"
        except Exception as e:
            log.error("Groq error: %s", e)
            yield f"data: [ERROR] {e}\n\n"
        finally:
            full_reply = "".join(collected)
            s.add_turn("user", user_msg)
            s.add_turn("assistant", full_reply)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.delete("/session/{session_id}", status_code=204)
async def end_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    del _sessions[session_id]
    log.info("Session %s deleted", session_id)


# ── curl-friendly plaintext CLI over HTTP ─────────────────────────────────────

WELCOME = """\
══════════════════════════════════════════
  🚗  CarDiag — AI Car Diagnostic Bot
══════════════════════════════════════════
Describe your car problem in plain English.

  curl -b c.txt -X POST http://HOST/cli \\
       -d "my engine knocks when hot"

Commands:  history | reset | quit
══════════════════════════════════════════
"""


@app.get("/cli", response_class=PlainTextResponse)
async def cli_start(response: PlainTextResponse):
    """Start a CLI session. Saves session cookie."""
    s = new_session()
    res = PlainTextResponse(WELCOME)
    res.set_cookie("sid", s.id, max_age=SESSION_TTL)
    return res


@app.post("/cli", response_class=PlainTextResponse)
async def cli_chat(request: Request):
    """
    Send a message, get a plaintext reply. Session via cookie.

    Usage:
        # Start session
        curl -c c.txt http://HOST/cli

        # Send messages
        curl -b c.txt -X POST http://HOST/cli -d "engine knocks when hot"
        curl -b c.txt -X POST http://HOST/cli -d "yes it knocks faster as RPM rises"
        curl -b c.txt -X POST http://HOST/cli -d "history"
        curl -b c.txt -X POST http://HOST/cli -d "reset"
    """
    sid = request.cookies.get("sid")
    if not sid or sid not in _sessions or _sessions[sid].expired():
        s = new_session()
        sid = s.id
    else:
        s = _sessions[sid]
        s.touch()

    body = await request.body()
    message = body.decode().strip()

    if not message:
        res = PlainTextResponse(WELCOME)
        res.set_cookie("sid", sid, max_age=SESSION_TTL)
        return res

    cmd = message.lower()

    if cmd == "quit":
        _sessions.pop(sid, None)
        res = PlainTextResponse(
            "Session ended. Run `curl -c c.txt http://HOST/cli` to start a new one.\n"
        )
        res.delete_cookie("sid")
        return res

    if cmd == "reset":
        _sessions.pop(sid, None)
        s = new_session()
        sid = s.id
        res = PlainTextResponse("Session reset.\n\n" + WELCOME)
        res.set_cookie("sid", sid, max_age=SESSION_TTL)
        return res

    if cmd == "history":
        if not s.history:
            text = "No history yet.\n"
        else:
            lines = []
            for turn in s.history:
                prefix = "You" if turn["role"] == "user" else "Bot"
                lines.append(f"[{prefix}] {turn['content']}\n")
            text = "\n".join(lines)
        res = PlainTextResponse(text + "\n> ")
        res.set_cookie("sid", sid, max_age=SESSION_TTL)
        return res

    # Real diagnosis — call Groq synchronously (CLI endpoint, not streaming)
    prior = list(s.history)
    try:
        chunks = list(stream_diagnosis(prior, message, GROQ_API_KEY))
        reply = "".join(chunks)
    except Exception as e:
        reply = f"[ERROR] {e}"

    s.add_turn("user", message)
    s.add_turn("assistant", reply)

    output = f"\n{'─'*50}\n{reply}\n{'─'*50}\n\n> "
    res = PlainTextResponse(output)
    res.set_cookie("sid", sid, max_age=SESSION_TTL)
    return res


# ── Static frontend (optional) ────────────────────────────────────────────────

import pathlib

static_dir = pathlib.Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def frontend():
        index = static_dir / "index.html"
        return (
            index.read_text()
            if index.exists()
            else HTMLResponse("<h1>CarDiag API</h1><p>See /docs</p>")
        )


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("\n══════════════════════════════════════════")
    print("  🚗  CarDiag API")
    print("══════════════════════════════════════════")
    print("  Web UI:   http://localhost:8000")
    print("  API docs: http://localhost:8000/docs")
    print("  CLI:      curl -c c.txt http://localhost:8000/cli")
    print("══════════════════════════════════════════\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
