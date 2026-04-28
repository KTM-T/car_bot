import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Path, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Import your diagnostic engine
from diagnostic_engine import MENU_TEXT, DiagSession

# Configuration
SESSION_TTL_MINUTES: int = 30
CLEANUP_INTERVAL_SECONDS: int = 120
MAX_SESSIONS: int = 1000

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("carbot")


# Session store
class SessionRecord:
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.diag: DiagSession = DiagSession()
        self.created_at: float = time.time()
        self.last_active: float = time.time()

    def touch(self) -> None:
        self.last_active = time.time()

    def is_expired(self, ttl_seconds: int) -> bool:
        return (time.time() - self.last_active) > ttl_seconds


_sessions: dict[str, SessionRecord] = {}


# Pydantic schemas
class SessionCreatedResponse(BaseModel):
    session_id: str
    welcome: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    session_id: str
    message: str
    follow_up: Optional[str] = None
    done: bool = False


class StatusResponse(BaseModel):
    status: str
    active_sessions: int


# Background cleanup
async def _cleanup_expired_sessions() -> None:
    ttl_seconds = SESSION_TTL_MINUTES * 60
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        expired = [sid for sid, rec in _sessions.items() if rec.is_expired(ttl_seconds)]
        for sid in expired:
            del _sessions[sid]
        if expired:
            log.info(
                "Cleaned up %d expired session(s). Active: %d",
                len(expired),
                len(_sessions),
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Car Diagnostic Bot API starting up.")
    cleanup_task = asyncio.create_task(_cleanup_expired_sessions())
    yield
    cleanup_task.cancel()
    log.info("Car Diagnostic Bot API shut down.")


# Create FastAPI app
app = FastAPI(title="Car Diagnostic Bot API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper
def _get_session(session_id: str) -> SessionRecord:
    rec = _sessions.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Session not found or expired.")
    rec.touch()
    return rec


# ============ API Endpoints ============


@app.get("/health", response_model=StatusResponse)
async def health_check():
    return StatusResponse(status="ok", active_sessions=len(_sessions))


@app.post("/session", response_model=SessionCreatedResponse, status_code=201)
async def create_session():
    if len(_sessions) >= MAX_SESSIONS:
        raise HTTPException(status_code=503, detail="Server at capacity")
    session_id = str(uuid.uuid4())
    _sessions[session_id] = SessionRecord(session_id)
    log.info("New session created: %s | Active: %d", session_id, len(_sessions))
    return SessionCreatedResponse(session_id=session_id, welcome=MENU_TEXT)


@app.post("/session/{session_id}/chat", response_model=ChatResponse)
async def chat(session_id: str, body: ChatRequest):
    rec = _get_session(session_id)
    result = rec.diag.respond(body.message)
    return ChatResponse(
        session_id=session_id,
        message=result["message"],
        follow_up=result.get("follow_up"),
        done=result.get("done", False),
    )


# ============ Enhanced Web Terminal Support ============
@app.post("/chat", response_class=PlainTextResponse)
async def chat_post(request: Request, response: Response):
    """
    Handle POST requests from web terminal for compatibility.
    This works alongside the GET endpoint.
    """
    try:
        body = await request.json()
        command = body.get("message", "")
    except:
        command = ""

    if not command:
        # New session
        session_id = str(uuid.uuid4())
        _sessions[session_id] = SessionRecord(session_id)

        welcome_text = f"""
{'='*60}
🚗 CAR DIAGNOSTIC BOT - Interactive CLI
{'='*60}

Session ID: {session_id}

Commands:
  • Describe symptoms: misfire, overheating, shake, no start, etc.
  • Answer questions: yes, no, while driving, at idle
  • Type 'help' to see this menu
  • Type 'history' to see conversation
  • Type 'reset' to start over
  • Type 'quit' to end session

{'='*60}
{MENU_TEXT}
{'='*60}

> 
"""
        res = PlainTextResponse(welcome_text)
        res.set_cookie(key="session_id", value=session_id, max_age=1800)
        return res

    # Process command
    session_id = request.cookies.get("session_id")

    if not session_id or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = SessionRecord(session_id)

    rec = _sessions[session_id]
    cmd_lower = command.lower().strip()

    # Handle special commands
    if cmd_lower == "help":
        help_text = f"""
{'='*60}
📖 HELP - Available Commands
{'='*60}

DIAGNOSIS COMMANDS:
  • Describe your car problem:
    - misfire, rough idle, stalling
    - overheating, hot temperature
    - shaking, vibration
    - no start, won't crank
    - strange noise, squeal, grind
    - smoke from exhaust
  
  • Answer diagnosis questions with:
    - yes / no
    - while driving / at idle / during braking
    - when cold / when hot
  
SESSION COMMANDS:
  • history     - Show conversation history
  • reset       - Start a new diagnosis session
  • quit        - End this session
  • help        - Show this menu

{'='*60}
> 
"""
        res = PlainTextResponse(help_text)
        res.set_cookie(key="session_id", value=session_id, max_age=1800)
        return res

    if cmd_lower == "history":
        if not rec.diag.history:
            return PlainTextResponse("📭 No conversation history yet.\n\n> ")

        history_text = "\n📜 CONVERSATION HISTORY:\n" + "=" * 40 + "\n"
        for i, turn in enumerate(rec.diag.history, 1):
            history_text += f"{i}. 👤 You: {turn['user']}\n"
            history_text += f"   🤖 Bot: {turn['bot'][:150]}{'...' if len(turn['bot']) > 150 else ''}\n\n"
        history_text += "=" * 40 + "\n> "
        res = PlainTextResponse(history_text)
        res.set_cookie(key="session_id", value=session_id, max_age=1800)
        return res

    if cmd_lower == "reset":
        _sessions[session_id] = SessionRecord(session_id)
        res = PlainTextResponse(
            "✅ Session reset! Starting fresh diagnosis.\n\n" + MENU_TEXT + "\n\n> "
        )
        res.set_cookie(key="session_id", value=session_id, max_age=1800)
        return res

    if cmd_lower == "quit":
        del _sessions[session_id]
        res = PlainTextResponse(
            "👋 Session ended. Goodbye!\n\nStart a new session with: curl -c cookies.txt http://localhost:8000/chat"
        )
        res.delete_cookie("session_id")
        return res

    # Process diagnostic message
    result = rec.diag.respond(command)

    output = f"""
{'-'*50}
🤖 {result['message']}
{'-'*50}
"""
    if result.get("follow_up"):
        output += f"\n💡 {result['follow_up']}\n"

    if result.get("done"):
        output += (
            f"\n✅ Diagnosis complete! Type 'reset' to diagnose another problem.\n"
        )

    output += f"\n> "

    res = PlainTextResponse(output)
    res.set_cookie(key="session_id", value=session_id, max_age=1800)
    return res


@app.get("/chat", response_class=PlainTextResponse)
async def chat_get(request: Request, response: Response):
    """GET endpoint for CLI with curl - maintains compatibility"""
    session_id = request.cookies.get("session_id")

    if not session_id or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = SessionRecord(session_id)

    welcome_text = f"""
{'='*60}
🚗 CAR DIAGNOSTIC BOT - Interactive CLI
{'='*60}

Session ID: {session_id}

Commands:
  • Describe symptoms: misfire, overheating, shake, no start, etc.
  • Answer questions: yes, no, while driving, at idle
  • Type 'help' to see this menu
  • Type 'history' to see conversation
  • Type 'reset' to start over
  • Type 'quit' to end session

{'='*60}
{MENU_TEXT}
{'='*60}

> 
"""
    res = PlainTextResponse(welcome_text)
    res.set_cookie(key="session_id", value=session_id, max_age=1800)
    return res


@app.get("/chat/{command:path}", response_class=PlainTextResponse)
async def chat_command(request: Request, command: str, response: Response):
    """GET endpoint for commands - maintains cookie session"""
    session_id = request.cookies.get("session_id")

    if not session_id or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = SessionRecord(session_id)

    rec = _sessions[session_id]
    cmd_lower = command.lower().strip()

    # Handle special commands
    if cmd_lower == "help":
        help_text = f"""
{'='*60}
📖 HELP - Available Commands
{'='*60}

DIAGNOSIS COMMANDS:
  • Describe your car problem:
    - misfire, rough idle, stalling
    - overheating, hot temperature
    - shaking, vibration
    - no start, won't crank
    - strange noise, squeal, grind
    - smoke from exhaust
  
  • Answer diagnosis questions with:
    - yes / no
    - while driving / at idle / during braking
    - when cold / when hot
  
SESSION COMMANDS:
  • history     - Show conversation history
  • reset       - Start a new diagnosis session
  • quit        - End this session
  • help        - Show this menu

{'='*60}
> 
"""
        res = PlainTextResponse(help_text)
        res.set_cookie(key="session_id", value=session_id, max_age=1800)
        return res

    if cmd_lower == "history":
        if not rec.diag.history:
            return PlainTextResponse("📭 No conversation history yet.\n\n> ")

        history_text = "\n📜 CONVERSATION HISTORY:\n" + "=" * 40 + "\n"
        for i, turn in enumerate(rec.diag.history, 1):
            history_text += f"{i}. 👤 You: {turn['user']}\n"
            history_text += f"   🤖 Bot: {turn['bot'][:150]}{'...' if len(turn['bot']) > 150 else ''}\n\n"
        history_text += "=" * 40 + "\n> "
        res = PlainTextResponse(history_text)
        res.set_cookie(key="session_id", value=session_id, max_age=1800)
        return res

    if cmd_lower == "reset":
        _sessions[session_id] = SessionRecord(session_id)
        res = PlainTextResponse(
            "✅ Session reset! Starting fresh diagnosis.\n\n" + MENU_TEXT + "\n\n> "
        )
        res.set_cookie(key="session_id", value=session_id, max_age=1800)
        return res

    if cmd_lower == "quit":
        del _sessions[session_id]
        res = PlainTextResponse(
            "👋 Session ended. Goodbye!\n\nStart a new session with: curl -c cookies.txt http://localhost:8000/chat"
        )
        res.delete_cookie("session_id")
        return res

    # Process diagnostic message
    result = rec.diag.respond(command)

    output = f"""
{'-'*50}
🤖 {result['message']}
{'-'*50}
"""
    if result.get("follow_up"):
        output += f"\n💡 {result['follow_up']}\n"

    if result.get("done"):
        output += (
            f"\n✅ Diagnosis complete! Type 'reset' to diagnose another problem.\n"
        )

    output += f"\n> "

    res = PlainTextResponse(output)
    res.set_cookie(key="session_id", value=session_id, max_age=1800)
    return res


@app.delete("/session/{session_id}", status_code=204)
async def end_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del _sessions[session_id]
    log.info("Session %s ended", session_id)


# Serve frontend files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")


# ============ BEST SOLUTION: Session-based Interactive CLI over HTTP ============
# Uses cookies for persistent sessions - works beautifully with curl!


@app.get("/chat", response_class=PlainTextResponse)
async def chat_start(request: Request, response: Response):
    """
    Start a new interactive CLI session.

    Usage:
        curl -c cookies.txt http://localhost:8000/chat
    """
    session_id = str(uuid.uuid4())
    _sessions[session_id] = SessionRecord(session_id)

    welcome_text = f"""
{'='*60}
🚗 CAR DIAGNOSTIC BOT - Interactive CLI
{'='*60}

Session ID: {session_id}

Commands:
  • Describe symptoms: misfire, overheating, shake, no start, etc.
  • Answer questions: yes, no, while driving, at idle
  • Type 'help' to see this menu
  • Type 'history' to see conversation
  • Type 'reset' to start over
  • Type 'quit' to end session

{'='*60}
{MENU_TEXT}
{'='*60}

> 
"""
    response = PlainTextResponse(welcome_text)
    response.set_cookie(key="session_id", value=session_id, max_age=1800)  # 30 minutes
    return response


@app.get("/chat/{command:path}", response_class=PlainTextResponse)
async def chat_command(request: Request, command: str, response: Response):
    """
    Send a command to the interactive CLI session.
    Session is maintained via cookie.

    Usage:
        curl -b cookies.txt "http://localhost:8000/chat/misfire"
        curl -b cookies.txt "http://localhost:8000/chat/yes"
        curl -b cookies.txt "http://localhost:8000/chat/while%20driving"
        curl -b cookies.txt "http://localhost:8000/chat/history"
    """

    # Get session ID from cookie or query param
    session_id = request.cookies.get("session_id") or request.query_params.get(
        "session_id"
    )

    # Handle new session creation if no session_id
    if not session_id or session_id not in _sessions:
        # Create new session automatically
        session_id = str(uuid.uuid4())
        _sessions[session_id] = SessionRecord(session_id)
        log.info("Auto-created session: %s", session_id)

    rec = _sessions[session_id]

    # Handle special commands
    cmd_lower = command.lower().strip()

    if cmd_lower == "help":
        help_text = f"""
{'='*60}
📖 HELP - Available Commands
{'='*60}

DIAGNOSIS COMMANDS:
  • Describe your car problem:
    - misfire, rough idle, stalling
    - overheating, hot temperature
    - shaking, vibration
    - no start, won't crank
    - strange noise, squeal, grind
    - smoke from exhaust
  
  • Answer diagnosis questions with:
    - yes / no
    - while driving / at idle / during braking
    - when cold / when hot
  
SESSION COMMANDS:
  • history     - Show conversation history
  • reset       - Start a new diagnosis session
  • quit        - End this session
  • help        - Show this menu

{'='*60}
> 
"""
        return PlainTextResponse(help_text)

    if cmd_lower == "history":
        if not rec.diag.history:
            return PlainTextResponse("📭 No conversation history yet.\n\n> ")

        history_text = "\n📜 CONVERSATION HISTORY:\n" + "=" * 40 + "\n"
        for i, turn in enumerate(rec.diag.history, 1):
            history_text += f"{i}. 👤 You: {turn['user']}\n"
            history_text += f"   🤖 Bot: {turn['bot'][:150]}{'...' if len(turn['bot']) > 150 else ''}\n\n"
        history_text += "=" * 40 + "\n> "
        return PlainTextResponse(history_text)

    if cmd_lower == "reset":
        # Create new DiagSession but keep same session_id
        _sessions[session_id] = SessionRecord(session_id)
        return PlainTextResponse(
            "✅ Session reset! Starting fresh diagnosis.\n\n" + MENU_TEXT + "\n\n> "
        )

    if cmd_lower == "quit":
        del _sessions[session_id]
        response = PlainTextResponse(
            "👋 Session ended. Goodbye!\n\nStart a new session with: curl -c cookies.txt http://localhost:8000/chat"
        )
        response.delete_cookie("session_id")
        return response

    # Process diagnostic message
    result = rec.diag.respond(command)

    # Format response like a terminal
    output = f"""
{'-'*50}
🤖 {result['message']}
{'-'*50}
"""
    if result.get("follow_up"):
        output += f"\n💡 {result['follow_up']}\n"

    if result.get("done"):
        output += (
            f"\n✅ Diagnosis complete! Type 'reset' to diagnose another problem.\n"
        )

    output += f"\n> "

    # Update cookie to extend session
    response = PlainTextResponse(output)
    response.set_cookie(key="session_id", value=session_id, max_age=1800)
    return response


# ============ Web Terminal Interface ============
@app.get("/terminal", response_class=HTMLResponse)
async def web_terminal():
    """Web-based terminal interface that works with GET-based CLI"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Car Diagnostic Bot Terminal</title>

<style>
body {
    margin: 0;
    background: #111;
    color: #eee;
    font-family: monospace;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

header {
    padding: 12px;
    background: #000;
    border-bottom: 1px solid #333;
    color: #00ff88;
}

#terminal {
    flex: 1;
    overflow-y: auto;
    padding: 15px;
    white-space: pre-wrap;
    line-height: 1.5;
}

.line-user { color: #ffaa66; }
.line-bot { color: #66ccff; }
.line-system { color: #88ff88; }
.line-error { color: #ff6666; }

#inputBar {
    display: flex;
    padding: 10px;
    background: #000;
    border-top: 1px solid #333;
}

#prompt {
    color: #00ff88;
    margin-right: 10px;
}

#cmd {
    flex: 1;
    background: transparent;
    border: none;
    color: white;
    font-family: monospace;
    font-size: 16px;
    outline: none;
}
</style>
</head>

<body>

<header>
🚗 Car Diagnostic Bot Web Terminal
</header>

<div id="terminal"></div>

<div id="inputBar">
<div id="prompt">></div>
<input id="cmd" autocomplete="off" autofocus>
</div>

<script>
const term = document.getElementById("terminal");
const cmd = document.getElementById("cmd");

let history = [];
let histIndex = 0;
let sessionInitialized = false;

function print(text, cls="line-bot") {
    const div = document.createElement("div");
    div.className = cls;
    div.textContent = text;
    term.appendChild(div);
    term.scrollTop = term.scrollHeight;
}

function stripAnsi(text) {
    // Remove any ANSI color codes if present
    return text.replace(/\\x1b\\[[0-9;]*[a-zA-Z]/g, '');
}

async function startSession() {
    try {
        print("Initializing session...", "line-system");
        const res = await fetch("/chat");
        const txt = await res.text();
        print(stripAnsi(txt), "line-system");
        sessionInitialized = true;
    } catch(err) {
        print("Connection failed: " + err.message, "line-error");
    }
}

async function sendCommand(message) {
    if (!message.trim()) return;

    print("> " + message, "line-user");

    try {
        // Use GET request with the command in the URL path
        const encodedCmd = encodeURIComponent(message);
        const res = await fetch(`/chat/${encodedCmd}`);
        
        if (!res.ok) {
            print(`Error: ${res.status} ${res.statusText}`, "line-error");
            return;
        }
        
        const txt = await res.text();
        print(stripAnsi(txt), "line-bot");

        if (message.toLowerCase() === "quit") {
            cmd.disabled = true;
            print("Session ended. Refresh to start a new session.", "line-system");
        }

    } catch(err) {
        print("Server error: " + err.message, "line-error");
    }
}

cmd.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        const message = cmd.value;
        if (!message.trim()) return;

        history.push(message);
        histIndex = history.length;

        sendCommand(message);
        cmd.value = "";
    }

    if (e.key === "ArrowUp") {
        if (histIndex > 0) {
            histIndex--;
            cmd.value = history[histIndex];
        }
        e.preventDefault();
    }

    if (e.key === "ArrowDown") {
        if (histIndex < history.length - 1) {
            histIndex++;
            cmd.value = history[histIndex];
        } else {
            histIndex = history.length;
            cmd.value = "";
        }
        e.preventDefault();
    }
});

// Start the session when page loads
startSession();
</script>

</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🚗 Car Diagnostic Bot - Full Stack with Interactive CLI")
    print("=" * 60)
    print(f"\n📍 Web Interface:     http://localhost:8000")
    print(f"📍 Web Terminal:      http://localhost:8000/terminal")
    print(f"📡 API Documentation: http://localhost:8000/docs")
    print(f"\n💡 Interactive CLI over HTTP:")
    print(f"   curl -c cookies.txt http://localhost:8000/chat")
    print(f"   curl -b cookies.txt 'http://localhost:8000/chat/misfire'")
    print(f"   curl -b cookies.txt 'http://localhost:8000/chat/yes'")
    print(f"   curl -b cookies.txt 'http://localhost:8000/chat/history'")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
