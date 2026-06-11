from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from utils.file_handler import validate_audio_extension, MAX_UPLOAD_BYTES
from services.crepe_service import extract_pitch

router = APIRouter()


# ── Response schema ────────────────────────────────────────────────────────


class PitchContour(BaseModel):
    time: list[float]  # seconds for each kept frame
    frequency: list[float]  # Hz per frame
    confidence: list[float]  # 0–1 per frame
    note: list[str]  # e.g. ["C4", "D4", ...]
    duration_s: float  # total audio duration
    frames_total: int  # frames before confidence filter
    frames_kept: int  # frames after confidence filter


# ── Endpoint ───────────────────────────────────────────────────────────────


@router.post("/pitch", response_model=PitchContour)
async def extract_pitch_route(
    file: UploadFile = File(...),
    confidence_threshold: float = Query(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Discard frames below this confidence (0–1). Higher = stricter.",
    ),
    step_size_ms: int = Query(
        default=10,
        ge=5,
        le=50,
        description="Time resolution in ms between frames. Lower = more detail, slower.",
    ),
):
    """
    Step 2 — Extract the dominant pitch contour from a stem using CREPE.

    Feed this the `no_vocals` stem produced by Demucs.
    Returns a frame-by-frame pitch contour the Basic Pitch step will use next.
    """
    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audio_bytes = await file.read()

    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB limit.")

    try:
        result = extract_pitch(
            audio_bytes,
            confidence_threshold=confidence_threshold,
            step_size_ms=step_size_ms,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return PitchContour(**result)
