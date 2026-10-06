<p align="center">
  <img src="apps/mobile/public/icon.png" alt="SOLO Logo" width="88" />
</p>

<h1 align="center">SOLO</h1>
<p align="center"><strong>AI Auto-Framing Studio — Podcast Recording, Redefined</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-66fcf1?style=flat-square" />
  <img src="https://img.shields.io/badge/platform-Android%20%7C%20Web%20PWA-45a29e?style=flat-square" />
  <img src="https://img.shields.io/badge/stack-TypeScript%20%7C%20Python%20%7C%20HTML5-informational?style=flat-square" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" />
</p>

---

## 🎙️ What is SOLO?

**SOLO** is a single-phone studio-grade recording system for podcasters and content creators. Point your phone at two speakers, press Start, and SOLO handles everything automatically:

- 🏠 **Room Scan** — calibrates camera intrinsics and floor plane using AR
- 🎙️ **Voice ID** — each speaker reads a short shared script; SOLO fingerprints their voice using pitch autocorrelation
- 📐 **Seating Check** — validates physical speaker distance boundaries before rolling camera
- 🔴 **4K60 Recording** — locks to the main (normal) camera lens with fixed WB & Focus — no auto-switching, no wide distortion
- 🤖 **AI Auto-Framing** — in-browser MediaPipe face detection + VAD + EMA-smoothed crop engine dynamically frames the active speaker in real time
- 🎬 **Review & Nudge** — dual-panel review player (Wide Shot + AI Framed output) with manual nudge controls to correct crop decisions

---

## 🗂️ Project Structure

```
SOLO/
├── apps/
│   └── mobile/                  # Mobile-first Web App (PWA + Capacitor Android)
│       ├── public/
│       │   ├── index.html        # ★ Main app — all screens + in-browser AI pipeline
│       │   ├── manifest.json     # PWA manifest
│       │   └── sw.js             # Service Worker (offline support)
│       ├── src/
│       │   ├── calibration/      # AR room scan + seating geometry logic (TS)
│       │   ├── camera/           # CameraSession — 4K capture controller
│       │   ├── voice/            # Voice enrollment module
│       │   ├── upload/           # Chunked resumable uploader
│       │   └── review/           # Review player component
│       ├── android/              # Capacitor Android native shell
│       ├── src/server_simulator.ts  # Local dev server (serves public/ on :3000)
│       └── package.json
│
├── services/
│   ├── backend-api/             # Private REST API (Node.js + TypeScript)
│   │   ├── src/
│   │   │   ├── server.ts         # Express API server (port 4000)
│   │   │   ├── jobs/             # Pipeline job dispatcher
│   │   │   └── storage/          # MinIO/local storage service
│   │   ├── .env.example          # ← copy to .env and fill in secrets
│   │   └── package.json
│   │
│   └── pipeline/                # AI Processing Pipeline (Python)
│       ├── src/
│       │   ├── calibration.py    # Phase 0 — camera intrinsics + background plate
│       │   ├── timing_track.py   # Phase 2.1 — VAD + lip-motion fast track
│       │   ├── identity_track.py # Phase 2.2 — ECAPA-TDNN slow identity track
│       │   ├── framing_engine.py # Phase 2.3 — crop decision + EMA smoothing
│       │   ├── renderer.py       # Phase 2.3 — optical-flow edge fill renderer
│       │   ├── audio_cleanup.py  # Phase 2.4 — loudness normalisation + noise filter
│       │   ├── mvp_features.py   # Phase 3 — SRT subtitles + highlight clips
│       │   └── feedback_logger.py# Phase 4 — ML feedback / crop correction log
│       ├── main.py               # Pipeline orchestrator entrypoint
│       └── requirements.txt
│
├── scripts/
│   └── verify_full_system.py    # End-to-end system verification script
│
├── podcast-ai-camera-execution-plan.md  # Full engineering execution plan
├── .gitignore
└── README.md                    # ← you are here
```

---

## ⚡ Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Node.js | ≥ 18.x |
| npm | ≥ 9.x |
| Python | ≥ 3.10 |
| pip | latest |

---

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/solo.git
cd solo
```

---

### 2. Run the Mobile App (Web PWA)

```bash
cd apps/mobile
npm install
npx ts-node src/server_simulator.ts
```

Open **http://localhost:3000** in your browser, or open `http://<your-local-ip>:3000` on your phone (same Wi-Fi).

