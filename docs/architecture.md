# KaamLink architecture

## Overview

```mermaid
flowchart LR
  UI[React Vite UI] --> API[FastAPI]
  API --> STT[Groq Whisper STT]
  API --> LLM[Groq Llama JSON]
  API --> EMB[Local E5 embeddings]
  API --> DB[(SQLite)]
  API --> TTS[edge-tts]
  API --> RAG[docs_kb RAG]
  WA[Twilio WhatsApp optional] --> API
```

## Job request sequence

```mermaid
sequenceDiagram
  participant C as Contractor
  participant UI as React
  participant API as FastAPI
  participant G as Groq
  participant DB as SQLite

  C->>UI: Voice / text job
  UI->>API: POST /api/job/voice|text
  API->>G: Whisper (+ language hint)
  G-->>API: transcript
  API->>G: Llama JSON extract
  G-->>API: structured job
  API->>DB: save Job
  UI->>API: POST /api/match/{id}
  API->>DB: filter + embed score
  API-->>UI: top shortlist
  UI->>API: POST /api/alert/{id}
  API-->>UI: wave alerts + timeline
```

## Scoring

`total = 0.5*embedding + 0.25*reliability + 0.15*wage_fit + 0.10*area_match`

## Provider

All cloud LLM/STT calls use **Groq (Whisper + Llama)** only. Embeddings are local `intfloat/multilingual-e5-small`.
