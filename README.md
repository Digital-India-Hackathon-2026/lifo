# Kavach

**Team Lifo — Digital India Hackathon 2026** (see [ORIGINAL_SUBMISSION.md](./ORIGINAL_SUBMISSION.md) for the immutable original team/idea record)

## Problem Statement

India lost ₹22,495 crore to reported cyber fraud in 2025 alone, and AI-enabled "Digital Arrest" scams — fraudsters impersonating CBI, ED, RBI, or police on video calls using AI-generated voices and fake uniformed backdrops — have hit 47% of Indian adults, nearly double the global average. Existing deepfake detectors serve insurance back-offices or police investigators; nobody protects the ordinary citizen at the moment they receive the call. Kavach is that missing layer: it instantly verifies suspicious videos, voice notes, and government notices for AI manipulation or forgery, recognizes the Digital Arrest scam pattern and surfaces the government's own official warning in real time, flags phishing domains and fake social profiles, and — when a scam is confirmed — lets an AI honeypot persona engage the scammer to stall them and extract intelligence, while auto-drafting the citizen's cybercrime complaint.

## Features

**Core Detection**
- Deepfake/manipulation detection for image, video, and audio
- Government notice OCR + forgery/PII/scam-indicator check
- Phishing domain checker (typosquat scoring + PhishTank blocklist)
- Fake social media profile checker
- Digital Arrest pattern matcher (rule-based transcript analysis)
- Session-based honeypot: AI persona (Gemini via Vertex AI) engages a scammer over uploaded/recorded audio, transcribes with faster-whisper, replies with Cloud TTS

**Scam-Specific Detectors** (30+ rule-based classifiers)
Romance/pig-butchering, investment/trading, lottery/prize, courier/customs, business email compromise, matrimonial fraud, government-scheme/subsidy, QR-code (quishing), exam/scholarship, fake e-commerce/delivery, USSD call-forwarding, fake recruitment, sextortion, plus bonus detectors for e-challan, customer-care, KYC-update, rental listings, loyalty/cashback, and utility-bill scams

**Legal & Recovery**
- Evidence & complaint assistant (auto-drafted cybercrime complaint)
- e-Zero FIR templates
- Bank dispute tracker with RBI Ombudsman auto-escalation (90-day RBI Master Direction window)
- Asset-recovery status tracker

**Family & Community Safety**
- Family safe-word vault
- Paired-device panic alert
- Community reporting + risk heatmap
- Gamified scam-awareness training drills

**Privacy-Preserving Network Intelligence**
- Campaign graph entity linking (SHA256-hashed, zero-knowledge by construction)
- Federated privacy-preserving blocklist
- B2B threat-intel feed (hashed contacts only)
- DPDP-compliant consent management with on-demand purge

**Distribution Surfaces**
- Chat webhook (WhatsApp/Telegram), browser extension URL check, IVR, smart-TV broadcast, smart-speaker command webhook

**Note:** Vapi-based real-time telephony honeypot was built and branch-tested (`feature/vapi-honeypot-realtime`) but is not part of this submission's `main` branch — the deployed version uses the session-based audio-upload honeypot described above.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Pydantic v2 (every response JSON, global exception handler) |
| App Frontend | React + TypeScript + Tailwind (Vite) |
| Marketing Site | React Three Fiber + TypeScript (Vite) |
| Video/Image classifier | `dima806/deepfake_vs_real_image_detection` (ViT, HuggingFace, local inference) |
| Audio classifier | `Gustking/wav2vec2-large-xlsr-deepfake-audio-classification` (local inference) |
| Document OCR | Google Cloud Vision API |
| Honeypot STT | faster-whisper (local, CPU) |
| Honeypot persona | Gemini 2.5 Flash Lite via Vertex AI |
| Honeypot TTS | Google Cloud Text-to-Speech |
| Storage | SQLite (SQLAlchemy 2.0) |
| Hosting | GCP Cloud Run (backend), Firebase Hosting (frontend + marketing) |

## Running Locally

Three separate dev servers.

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GOOGLE_CLOUD_PROJECT, GOOGLE_APPLICATION_CREDENTIALS, etc.
uvicorn app.main:app --reload --port 8000
```

**Frontend (app)**
```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

**Marketing site**
```bash
cd marketing
npm install
cp .env.example .env   # set VITE_APP_URL=http://localhost:5174
npm run dev
```

## Deployed URLs

| Surface | URL |
|---|---|
| Backend API (GCP Cloud Run) | `TODO: insert once Cloud Run redeploy is confirmed healthy — see parent session` |
| App (Firebase Hosting) | https://kavach-501620-app.web.app |
| Marketing site (Firebase Hosting) | https://kavach-marketing.web.app |

## Known Limitations

- **SQLite storage** — all persistence (case files, campaign graph, blocklist, consent, dispute tracking, etc.) uses a single local SQLite file, not a production-grade managed database.
- **No scheduled-purge automation** — DPDP consent purge (`POST /compliance/consent/purge-expired`) and bank-dispute overdue detection (`GET /legal/dispute/{case_id}/status`) are on-demand sweeps only; no task scheduler is wired up (e.g. GCP Cloud Scheduler would need to call these endpoints on a cadence in production).
- **No session TTL** — honeypot sessions and vulnerable-user call sessions are held in memory with no expiry, which would grow unbounded in a long-running production deployment.
- **No real telephony** — the honeypot is a session-based audio-upload/browser-mic simulator, not live SIP/WebRTC/cellular call routing. Real telecom-level integration (Twilio Programmable Voice or a SIP provider) is a future step.
- **Phishing domain check** uses a local PhishTank cache rather than a live per-request API call, and the fake-social-profile checker is a heuristic v1 that hasn't had a calibration pass on false positives yet.
- **Smart-TV broadcast and Item 43 (landline adapter)** are an honest hardcoded stub and a documentation-only concept note respectively — no real hardware/platform integration is in scope.
