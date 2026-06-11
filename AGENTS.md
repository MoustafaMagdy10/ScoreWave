# AGENTS.md - Songify Backend Development Guide

## Overview

Songify is a Python FastAPI backend for converting audio recordings into sheet music using AI. The goal is simple: **take a song as input → output a full music sheet**.

### What This Project Does

The project builds an end-to-end audio-to-sheet-music pipeline:
1. User uploads an audio file (MP3, WAV, FLAC, M4A, etc.)
2. The backend processes it through multiple AI stages
3. The final output is a downloadable MusicXML file
4. A React frontend (planned) displays the sheet music using OSMD (OpenSheetMusicDisplay)

### Module Descriptions

| Module | Status | Purpose |
|--------|--------|---------|
| **Demucs** | ✅ Complete | Audio source separation - splits audio into stems (vocals, drums, bass, other). Uses htdemucs model for high-quality separation. |
| **CREPE** | ✅ Complete | Pitch detection/estimation - analyzes audio and extracts frequency data (Hz) with confidence scores. Used for note prediction. |
| **Basic Pitch** | ✅ Complete | Audio-to-MIDI transcription - converts audio stems to MIDI notes. Built on Basic Pitch from Spotify. Outputs MIDI file + JSON note events. |
| **music21** | ⏳ Planned | Music notation framework - converts MIDI data into musical notation with proper timing, dynamics, and articulation. |
| **MusicXML Export** | ⏳ Planned | Export the notation to MusicXML format for interoperability with music software. |
| **Task Queue** | ⏳ Planned | Celery + Redis for async processing - handles long-running transcription jobs. |
| **React Frontend** | ⏳ Planned | UI for upload, progress tracking, and OSMD-based sheet music viewer. |

### Current State & Progress

**Completed:**
- ✅ FastAPI backend with Demucs integration
- ✅ Audio separation endpoint (`POST /api/separate`)
- ✅ Stem download endpoints (`GET /api/stems/{stem_name}`)
- ✅ CREPE pitch extraction endpoint (`POST /api/pitch`)
- ✅ Basic Pitch transcription endpoint (`POST /api/transcribe`)
- ✅ MIDI and JSON note events download endpoints
- ✅ Health checks for all models (Demucs, CREPE, Basic Pitch)

**In Progress / Planned:**
- ⏳ music21 integration for notation
- ⏳ MusicXML export
- ⏳ Task queue for async processing
- ⏳ React frontend with OSMD viewer

### Planned Architecture

```
User Upload
      ↓
   React (Frontend)
      ↓
  FastAPI (Backend)
      ↓
 Task Queue (Celery + Redis)
      ↓
    Pipeline
      ├── 1) Demucs         (separate stems)
      ├── 2) Basic Pitch    (audio → MIDI)
      ├── 3) music21        (MIDI → notation)
      └── 4) Export         (MusicXML)
                  ↓
        React Viewer (OSMD)
```

**Tech Stack**: Python, FastAPI, Demucs, torchcrepe, Basic Pitch, music21, Pydantic, tqdm, React, OSMD

---

## Build / Run Commands

### Running the Server

```bash
# From backend/ directory
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or directly
python main.py
```

### Installing Dependencies

```bash
pip install -r requirments.txt
```

### Testing

This project uses **pytest**. Install it first:

```bash
pip install pytest pytest-asyncio httpx
```

**Run all tests:**
```bash
pytest
```

**Run a single test file:**
```bash
pytest tests/test_demucs_service.py
```

**Run a single test function:**
```bash
pytest tests/test_demucs_service.py::test_health_check
```

**Run tests matching a pattern:**
```bash
pytest -k "demucs"
```

### Linting

Install **ruff** for linting (recommended for Python):

```bash
pip install ruff
```

**Run linter:**
```bash
ruff check .
```

**Auto-fix issues:**
```bash
ruff check . --fix
```

**Format code:**
```bash
ruff format .
```

### Type Checking

Install and run **mypy**:

```bash
pip install mypy
mypy .
```

---

## Code Style Guidelines

### Imports

Organize imports in three groups with blank lines between (top of file):

```python
# 1. Standard library
import io
import time
import threading
from pathlib import Path

# 2. Third-party packages
import torch
import torchaudio
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from demucs.apply import apply_model

# 3. Local application imports
from models.demucs import Demucs
from services.demucs_service import separate_audio
from shared.logger import logger
from utils.file_handler import validate_audio_extension
```

- Use **relative imports** for local modules (`from models.demucs import Demucs`)
- Avoid wildcard imports (`from x import *`)

### Type Hints

Always use type hints for:
- Function arguments and return types
- Variable annotations
- Class attributes

