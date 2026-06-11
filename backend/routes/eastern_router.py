"""
Eastern music API router — Maqam detection and Arabic music analysis.

Endpoints
---------
GET  /api/eastern/maqamat              List all maqamat (in-memory dict)
GET  /api/eastern/maqam/{name}         Detail for one maqam (in-memory dict)
POST /api/eastern/analyze              Analyze note list for maqam + quarter tones
POST /api/eastern/detect               Audio upload → maqam detection via histogram
GET  /api/eastern/library              Full maqam knowledge base from DB
GET  /api/eastern/library/{id}         Single maqam from DB by numeric ID
GET  /api/eastern/health               Health check
"""

import asyncio
import functools
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from shared.logger import logger
from services.eastern_music_service import (
    MAQAMAT,
    analyze_eastern_music,
    detect_maqam_from_audio,
    get_maqam_db_info,
    get_maqam_info,
    list_maqamat,
)

router = APIRouter(prefix="/eastern", tags=["Eastern Music"])


# ── Request / Response schemas ────────────────────────────────────────────────


class NoteInput(BaseModel):
    """Input note for analysis."""

    pitch: int
    start_time: Optional[float] = None
    duration: Optional[float] = None
    velocity: Optional[int] = None
    frequency_hz: Optional[float] = None


class AnalyzeRequest(BaseModel):
    """Request body for Eastern music analysis."""

    notes: List[NoteInput]


class MaqamInfoResponse(BaseModel):
    """Response for maqam information (in-memory dict)."""

    name: str
    intervals_quarter_tones: List[int]
    notes: List[str]
    has_quarter_tones: bool


class AnalyzeResponse(BaseModel):
    """Response for Eastern music analysis from note list."""

    maqam: str
    tonic: Optional[int] = None
    maqam_confidence: float
    quarter_tone_count: int
    is_eastern: bool
    notes: List[Dict[str, Any]]


class MaqamatListResponse(BaseModel):
    """Response for listing all in-memory maqamat."""

    maqamat: List[MaqamInfoResponse]
    count: int


class DetectResponse(BaseModel):
    """Response from audio-based maqam detection."""

    maqam: str
    confidence: float
    tonic_note: str
    tonic_hz: float
    tonic_cents: float
    peak_cents: List[float]
    essentia_used: bool
    method: str
    db_info: Optional[Dict[str, Any]] = None


class MaqamDBResponse(BaseModel):
    """Full maqam record from the knowledge-base database."""

    id: int
    name_arabic: str
    name_latin: str
    root_note: str
    scale_cents: List[float]
    mood_english: Optional[str]
    mood_arabic: Optional[str]
    famous_songs: Optional[List[str]]
    jins_structure: Optional[str]
    has_quarter_tones: bool
    confidence_threshold: float


class LibraryResponse(BaseModel):
    """Full maqam knowledge base from DB."""

    maqamat: List[MaqamDBResponse]
    count: int


# ── In-memory endpoints ───────────────────────────────────────────────────────


@router.get("/maqamat", response_model=MaqamatListResponse)
def get_all_maqamat():
    """
    📋 **List all supported maqamat** (in-memory reference data)

    Returns scale intervals in quarter tones (24-TET) and note names
    with quarter-tone notation for each maqam.
    """
    logger.info("Listing all maqamat")
    maqamat = list_maqamat()
    return MaqamatListResponse(
        maqamat=[MaqamInfoResponse(**m) for m in maqamat],
        count=len(maqamat),
    )


@router.get("/maqam/{name}", response_model=MaqamInfoResponse)
def get_maqam(name: str):
    """
    🎵 **Get details about a specific maqam** (in-memory)

    - **name**: Maqam name (e.g. Rast, Bayati, Hijaz, Saba) — case-insensitive.
    """
    logger.info(f"Getting maqam info: {name}")
    name_lookup = {k.lower(): k for k in MAQAMAT.keys()}
    actual_name = name_lookup.get(name.lower())

    if not actual_name:
        raise HTTPException(
            status_code=404,
            detail=f"Maqam '{name}' not found. Available: {list(MAQAMAT.keys())}",
        )

    info = get_maqam_info(actual_name)
    if "error" in info:
        raise HTTPException(status_code=404, detail=info["error"])

    return MaqamInfoResponse(**info)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_notes(request: AnalyzeRequest):
    """
    🎼 **Analyze note list for Eastern music characteristics**

    Accepts a list of MIDI notes and returns:
    - **Maqam** detected (with confidence)
    - **Quarter-tone** count (microtonal pitches)
    - Whether the music is likely Eastern/Arabic

    Optionally include ``frequency_hz`` per note for accurate quarter-tone
    detection (centroid deviation from equal temperament).
    """
    if not request.notes:
        raise HTTPException(status_code=400, detail="No notes provided for analysis")

    logger.info(f"Analyzing {len(request.notes)} notes for Eastern characteristics")
    notes_data = [n.model_dump() for n in request.notes]
    result = analyze_eastern_music(notes_data)

    return AnalyzeResponse(
        maqam=result["maqam"],
        tonic=result.get("tonic"),
        maqam_confidence=result["maqam_confidence"],
        quarter_tone_count=result["quarter_tone_count"],
        is_eastern=result["is_eastern"],
        notes=result["notes"],
    )


