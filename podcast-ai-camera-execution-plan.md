# AI Auto-Framing Podcast Camera — End-to-End Execution Plan

**A note on how this document is numbered, so nothing gets confusing later:** every cross-reference in this document points to a **Phase number** (Phase 0–5) or a **Risk number** (Risk 1–4) — never to a section number. Section headers below are unnumbered on purpose; use the Contents list to navigate. This means inserting a new section later never breaks an existing cross-reference, and "Phase 1.4" always means the same thing everywhere it's mentioned.

## Contents

- [What We're Building](#what-were-building)
- [This Is a Mobile App, Not a Website](#this-is-a-mobile-app-not-a-website)
- [Why This Can't Just Use the Phone's Stock Camera App](#why-this-cant-just-use-the-phones-stock-camera-app)
- [System Overview](#system-overview)
- [Architecture & Tech Stack (Free / Open-Source)](#architecture--tech-stack-free--open-source)
- [Phase 0 — Calibration & Room Scan](#phase-0--calibration--room-scan)
- [Phase 1 — Capture Flow (App)](#phase-1--capture-flow-app)
- [Phase 2 — Cloud Processing Pipeline](#phase-2--cloud-processing-pipeline)
- [Phase 3 — MVP Feature Layer](#phase-3--mvp-feature-layer)
- [Phase 4 — Learning & Feedback Loop](#phase-4--learning--feedback-loop)
- [Phase 5 — Polish & Scale](#phase-5--polish--scale)
- [Known Engineering Risks & Mitigations](#known-engineering-risks--mitigations)
- [Full Dependency Graph](#full-dependency-graph)
- [Suggested Build Order](#suggested-build-order)

---

## What We're Building

A **single-phone recording app** for podcasters that:
1. Calibrates the camera and scans the room before recording.
2. Enrolls each speaker's voice.
3. Records raw footage at max quality on the main lens.
4. Post-processes it into a finished 16:9 video that automatically frames whoever is speaking, fills in missing edges from real room-background data, and applies audio cleanup, captions, and highlight clips.

This document covers **all work, in dependency order, with the reasoning behind each step**, the tech stack for every layer, and known engineering risks with their mitigations.

---

## This Is a Mobile App, Not a Website

Worth stating plainly, because it shapes every tech choice below:

- The product is a **native iOS app and a native Android app** — there is no public website, and no web frontend to build or maintain.
- The "cloud" pieces described later (processing pipeline, storage, orchestration) are **private backend services that only the mobile app talks to**, not a website. Nobody visits them in a browser; they exist purely to do the heavy processing a phone can't do alone.
- Anywhere this document says "backend," "API," or "cloud pipeline," read that as *"a service the app calls over the network,"* never as *"a page someone browses to."*
- This also means there's no need for web-specific tech (frontend frameworks, browser hosting, SEO, responsive web design) anywhere in this plan — every tech choice below is either **on-device mobile SDK** or **backend/processing infrastructure**.

---

## Why This Can't Just Use the Phone's Stock Camera App

There is no public API to inject custom logic (calibration data pull, ARKit session, custom crop-box overlays) into the OS's stock Camera app. So:

- We must build **our own capture screen** using the platform's low-level camera framework:
  - iOS: `AVFoundation` (+ `ARKit` for scene/calibration data)
  - Android: `CameraX` or `Camera2` (+ `ARCore` for scene/calibration data)
- What we *can* reuse from the OS, so we're not reinventing everything:
  - Save finished exports to the native Photos/Gallery app
  - System share sheet for exporting to YouTube/Instagram/etc.
  - OS-level permissions flow for camera/microphone/motion sensors
  - Background audio session handling (so calls/notifications don't kill a recording)

**Why this matters early:** every downstream feature (calibration, framing, background plates) depends on us owning the capture pipeline, not the stock app. This is a foundational architecture decision, not an afterthought.

---

## System Overview

```
[Native Mobile App — iOS / Android]
   ├── Setup Flow (calibration + room scan + voice enrollment)
   ├── Capture Engine (AVFoundation/CameraX, max-res recording)
   ├── Local Storage (raw video + calibration/voice metadata)
   └── Upload → [Private Backend — API only, not a website]
                    ├── VAD + Acoustic Onset (cut-timing trigger)
                    ├── Diarization & ASR (identity + transcript, not timing)
                    ├── Face/Active-Speaker Tracking (visual confidence, can veto audio)
                    ├── Framing Decision Engine (debounced cut timing)
                    ├── Crop + Dynamic Edge-Fill Renderer (optical flow / plate hybrid)
                    ├── Audio Cleanup
                    └── Feature Layer (captions, highlights, trimming)
                              ↓
                    [Finished Video + Exports] → back to app for review/export
```

Backend-processed for v1 (faster iteration, heavier compute than a phone can do alone), with an eye toward moving lightweight parts (face detection, basic framing) on-device later for cost/latency. The pipeline is deliberately split into a **fast timing track** (VAD + visual confidence, drives *when* cuts happen) and a **slow identity track** (ASR + diarization, drives *who* is on screen) — see [Risk 3](#risk-3--av-drift--diarization-driven-timing-delay) for why these can't be merged into one signal.

---

## Architecture & Tech Stack (Free / Open-Source)

Every tool listed below is free to self-host or has a free tier — no paid licenses required to build and run the MVP. Where a layer runs (on the phone vs. on the backend) is called out explicitly, since that distinction matters more than usual for a mobile-first product.

### Layer 1 — Mobile App: Capture & Calibration *(runs on-device)*

| Component | iOS | Android | Why |
|---|---|---|---|
| Camera capture | `AVFoundation` | `CameraX` / `Camera2` | Free, built into the OS SDK. Only these give frame-level control needed to lock lens/format (see [Phase 1.4](#phase-1--capture-flow-app)) |
| Room scan / calibration | `ARKit` | `ARCore` | Free, built into the OS SDK. Gives intrinsics, real-world scale, and point-cloud in one pass (see [Phase 0.1](#phase-0--calibration--room-scan)) |
| Fallback calibration | `AVCameraCalibrationData` | `Camera2` `LENS_INTRINSIC_CALIBRATION` | Free, built-in. Used when AR isn't available (see [Phase 0.2](#phase-0--calibration--room-scan)) |
| Live face detection (seating check) | `Vision` framework | `ML Kit Face Detection` | Free. Real-time, on-device, no network round-trip needed for the live preview overlay |
| Local storage before upload | `FileManager` | Android `EncryptedFile` (Jetpack Security) | Free, part of the OS SDK. Keeps raw footage encrypted on-device until upload completes |
| Background upload | `URLSession` background tasks | `WorkManager` | Free, part of the OS SDK. Large 4K files need resumable, OS-survivable uploads |

### Layer 2 — Backend: Ingestion & Storage *(runs on the backend, not visible to users as a website)*

| Component | Tech | Why |
|---|---|---|
| Object storage | **MinIO** (self-hosted, S3-compatible) | Free and open-source; stores raw footage, background plates, and finished exports without a paid cloud storage bill |
| API service | **Node.js** (NestJS) or **Go**, self-hosted | Free, open-source frameworks. Handles auth, upload URLs, and job triggering — an API only the app calls, never a public page |
| Metadata database | **PostgreSQL** | Free, open-source. Stores sessions, calibration data, voiceprint references, job status |
| Job/session cache | **Redis** | Free, open-source. Fast lookups for in-progress job status shown in the app |
| Authentication | **Keycloak** (self-hosted) | Free, open-source identity provider — avoids paid auth services |

### Layer 3 — Backend: Orchestration & Compute

| Component | Tech | Why |
|---|---|---|
| Workflow orchestration | **Temporal** or **Apache Airflow** (self-hosted) | Free, open-source. The pipeline is multi-stage with real dependencies (see the [Dependency Graph](#full-dependency-graph)) — needs retries and parallel branches, not just a linear script |
| Job queue | **Apache Kafka** or **RabbitMQ** (self-hosted) | Free, open-source. Decouples "upload finished" from "processing starts" |
| Compute | **Kubernetes**, self-hosted on rented GPU servers | Kubernetes itself is free and open-source; only the underlying GPU hardware time costs money — there's no way around paying for the compute itself, but the orchestration software is free |

### Layer 4 — Processing Pipeline: Fast Timing Track *(backend — decides *when* a cut happens)*

| Component | Tech | Why |
|---|---|---|
| Voice Activity Detection | **Silero VAD** or **WebRTC VAD** | Free, open-source. Sub-frame accurate, avoids the ASR lag described in [Risk 3](#risk-3--av-drift--diarization-driven-timing-delay) |
| Acoustic onset detection | **librosa** (Python) | Free, open-source. Pinpoints the exact moment speech energy begins |
| Visual active-speaker confidence | **Light-ASD** / **TalkNet** (open-source models), or **MediaPipe Face Mesh** for a lighter lip-movement heuristic | Free, open-source. Gives the visual signal that gets veto power during mic bleed ([Risk 4](#risk-4--voice-enrollment-bleed--cross-talk-misattribution)) |
| Face detection/tracking | **RetinaFace** or **MediaPipe** (detection) + **ByteTrack** (tracking) | Free, open-source. Keeps consistent per-person identity across the session |

### Layer 5 — Processing Pipeline: Slow Identity Track *(backend — decides *who* is speaking and produces the transcript)*

| Component | Tech | Why |
|---|---|---|
| Transcription (ASR) | **OpenAI Whisper**, self-hosted | Free, open-source. No per-minute transcription fee since it runs on your own GPU compute |
| Speaker diarization | **pyannote-audio** or **NVIDIA NeMo** (diarization module) | Free, open-source. Purpose-built diarization models |
| Voiceprint / speaker embeddings | **SpeechBrain (ECAPA-TDNN)** or **Resemblyzer** | Free, open-source. Generates the enrollment embeddings from [Phase 1.2](#phase-1--capture-flow-app) |

### Layer 6 — Framing Decision Engine *(backend)*

| Component | Tech | Why |
|---|---|---|
| Rule engine (v1) | Custom **Python** service | Free. Rule-based per [Phase 2](#phase-2--cloud-processing-pipeline) — simpler to debug than ML before real correction data exists |
| Smoothing / debounce | Plain Python (Kalman filter or exponential moving average) | Free. Produces the eased pans/zooms and the ~400ms debounce from [Risk 3](#risk-3--av-drift--diarization-driven-timing-delay) |
| Future learned model (Phase 4) | **PyTorch** | Free, open-source. Replaces/augments the rule engine once correction data exists |

### Layer 7 — Rendering & Compositing Engine *(backend)*

| Component | Tech | Why |
|---|---|---|
| Core video processing | **FFmpeg** | Free, open-source, the industry standard. Handles crop, overlay, scale |
| Optical flow (dynamic edge-fill) | **OpenCV** (Farneback/DIS, fast) or **RAFT** (deep-learning, higher quality) | Free, open-source. Implements the [Risk 1](#risk-1--background-plate-compositing-vs-dynamic-room-changes) mitigation — extending background plausibly frame-to-frame instead of pasting a stale plate |
| Background plate alignment | **OpenCV** (feature matching + homography) | Free, open-source. Aligns a background plate to the live frame's perspective before use as a fallback |

### Layer 8 — Audio Cleanup *(backend)*

| Component | Tech | Why |
|---|---|---|
| Loudness normalization | **FFmpeg `loudnorm` filter** | Free. Broadcast-grade loudness matching between speakers — this is the direct fix for the original two-phone mic-mismatch problem |
| Noise reduction | **RNNoise** or **DeepFilterNet** | Free, open-source, real-time-capable denoising models |

### Layer 9 — MVP Feature Layer *(backend, reuses Layer 4/5 outputs)*

| Feature | Tech | Why |
|---|---|---|
| Captions/subtitles | Whisper transcript → SRT/VTT (custom script) | Free — reuses the ASR output already in the pipeline |
| Filler-word/silence trimming | Transcript timestamps → FFmpeg cut-list | Free — pure timestamp math, no new model needed |
| Highlight-clip detection | Audio energy scoring + transcript keyword scoring; optionally a **self-hosted open LLM** (e.g., Llama 3) for ranking | Free if self-hosted — avoids a per-call fee from a commercial LLM API |
| Thumbnail selection | **OpenCV** frame-quality scoring | Free — reuses face-tracking data already computed |

### Layer 10 — Learning & Feedback Loop *(backend)*

| Component | Tech | Why |
|---|---|---|
| Correction logging | **PostgreSQL** (metadata) + **MinIO** (raw examples) | Free, open-source |
| Training pipeline | **PyTorch**, scheduled via **Airflow** | Free, open-source. Periodic offline retraining, not live/online learning — see [Phase 4](#phase-4--learning--feedback-loop) for why |
| Model tracking | **MLflow** | Free, open-source. Tracks model versions as the framing engine evolves from rule-based to learned |

### Layer 11 — Mobile App: Review & Export *(runs on-device, talks to the backend API)*

| Component | iOS | Android | Why |
|---|---|---|---|
| In-app preview/correction UI | `AVPlayer` + custom overlay | `ExoPlayer` + custom overlay | Free, part of the OS SDK. Where users nudge crop decisions, feeding [Phase 4](#phase-4--learning--feedback-loop) |
| Receiving finished exports | Signed download URL from MinIO | Same | Free — no paid CDN required at MVP scale |

### Layer 12 — DevOps, Security & Monitoring

| Component | Tech | Why |
|---|---|---|
| CI/CD | **GitHub Actions** (free tier) | Free for individual/small-team use; integrates with containerized deploys |
| Monitoring | **Prometheus + Grafana** (self-hosted) | Free, open-source. The pipeline has many stages — need visibility into where jobs fail or slow down |
| Error tracking | **Sentry** (self-hosted, open-source edition) | Free when self-hosted |
| Encryption | TLS in transit; disk-level encryption at rest on the storage layer | Free — built into standard tooling, not an add-on cost |

### Crux Summary (one line per layer)

| Layer | Free / Open-Source Tech |
|---|---|
| Mobile capture & calibration | AVFoundation / CameraX + ARKit / ARCore |
| Backend storage & API | MinIO, Node.js/Go, PostgreSQL, Redis, Keycloak |
| Orchestration & compute | Temporal / Airflow, Kafka, Kubernetes |
| Fast timing track | Silero VAD, librosa, Light-ASD/MediaPipe, RetinaFace + ByteTrack |
| Slow identity track | Whisper, pyannote-audio, SpeechBrain |
| Framing engine | Python + PyTorch |
| Rendering & compositing | FFmpeg, OpenCV, RAFT |
| Audio cleanup | FFmpeg loudnorm, RNNoise / DeepFilterNet |
| MVP features | Whisper transcript reuse, OpenCV, self-hosted Llama (optional) |
| Learning loop | PyTorch, MLflow |
| Mobile review/export | AVPlayer / ExoPlayer |
| DevOps | GitHub Actions, Prometheus + Grafana, Sentry |

**One honest caveat:** "free" here means no software licensing cost — self-hosting GPU compute for Whisper, diarization, and rendering still costs real money in server time at scale. The savings are in avoiding per-minute/per-call fees from commercial APIs, not in avoiding infrastructure cost entirely.

---

## Phase 0 — Calibration & Room Scan

**Why we need this at all:** every later decision (how tight we can crop, how to fill missing edges, how to map "person moved" to real pixel offsets) depends on knowing how the camera's pixels map to real-world space. Skipping this means the framing engine is guessing blind.

**Phase 0.1 — Primary path: piggyback on AR frameworks (recommended default)**
- Use **ARKit** (iOS) / **ARCore** (Android) during the room-scan step.
- User walks the phone around the room for a few seconds as part of setup — a natural, low-friction motion.
- This single step gives us, for free:
  - Camera intrinsics (focal length, optical center, distortion) — continuously refined via visual-inertial odometry
  - Real-world scale (metric distances, not just relative)
  - A rough depth/point-cloud of the room
- **Why this is primary:** zero extra user action beyond what we already wanted (room reference capture), and more accurate than a static checkerboard since it fuses camera + gyroscope + accelerometer data over the scan.

**Phase 0.2 — Fallback path: read factory calibration data directly**
- If ARKit/ARCore isn't available or the device is unsupported:
  - iOS: pull `AVCameraCalibrationData` (intrinsic matrix + lens distortion) directly.
  - Android: pull `LENS_INTRINSIC_CALIBRATION` / `LENS_DISTORTION` from `Camera2` characteristics.
- **Why keep this as a fallback:** some budget Android devices don't expose full AR support, but almost all expose basic factory calibration — this avoids ever forcing the user through a manual checkerboard flow.

**Phase 0.3 — Scale/reference anchor during the same scan**
- While scanning, run face detection on any people already in frame, or ask the user to hold up a standard object (e.g., a card of known size) for one frame if extra scale confidence is needed.
- **Why:** ARKit/ARCore already gives metric scale, but a face-size or known-object cross-check adds robustness against drift, especially in small or feature-poor rooms.

**Phase 0.4 — Output of Phase 0**
- Camera intrinsics + distortion coefficients
- Real-world scale factor (pixels-per-meter at typical seating depth)
- Room point-cloud / depth map
- A set of **background reference plates** (frames captured during the scan) — used as a **starting reference and fallback** for edge-filling, not as a permanent static overlay (see [Risk 1](#risk-1--background-plate-compositing-vs-dynamic-room-changes) for why, and how this evolves during recording)

**Phase 0.5 — Scope boundary: AR session runs only during setup, not during recording**
- The ARKit/ARCore session (Phase 0.1) is used **only** to build calibration + point-cloud + plates during the setup scan.
- It is deliberately **not** kept running during actual 4K recording — running AR tracking concurrently with high-bitrate video capture on a single primary lens risks hardware frame-dropping on many devices.
- **Why this matters:** it removes a real resource conflict between two demanding subsystems (AR session + 4K60 encode) by simply not running them at the same time. If a future version needs continuous live depth during recording, that's a deliberate scope expansion to design for separately — not something Phase 0 needs to solve now.

**Dependency:** nothing upstream — this is step one. Everything else consumes this data.

---

## Phase 1 — Capture Flow (App)

Builds directly on Phase 0's output.

**Phase 1.1 — Room scan** (Phase 0, above) — produces calibration + background plates.

**Phase 1.2 — Voice enrollment** — each speaker reads a short on-screen prompt; extract a voiceprint embedding (SpeechBrain/Resemblyzer, see Layer 5) per speaker.
- *Why now:* needs to happen before recording so diarization has reference voiceprints ready; doesn't depend on calibration, so can run in parallel with the room scan.

**Phase 1.3 — Guided seating check** — live preview with face-detection overlay; using the scale factor from Phase 0, **enforce** (not just warn about) a strict distance/spacing boundary before allowing recording to start.
- *Why enforce rather than just warn:* since the main lens is locked (no ultra-wide fallback, per Phase 1.4), pan-and-scan headroom is fixed and finite. A person seated outside the safe zone cannot be fixed later by cropping — so this has to be a hard gate, not a soft suggestion.

**Phase 1.4 — Recording** — main lens locked, explicit fixed format (e.g., 4K60), fixed focus, fixed white balance; automatic lens switching (wide↔ultra-wide↔telephoto) disabled entirely for the session.
- *Why main lens + max res:* preserves crop headroom for later digital zoom without relying on lower-quality ultra-wide glass.
- *Why lock the format explicitly:* modern phones auto-switch physical lenses mid-stream based on distance/lighting; letting this happen mid-recording would silently change intrinsics and framing math partway through. Locking format also avoids the AR+4K concurrency conflict from Phase 0.5, since no AR session competes with the encoder during capture.
- *Why this limits us, and how we compensate:* locking to the main lens caps total digital pan-and-scan headroom for subjects sitting far apart. This is why Phase 1.3's seating boundary is strict, not just advisory.

**Dependency:** Phase 1 requires Phase 0 complete (calibration + plates) before recording begins; voice enrollment (1.2) can run in parallel with the room scan (1.1).

---

## Phase 2 — Cloud Processing Pipeline

Consumes: raw video + calibration data + background plates + voiceprints (all from Phase 0/1). Runs entirely on the backend — see [Architecture & Tech Stack](#architecture--tech-stack-free--open-source) Layers 4–8 for the concrete tools behind each step below.

The pipeline is split into two tracks that feed the framing engine separately — see [Risk 3](#risk-3--av-drift--diarization-driven-timing-delay) for why they must not be merged into one signal.

**Phase 2.1 — Fast timing track** (drives *when* a cut happens):

| Step | What it does | Why it's needed | Depends on |
|---|---|---|---|
| VAD + acoustic onset detection | Lightweight, sub-frame voice-activity + energy-onset detection on raw audio | Gives a low-latency trigger for cut timing that lines up with the actual moment speech starts, avoiding the 200–500ms lag inherent in ASR-based timestamps | Raw audio |
| Visual active-speaker confidence | Lip-movement/face-motion confidence score per tracked face, per frame | Cross-checks the audio trigger against who is visibly speaking; gets **veto power** over the audio signal during flagged high-bleed segments (see [Risk 4](#risk-4--voice-enrollment-bleed--cross-talk-misattribution)) | Face tracking + raw video |

**Phase 2.2 — Slow identity track** (drives *who* and *what*, not timing):

| Step | What it does | Why it's needed | Depends on |
|---|---|---|---|
| Diarization + ASR | Match voice segments to enrolled voiceprints; generate transcript | Establishes speaker identity and produces transcript text for captions/trimming — but is **not** used to time visual cuts | Voice enrollment (Phase 1.2) |
| Face/active-speaker tracking | Detect + track faces per frame | Confirms *where* each identified speaker is on-screen | Raw video |

**Phase 2.3 — Framing + rendering:**

| Step | What it does | Why it's needed | Depends on |
|---|---|---|---|
| Framing decision engine | Rule-based crop-box path per frame: triggered by VAD+onset (not ASR), identity resolved via diarization+visual-veto fusion, cap max zoom (from calibration scale), debounced minimum-hold (~400ms) to avoid whiplash cuts on brief interjections, widen to two-shot on overlap/silence | This *is* the core product value — auto camera operator, timed off the right signal | Fast timing track + slow identity track + calibration scale (Phase 0.4) |
| Crop + dynamic edge-fill renderer | Apply crop-box path; where crop exceeds captured frame, fill edges using **optical-flow-based background expansion or contextual blur** as the default, with the Phase 0 background plates used only as an initial reference / low-motion fallback (see [Risk 1](#risk-1--background-plate-compositing-vs-dynamic-room-changes)) | Produces the finished 16:9 frame while avoiding seams, mismatched shadows, or ghosting from a stale static plate as the room changes over a long session | Framing engine + background plates + live frame data |

**Phase 2.4 — Audio cleanup:**

| Step | What it does | Why it's needed | Depends on |
|---|---|---|---|
| Level-matching / normalization | Matches loudness between speakers | Fixes the original loud/quiet mic-bleed problem that started this whole project | Diarization (Phase 2.2) |
| Noise reduction | Removes background hiss/hum | Cleans up untreated-room recordings | Raw audio |

**Why rule-based first, not ML-based framing:** faster to ship, fully debuggable, and gives us a working product before we have any real user-correction data to train a learned model on (that comes in Phase 4).

---

## Phase 3 — MVP Feature Layer

Built on top of artifacts Phase 2 already produces — cheap to add because the hard part (ASR, diarization, tracking) is already done. See Layer 9 for the specific tools.

| Feature | Reuses |
|---|---|
| Filler-word/silence trimming | ASR transcript timestamps (Phase 2.2) |
| Auto captions/subtitles | ASR transcript (Phase 2.2) |
| Highlight-clip detection → 9:16 exports | Audio energy/tone + transcript signals |
| Auto thumbnail selection | Face tracking (Phase 2.2) |

**Why this order:** these are the highest "wow factor per engineering hour" additions once the core pipeline exists — no new heavy infrastructure required.

---

## Phase 4 — Learning & Feedback Loop

- In-app review screen (Layer 11): user nudges/corrects crop decisions per segment.
- Log corrections as labeled training data (Layer 10).
- Periodically retrain: evolve the rule-based framing engine (Phase 2.3) into a learned model (predicting crop-box from audio+face features) once enough real corrections exist.

**Why not sooner:** online/live learning is high-risk (drift, cost) and there's no useful training signal until real users have generated correction data against a working rule-based baseline.

**Dependency:** requires Phase 2 (framing engine) live in production with real users first.

---

## Phase 5 — Polish & Scale

- Move latency-tolerant components (face detection, basic framing) on-device to cut backend cost/latency; keep heavy components (ASR, any generative outpainting fallback) on the backend.
- Multi-format export bundle (16:9 / 9:16 / 1:1 / audio-only).
- Branding templates, lower-thirds, intro/outro.
- Show notes/transcript auto-draft export.

**Why last:** these are scaling/cost/polish concerns — valuable, but only worth optimizing once the core product is validated and has real usage volume to justify the engineering cost.

---

## Known Engineering Risks & Mitigations

These are gaps that surface once you look past the happy path. Each one changes a specific piece of the plan above — cross-referenced inline.

### Risk 1 — Background-plate compositing vs. dynamic room changes

- **The fault:** Static reference plates (Phase 0.4) assume nothing in the room changes. Over a real session — light shifting as clouds pass, a chair getting moved, someone walking into frame — compositing a stale plate onto live video produces visible seams, mismatched shadows, or ghosting.
- **The mitigation:** Default to **optical-flow-based background expansion or a subtle contextual blur** for edge-fill, rather than pasting in the static plate directly (Phase 2.3, Layer 7). The Phase 0 plates remain useful as an initial reference and as a fallback when optical flow has nothing to extrapolate from (e.g., the very start of the session).
- **Added refinement:** for sessions with largely stable lighting, periodically **refresh the plate** during natural wide-shot/silence moments (every few minutes) rather than relying on a single scan from time zero or on optical flow alone for the entire session.

### Risk 2 — Multi-lens auto-switching & AR/4K hardware concurrency

- **The fault:** Phones auto-switch physical lenses based on distance/lighting; overriding this to lock the main lens solves quality but hard-caps digital pan-and-scan headroom. Separately, running an AR session (ARKit/ARCore) concurrently with high-bitrate 4K capture on one lens risks frame-dropping.
- **The mitigation:** Lock an explicit high-resolution format (e.g., 4K60), fixed focus, fixed white balance, and disable automatic lens switching entirely for the recording session (Phase 1.4). Enforce strict distance/spacing boundaries at the guided seating check to compensate for the reduced headroom (Phase 1.3). Keep the AR session scoped to **setup only**, never running concurrently with 4K recording (Phase 0.5) — this removes the resource conflict by construction rather than trying to manage it at runtime.

### Risk 3 — A/V drift & diarization-driven timing delay

- **The fault:** ASR timestamps operate on 200–500ms contextual windows; using them to trigger visual framing cuts makes cuts feel delayed relative to when someone actually starts speaking.
- **The mitigation:** Split the pipeline into a fast timing track (VAD + acoustic onset detection, Phase 2.1) that drives *when* a cut happens, and a slow identity track (ASR + diarization, Phase 2.2) that drives *who* is on screen and produces the transcript — never used for cut timing.
- **Added refinement:** pair the fast VAD trigger with a **minimum-hold/debounce window (~400ms)** on the framing engine (Phase 2.3) so brief interjections, laughs, or breaths don't cause rapid whiplash cuts.

### Risk 4 — Voice enrollment bleed & cross-talk misattribution

- **The fault:** In untreated rooms or with mic bleed, a loud speaker's voice leaking into a soft speaker's mic can trick diarization into cutting to the wrong person.
- **The mitigation:** Fuse visual active-speaker confidence (lip-tracking) with audio voiceprint embeddings to resolve ambiguity during high-bleed or interruption moments (Phase 2.1).
- **Added refinement:** during segments flagged as high-bleed, give the **visual confidence signal veto power** over the audio-only diarization result, rather than simply averaging the two — an averaged signal can still be dragged the wrong way by a dominant loud voice.

---

## Full Dependency Graph

```
Phase 0 (Calibration + Room Scan, AR session scoped to setup only — Risk 2)
   ├──> Phase 1.3 (Seating check — strict boundary, needs scale factor — Risk 2)
   ├──> Phase 1.4 (Recording — locked main lens/format — Risk 2)
   └──> Phase 2.3 renderer (Background plates as fallback/reference — Risk 1)

Phase 1.2 (Voice enrollment) ──> Phase 2.2 (Diarization)

Phase 2.1 — Fast timing track (VAD + acoustic onset + visual confidence — Risk 3, Risk 4)
   └──> Phase 2.3 Framing decision engine (cut timing + debounce)

Phase 2.2 — Slow identity track (Diarization + ASR + face tracking)
   └──> Phase 2.3 Framing decision engine (who's on screen + transcript for Phase 3)

Phase 2.3 Framing engine ──> Phase 2.3 Crop + dynamic edge-fill renderer (Risk 1) ──> Phase 2.4 Audio cleanup

Phase 2 outputs
   └──> Phase 3 (Captions, trimming, highlights, thumbnails)
   └──> Phase 4 (Feedback loop — needs a live framing engine to correct)

Phase 4 ──> improves Phase 2.3's framing engine over time

Phase 5 (Polish/scale) ──> builds on all of the above being stable
```

---

## Suggested Build Order

1. **Phase 0 + 1** — capture + calibration must be rock solid; everything depends on it. Build the locked-format capture and strict seating boundary (Risk 2) as part of this step, not as a later patch — retrofitting a hard gate after users are already recording badly is far more painful.
2. **Phase 2 core** — build the **fast timing track first** (Phase 2.1: VAD + onset + visual confidence, addressing Risk 3/Risk 4), then the slow identity track (Phase 2.2: diarization/ASR), then the framing engine (Phase 2.3) that consumes both. Getting the timing track right early avoids building the whole framing engine on the wrong trigger signal and having to rework it later.
3. **Phase 2.3 renderer** — start with static Phase 0 plates for edge-fill to get an end-to-end pipeline working fast, then upgrade to optical-flow/dynamic fill (Risk 1) once the core cut logic is validated — "ship the simple version first, harden it once the core value is proven."
4. **Phase 3** — captions + filler trimming (cheap, reuses Phase 2 tech).
5. **Phase 3** — highlight clips (higher effort, high visible payoff).
6. **Phase 4** — learning loop, only once real usage/correction data exists.
7. **Phase 5** — on-device optimization and branding polish, once product-market fit is validated.
