# KaamLink

Voice-first contractor ↔ worker matching for Chennai / Chengalpattu.

**Provider: Groq (Whisper + Llama)** · local `multilingual-e5-small` embeddings · SQLite.

![screenshot-home](docs/screenshot-home.png)
![screenshot-contractor](docs/screenshot-contractor.png)

## Features

- Voice/text job & worker onboarding (language chip + Demo mode)
- Structured extraction + clarifying questions
- Embedding shortlist with score breakdown
- Wave alerts (5 at a time) with timeout auto-fallback + simulate replies
- Wage suggestion / lowball flag
- edge-tts play button on alerts
- Ask KaamLink RAG Q&A
- LLM vs Regex eval + Analytics dashboard
- Optional Twilio WhatsApp sandbox

## Setup

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env   # paste GROQ_API_KEY
rm -f kaamlink.db && python seed.py
uvicorn app.main:app --reload --port 8000
# new terminal
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

## Env vars

| Var | Required | Default |
|-----|----------|---------|
| `GROQ_API_KEY` | yes* | — |
| `GROQ_LLM_MODEL` | no | `llama-3.3-70b-versatile` |
| `GROQ_FAST_MODEL` | no | `llama-3.1-8b-instant` |
| `GROQ_STT_MODEL` | no | `whisper-large-v3` |
| `ALERT_TIMEOUT_SECONDS` | no | `60` |
| `DEMO_MODE` | no | `false` |
| `ENABLE_TWILIO` | no | `false` |
| `TWILIO_*` | if Twilio | — |
| `CORS_ORIGINS` | no | `*` |
| `PORT` | deploy | `8000` |

\*Without a key, enable Demo mode in the UI (canned STT/extraction).

## Eval

```bash
cd backend && source .venv/bin/activate
python ../eval/run_eval.py
# or POST /api/eval/run from Metrics page
```

## WhatsApp (optional)

1. Set `ENABLE_TWILIO=true` and Twilio sandbox credentials in `.env`.
2. `ngrok http 8000` → set sandbox webhook to `https://<ngrok>/whatsapp`.
3. Join sandbox; send a job voice note or text; workers can reply YES/NO / haan / illai.

## Deploy (Render / Railway)

1. Build frontend into `frontend/dist` (Dockerfile / render.yaml do this).
2. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` with `PYTHONPATH=backend`.
3. Paste env vars: `GROQ_API_KEY`, model names above. `AUTO_SEED=true` seeds on first boot.
4. Or: `docker build -t kaamlink . && docker run -p 8000:8000 -e GROQ_API_KEY=... kaamlink`

## Docs

- [Architecture](docs/architecture.md)
- [3-minute demo script](docs/demo_script.md)

## Tests

```bash
cd backend && source .venv/bin/activate && pytest -q
```