# ── Audio-based detection ─────────────────────────────────────────────────────


@router.post("/detect", response_model=DetectResponse)
async def detect_maqam_endpoint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    🎧 **Detect maqam from an uploaded audio file**

    Uploads an audio file (MP3, WAV, FLAC, M4A) and performs:
    1. F0 extraction via **Essentia PitchMelodia** (falls back to librosa pyin)
    2. 240-bin **cents histogram** construction (5 cents/bin)
    3. **Tonic detection** from the dominant histogram peak
    4. **Maqam matching** via Jaccard similarity against the 8 canonical patterns
    5. DB lookup for full cultural metadata (names, mood, famous songs)

    Returns the detected maqam, tonic note + Hz, confidence, and rich DB info.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    logger.info(f"Maqam detection request: {file.filename} ({len(audio_bytes)} bytes)")

    # Run CPU-bound detection in thread pool (don't block event loop)
    loop = asyncio.get_event_loop()
    detection = await loop.run_in_executor(
        None, functools.partial(detect_maqam_from_audio, audio_bytes)
    )

    # Enrich with DB record
    db_info: Optional[Dict[str, Any]] = None
    if detection["maqam"] != "Unknown":
        db_info = await get_maqam_db_info(detection["maqam"], db)

    return DetectResponse(
        maqam=detection["maqam"],
        confidence=detection["confidence"],
        tonic_note=detection["tonic_note"],
        tonic_hz=detection["tonic_hz"],
        tonic_cents=detection["tonic_cents"],
        peak_cents=detection["peak_cents"],
        essentia_used=detection["essentia_used"],
        method=detection["method"],
        db_info=db_info,
    )


# ── Knowledge-base (DB) endpoints ─────────────────────────────────────────────


@router.get("/library", response_model=LibraryResponse)
async def get_maqam_library(db: AsyncSession = Depends(get_db)):
    """
    📚 **Full maqam knowledge base**

    Returns all maqamat stored in the database with complete cultural and
    technical metadata:
    - Arabic name and Latin transliteration
    - Root note and cents-based scale definition (24-TET)
    - Emotional mood (Arabic + English)
    - Famous songs in this maqam
    - Jins (tetrachord) structure
    - Quarter-tone flag and confidence threshold
    """
    from models.maqam import Maqam

    result = await db.execute(select(Maqam).order_by(Maqam.name_latin))
    maqamat = result.scalars().all()

    if not maqamat:
        logger.warning("Maqam library is empty — run: python -m scripts.seed_maqamat")

    return LibraryResponse(
        maqamat=[MaqamDBResponse(**m.to_dict()) for m in maqamat],
        count=len(maqamat),
    )


@router.get("/library/{maqam_id}", response_model=MaqamDBResponse)
async def get_maqam_by_id(maqam_id: int, db: AsyncSession = Depends(get_db)):
    """
    📖 **Get a single maqam from the knowledge base by ID**

    - **maqam_id**: Numeric database ID (see `/api/eastern/library` for IDs).
    """
    from models.maqam import Maqam

    result = await db.execute(select(Maqam).where(Maqam.id == maqam_id))
    maqam = result.scalar_one_or_none()

    if not maqam:
        raise HTTPException(
            status_code=404,
            detail=f"Maqam with id={maqam_id} not found",
        )

    return MaqamDBResponse(**maqam.to_dict())


# ── Health check ──────────────────────────────────────────────────────────────


@router.get("/health")
async def eastern_health_check(db: AsyncSession = Depends(get_db)):
    """🏥 Health check for Eastern music analysis service."""
    from models.maqam import Maqam
    from services.pitch_histogram_service import ESSENTIA_AVAILABLE

    result = await db.execute(select(Maqam))
    db_count = len(result.scalars().all())

    return {
        "status": "healthy",
        "service": "eastern_music",
        "maqamat_memory": len(MAQAMAT),
        "maqamat_db": db_count,
        "essentia_available": ESSENTIA_AVAILABLE,
        "features": [
            "maqam_detection_notes",
            "maqam_detection_audio",
            "quarter_tone_analysis",
            "pitch_histogram",
            "maqam_knowledge_base",
        ],
    }
