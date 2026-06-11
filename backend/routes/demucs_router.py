from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from models.schema import SeparationResponse, StemPaths
from utils.file_handler import validate_audio_extension, MAX_UPLOAD_BYTES
from services.demucs_service import separate_audio

router = APIRouter()

# Where Demucs writes stems — shared with the download endpoints
STEMS_DIR = "tmp/stems"


@router.post("/separate", response_model=SeparationResponse)
async def run_separation(file: UploadFile = File(...)):
    """
    Step 1 — Accept an audio file and return separated stems.

    Reads the uploaded bytes directly into memory and passes them
    to the Demucs service — no intermediate file save needed.
    """
    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audio_bytes = await file.read()

    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="File exceeds the 50 MB upload limit."
        )

    try:
        separate_audio(audio_bytes, STEMS_DIR)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return SeparationResponse(
        stems=StemPaths(
            vocals="/api/stems/vocals",
            no_vocals="/api/stems/no_vocals",
            drums="/api/stems/drums",
            bass="/api/stems/bass",
            other="/api/stems/other",
        )
    )


@router.get("/stems/{stem_name}")
def download_stem(stem_name: str):
    """Download a separated stem WAV. stem_name: vocals | no_vocals | drums | bass | other"""
    valid = {"vocals", "no_vocals", "drums", "bass", "other"}
    if stem_name not in valid:
        raise HTTPException(status_code=400, detail=f"stem_name must be one of {valid}")

    path = Path(STEMS_DIR) / f"{stem_name}.wav"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Stem '{stem_name}' not found. Run POST /api/separate first.",
        )

    return FileResponse(
        path=str(path), media_type="audio/wav", filename=f"{stem_name}.wav"
    )
