# ScoreWave 🎼

ScoreWave is an experimental backend service for converting audio recordings into **sheet music** using AI.

The project aims to build a full pipeline that:

1. Separates instruments from an audio track
2. Transcribes notes
3. Generates sheet music notation

Currently the backend API is implemented using FastAPI and supports **audio source separation using Demucs**.

---

# Current Status

The project is in **early development**.

Implemented so far:

* FastAPI backend
* Demucs integration
* Audio upload endpoint
* Instrument separation service
* Health check for the Demucs model

Planned next steps:

* Audio → MIDI transcription
* MusicXML generation
* Sheet music viewer
* Async processing pipeline

---

# Architecture (Planned)

```text
Audio Input
     ↓
Demucs (instrument separation)
     ↓
Transcription Model
     ↓
music21 Processing
     ↓
MusicXML / MIDI
     ↓
Sheet Music Viewer
```

---

# Tech Stack

## Backend

* Python
* FastAPI
* Demucs
* Librosa (planned)
* music21 (planned)

## Frontend (planned)

* React
* OpenSheetMusicDisplay
* Tone.js

---

# Project Structure

```
backend/
│
├── app/
│   ├── api/
│   │   └── routes.py
│   │
│   ├── models/
│   │   └── demucs_model.py
│   │
│   ├── services/
│   │   └── demucs_service.py
│   │
│   ├── pipeline/
│   │   └── audio_pipeline.py
│   │
│   └── main.py
```

---

# Running the Project

### Clone the repository

```
git clone https://github.com/yourusername/scoreforge.git
cd scoreforge
```

---

### Create a virtual environment

```
python -m venv venv
source venv/bin/activate
```

Windows:

```
venv\Scripts\activate
```

---

### Install dependencies

```
pip install -r requirements.txt
```

---

### Run the server

```
uvicorn app.main:app --reload
```

Server will run at:

```
http://localhost:8000
```

---

# API Endpoints

### Health Check

```
GET /health
```

### Demucs Health

```
GET /health/demucs
```

### Separate Audio

```
POST /separate
```

Uploads an audio file and returns separated stems.

---

# Roadmap

Phase 1

* Demucs integration
* Backend API

Phase 2

* Audio → MIDI transcription
* MusicXML generation

Phase 3

* Sheet music viewer
* Downloadable scores

---

# License

MIT License
