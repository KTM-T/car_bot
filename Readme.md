# CarDiag — AI Car Diagnostic Bot

Groq-powered car diagnostics over a REST API and curl-friendly CLI.

## Stack

- **AI**: Groq (`llama-3.3-70b-versatile`), streaming
- **API**: FastAPI + uvicorn
- **Sessions**: in-memory, cookie-based for CLI

---

## Run locally

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
python main.py
```

---

## Deploy to Railway (free tier)

1. Push this folder to a GitHub repo
2. Go to https://railway.app → New Project → Deploy from GitHub repo
3. Select the repo
4. Add environment variable: `GROQ_API_KEY=gsk_...`
5. Railway auto-detects `railway.toml` and deploys

Your URL will be: `https://cardiag-production-XXXX.up.railway.app`

---

## Usage

### REST API (for websites / apps)

```bash
# Create a session
SESSION=$(curl -s -X POST https://HOST/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Chat — streaming SSE response
curl -N -X POST https://HOST/session/$SESSION/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "my engine knocks when hot"}'

# Follow-up
curl -N -X POST https://HOST/session/$SESSION/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "yes it knocks faster as RPM rises"}'

# End session
curl -X DELETE https://HOST/session/$SESSION
```

### CLI (curl from terminal anywhere)

```bash
# Start session (saves cookie to c.txt)
curl -c c.txt https://HOST/cli

# Send messages (reuses cookie)
curl -b c.txt -X POST https://HOST/cli -d "engine knocks when hot"
curl -b c.txt -X POST https://HOST/cli -d "yes, faster at higher RPM"
curl -b c.txt -X POST https://HOST/cli -d "battery drains overnight"

# Utilities
curl -b c.txt -X POST https://HOST/cli -d "history"
curl -b c.txt -X POST https://HOST/cli -d "reset"
curl -b c.txt -X POST https://HOST/cli -d "quit"
```

### Health check

```bash
curl https://HOST/health
```

---

## API docs

FastAPI auto-generates interactive docs at:

```
https://HOST/docs
```

---

## Environment variables

| Variable              | Required | Default | Description             |
| --------------------- | -------- | ------- | ----------------------- |
| `GROQ_API_KEY`        | Yes      | —       | Groq API key            |
| `SESSION_TTL_MINUTES` | No       | `30`    | Session expiry          |
| `MAX_SESSIONS`        | No       | `500`   | Max concurrent sessions |