> **Tip:** For HTTPS camera access on mobile, use a tunnel:
> ```bash
> npx localtunnel --port 3000
> ```

---

### 3. Run the Backend API

```bash
cd services/backend-api
npm install

# Set up environment
cp .env.example .env
# → Edit .env with your actual values

npm start          # Production
npm run dev        # Development (same, with ts-node)
```

API runs on **http://localhost:4000**

---

### 4. Run the Python Pipeline

```bash
cd services/pipeline

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run pipeline test
python scripts/run_pipeline_test.py
```

---

## 🔐 Environment Variables

Never commit secrets. The backend API reads from a `.env` file.

Copy the template and fill in your values:

```bash
cp services/backend-api/.env.example services/backend-api/.env
```

| Variable | Description |
|----------|-------------|
| `PORT` | Backend API port (default: `4000`) |
| `MINIO_ENDPOINT` | MinIO / S3-compatible storage host |
| `MINIO_ACCESS_KEY` | Storage access key |
| `MINIO_SECRET_KEY` | Storage secret key |
| `MINIO_BUCKET` | Bucket name for session uploads |
| `PIPELINE_WORKER_URL` | URL of the Python pipeline worker |
| `PIPELINE_SECRET_TOKEN` | Shared secret for pipeline auth |
| `AWS_ACCESS_KEY_ID` | (Optional) AWS S3 access key |
| `AWS_SECRET_ACCESS_KEY` | (Optional) AWS S3 secret |

> The `.env` file is listed in `.gitignore` and will **never** be committed.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  SOLO Mobile App  (Browser PWA / Android Capacitor)      │
│                                                           │
│  [Start] → [Room Scan] → [Voice ID] → [Seating Check]    │
│         → [4K60 Record] → [Upload] → [AI Review]         │
│                                                           │
│  In-browser AI pipeline (MediaPipe + Web Audio API):      │
│    Face Detection → VAD → Active-Speaker Assignment       │
│    → EMA Crop Smoothing → Dual-Panel Canvas Render        │
└───────────────────┬─────────────────────────────────────┘
                    │ REST API (upload + dispatch)
                    ▼
┌─────────────────────────────────────────────────────────┐
│  Backend API  (Node.js / Express — port 4000)            │
│                                                           │
│  POST /api/sessions              ← session metadata       │
│  POST /api/sessions/:id/upload-url                        │
│  PUT  /api/sessions/:id/upload/:fileId ← binary upload    │
│  POST /api/sessions/:id/start-processing                  │
│  GET  /api/sessions/:id/status   ← job polling            │
└───────────────────┬─────────────────────────────────────┘
                    │ job dispatch
                    ▼
┌─────────────────────────────────────────────────────────┐
│  Python Pipeline  (5-phase processing)                   │
│                                                           │
│  Phase 0 — Calibration & Room Scan                        │
│  Phase 2.1 — Fast VAD + Lip Motion Track                  │
│  Phase 2.2 — Slow ECAPA-TDNN Identity Track               │
│  Phase 2.3 — Framing Engine + EMA Crop + Renderer         │
│  Phase 2.4 — Audio Cleanup (LUFS + noise filter)          │
│  Phase 3 — SRT Subtitles + Highlight Clips + Thumbnail    │
│  Phase 4 — Feedback Logger (ML training loop)             │
└─────────────────────────────────────────────────────────┘
```

---

## 📱 App Screens

| # | Screen | Purpose |
|---|--------|---------|
| 0 | **Welcome** | Start Session button — camera activates only on tap |
| 1 | **Room Scan** | AR plane detection, lens intrinsics calibration |
| 2 | **Voice Enrollment** | Both speakers read shared script; pitch fingerprinting |
| 3 | **Seating Check** | Distance validation (0.8m – 3.5m) before recording |
| 4 | **4K Recording** | Live recording with real-time timer, main lens locked |
| 5 | **Upload** | Chunked session upload to backend API |
| 6 | **AI Review** | Wide Shot + AI Framed dual-panel + Nudge controls |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

Please follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">Built with ❤️ — SOLO by <strong>Team IQOO</strong></p>