```python
def separate_audio(audio_bytes: bytes, output_dir: str) -> dict[str, str]:
    ...

class StemPaths(BaseModel):
    vocals: str
    no_vocals: str
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `demucs_service.py` |
| Classes | PascalCase | `class Demucs:` |
| Functions | snake_case | `def separate_audio():` |
| Variables | snake_case | `audio_bytes`, `stem_paths` |
| Constants | UPPER_SNAKE | `MAX_UPLOAD_BYTES`, `CREPE_SR` |
| Private functions | prefix with `_` | `_load_model()` |

### Error Handling

**FastAPI routes**: Use `HTTPException` for user-facing errors:

```python
from fastapi import HTTPException

@router.post("/separate")
async def run_separation(file: UploadFile = File(...)):
    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    try:
        separate_audio(audio_bytes, STEMS_DIR)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Services**: Raise descriptive exceptions with context:

```python
def health_check(self) -> bool:
    if self.model is None:
        return False
    try:
        return sum(1 for _ in self.model.parameters()) > 0
    except Exception:
        return False
```

### Docstrings

Use Google-style docstrings for public functions:

```python
def separate_audio(audio_bytes: bytes, output_dir: str) -> dict[str, str]:
    """
    Separate raw audio bytes into stems using Demucs.

    Args:
        audio_bytes: Raw bytes of the audio file (MP3 / WAV / FLAC / M4A).
        output_dir: Directory where stem WAVs will be written.

    Returns:
        Dict mapping stem name -> absolute path to the written WAV file.

    Raises:
        RuntimeError: If the model is not loaded or separation fails.
    """
```

### Async Patterns

- FastAPI route handlers should be `async def` when performing I/O operations
- Use `await` for async I/O; CPU-bound work runs in threadpool via `run_in_executor`
- For file processing (CPU-bound), keep it sync in service layer:

```python
# Router (async)
@router.post("/separate")
async def run_separation(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    separate_audio(audio_bytes, STEMS_DIR)  # CPU-bound, sync

# Service (sync)
def separate_audio(audio_bytes: bytes, output_dir: str) -> dict[str, str]:
    # Demucs processing here
```

### Pydantic Schemas

Define request/response schemas in `models/schema.py`:

```python
from pydantic import BaseModel

class StemPaths(BaseModel):
    vocals: str
    no_vocals: str
    drums: str
    bass: str
    other: str

class SeparationResponse(BaseModel):
    stems: StemPaths
```

### Logging

Use the centralized logger from `shared/logger.py`:

```python
from shared.logger import logger

logger.info("Starting separation...")
logger.error(f"Failed to load model: {e}")
```

### Progress Bars

Use `tqdm` consistently across all services:

```python
from tqdm import tqdm

def _bar(desc: str, total: int = 1, unit: str = "step") -> tqdm:
    return tqdm(
        total=total,
        desc=f"  {desc}",
        unit=unit,
        ncols=70,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit} [{elapsed}]",
        colour="yellow",
    )
```

---

## Project Structure

```
backend/
├── main.py              # FastAPI app entry point
├── models/              # Data models and schemas
│   ├── demucs.py        # Demucs wrapper class
│   ├── crepe.py         # CREPE wrapper class
│   └── schema.py        # Pydantic schemas
├── routes/              # API route handlers
│   ├── demucs_router.py
│   └── crepe_router.py
├── services/            # Business logic (model loading, processing)
│   ├── demucs_service.py
│   └── crepe_service.py
├── shared/              # Shared utilities
│   └── logger.py
└── utils/               # Helper functions
    └── file_handler.py
```

### Service Layer Patterns

**Model singletons**: Load ML models at module level (lazy loading):

```python
# services/demucs_service.py

_demucs = Demucs(model_name="htdemucs")  # Loaded once on first import

def separate_audio(...):
    model = _demucs.model  # Use the singleton
    ...
```

---

## Agent Rules

### Always Check AGENTS.md Before Coding

Before starting any coding task, agents MUST:
1. Read `AGENTS.md` to understand current conventions
2. Check for any project-specific patterns in existing code
3. Verify tooling commands are up to date

### Update AGENTS.md After Coding

After completing a coding task, agents MUST:
1. Update this file if new patterns or conventions were introduced
2. Add new commands or tooling if added to the project
3. Document any new project-specific guidelines discovered during work

### Pre-commit Checklist

Before marking a task complete:
- [ ] Run `ruff check .` and fix any issues
- [ ] Run `ruff format .` if code was modified
- [ ] Run `mypy .` if adding new code (optional but recommended)
- [ ] Run tests: `pytest`
- [ ] Update AGENTS.md if new patterns were introduced
