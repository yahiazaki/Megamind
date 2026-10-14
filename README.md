<p align="center"><img src="frontend/public/megamind-logo.svg" width="110" alt="Megamind logo"></p>

<h1 align="center">Megamind</h1>
<p align="center">A local-first personal AI: a study assistant over five years of my notes, and a portfolio that answers recruiters' questions about me.</p>

> Status: **local preview, not production.** Everything runs on one Windows laptop (RTX 5050, 8 GB VRAM) with free, open models.

## What it does

| Area | Features |
|---|---|
| **Knowledge book** | All my study notes (security, networking, Bash, APIs, databases, Python, design patterns, embedded/RTOS) translated from Arabic/Franco-Arabic to English, merged into one bookmarked PDF with a contents page and page numbers, plus supplementary chapters for important gaps. |
| **Study chat (RAG)** | Ask in English, Arabic or Franco. Answers are grounded in the book with inline citations; clicking a citation opens the exact page with the passage highlighted, and links into the book PDF. |
| **Study sessions** | `/quiz [n] [topic]` generates MCQ + short-answer questions from my notes and grades them; `/end` summarises the session (strengths, weak spots, what to study next with book pages) and sends it to my WhatsApp. |
| **Admin library** | Upload Word, PDF, Markdown or text (or write a note). Megamind translates it when needed, converts it to PDF, appends it to the book next to its subject, and indexes it. |
| **Reminders** | `/remind …` or plain language ("fakarny bokra 6 el sobh…") creates Google Calendar events; every morning a WhatsApp message lists the day's plan. |
| **Portfolio** | Public page with experience, projects, skills, and an "Ask about Yahia" chat restricted to my profile and public work log. |
| **CV generator** | Paste a job description → a tailored one-page CV (Word + PDF) built only from my real experience and work log. |
| **Work log** | Track tasks and achievements as they happen; they feed the CV generator and (optionally) the portfolio. |

## Architecture

```
frontend/  React + Vite + TypeScript + Tailwind  (portfolio, admin panel)
backend/   FastAPI + SQLite (SQLModel)
  app/ingest   docx/pdf/md → (translate) → Word PDF export → page-anchored chunks → book
  app/rag      hybrid retrieval: bge-m3 dense vectors + BM25, reciprocal-rank fusion,
               LLM query rewriting for Franco/Arabic and follow-up questions
  app/services study sessions, quizzes, CV, reminders, WhatsApp, Google Calendar, scheduler
knowledge/supplements/   extra chapters (Markdown) added to the book
data/        (git-ignored) notes, generated PDFs, database, tokens
```

- **LLM:** `qwen3:8b` via [Ollama](https://ollama.com) (local, free). Switchable in Settings to any Anthropic Messages-compatible endpoint.
- **Embeddings:** `bge-m3` via Ollama (multilingual, 1024-d).
- **PDF:** Microsoft Word COM export (best fidelity for screenshots and Arabic), LibreOffice fallback, PyMuPDF for the book, chunking and page previews.
- **WhatsApp:** [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/) free API. Every message is also kept in the Outbox.
- **Calendar:** Google Calendar API (free) with OAuth.

## Setup (Windows)

Prerequisites: Python 3.12+, Node 20+, [Ollama](https://ollama.com/download), Microsoft Word (or LibreOffice).

```powershell
# 1. models
ollama pull qwen3:8b
ollama pull bge-m3

# 2. backend
cd backend
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 3. frontend
cd ..\frontend
npm install
npm run build

# 4. configuration
cd ..
copy .env.example .env      # then set ADMIN_PASSWORD, SECRET_KEY, WHATSAPP_PHONE …
```

### Load the notes

Put the source documents in `data/sources/` (`01-security.docx`, `02-networks.docx`, …) and, optionally, a profile in `data/profile.json` (see `backend/scripts/profile.example.json`). Then:

```powershell
cd backend
.\.venv\Scripts\python scripts\translate_tool.py extract   # find Arabic / Franco paragraphs
.\.venv\Scripts\python scripts\translate_tool.py apply     # write translated .docx (from data/translation/*.json)
.\.venv\Scripts\python scripts\bootstrap.py                # ingest everything and build the book
```

New documents are easier to add from **Admin → Library**: translation runs automatically there with the local model.

### Run

```powershell
.\start.ps1
```

- Portfolio: http://localhost:8000
- Admin: http://localhost:8000/admin
- Frontend dev server with hot reload: `cd frontend; npm run dev` → http://localhost:5173 (proxies `/api` to :8000)

## Integrations

**WhatsApp (CallMeBot):** add CallMeBot's number (from their site) to your contacts, send it `I allow callmebot to send me messages`, then paste the API key it replies with into **Settings**. Use *Send a test message* to verify.

**Google Calendar:** in Google Cloud Console create a project, enable the *Google Calendar API*, configure the OAuth consent screen (External, add yourself as a test user), create an **OAuth client ID → Web application** with the redirect URI `http://localhost:8000/api/google/callback`, save the JSON as `data/google/client_secret.json`, then click **Connect Google Calendar** in Settings.

## Privacy

`data/` and `.env` are git-ignored. The repository contains code and the supplementary chapters only. My notes, CVs, the generated book, the database and tokens never leave the machine. The public portfolio exposes only the profile fields I choose (the phone number is hidden by default). The recruiter chat is rate-limited and cannot see the notes.

## Roadmap

- Deploy the portfolio publicly (the chat would then need a hosted model or API key).
- OCR / vision captions for screenshots inside the notes.
- Optional cross-encoder reranker (bge-reranker-v2-m3) once VRAM allows.
