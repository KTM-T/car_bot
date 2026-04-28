# Car Diagnostic Bot — FastAPI

## Project layout

```
.
├── main.py               ← FastAPI wrapper (this file)
├── diagnostic_engine.py  ← Your DiagSession engine (paste your code here)
└── requirements.txt
```

## Quick start

```bash
pip install -r requirements.txt
uvicorn main:app --reload            # dev
uvicorn main:app --host 0.0.0.0 --port 8000   # production
```

Then open http://localhost:8000/docs for the interactive Swagger UI.

---

## Typical API flow

### 1 — Create a session

```
POST /session
→ { "session_id": "abc-123...", "welcome": "🚗 ULTIMATE CAR..." }
```

### 2 — Chat (repeat as needed)

```
POST /session/abc-123.../chat
Body: { "message": "my engine is knocking" }
→ { "message": "...", "follow_up": "when", "done": false }
```

### 3 — (Optional) Fetch history

```
GET /session/abc-123.../history
→ { "turns": [...], "current_topic": "knock", "current_step": 1 }
```

### 4 — End session

```
DELETE /session/abc-123...
→ 204 No Content
```

---

## Config (top of main.py)

| Variable                   | Default | Purpose                                |
| -------------------------- | ------- | -------------------------------------- |
| `SESSION_TTL_MINUTES`      | 30      | Idle sessions expire after this        |
| `CLEANUP_INTERVAL_SECONDS` | 120     | How often expired sessions are evicted |
| `MAX_SESSIONS`             | 1000    | Hard cap on concurrent sessions        |

---

## Scaling to multiple workers

The in-memory `_sessions` dict is **not shared** across Uvicorn workers.
For multi-worker deployments, replace it with a Redis session store:

```python
import redis, pickle

r = redis.Redis(host="localhost", port=6379)

def _get_session(session_id):
    raw = r.get(session_id)
    if not raw:
        raise HTTPException(404, "Session not found")
    return pickle.loads(raw)

def _save_session(session_id, rec, ttl=SESSION_TTL_MINUTES * 60):
    r.setex(session_id, ttl, pickle.dumps(rec))
```

Then call `_save_session` after every `.respond()` call.

---

## Deployment (Railway / Render / Fly.io)

Add a `Procfile`:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Or a `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
