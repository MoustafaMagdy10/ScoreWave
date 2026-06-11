"""
Eastern pipeline API router — complete multi-section maqam-aware transcription.

Endpoints:
  POST /api/eastern/pipeline/analyze      Run the full pipeline
  GET  /api/eastern/pipeline/musicxml/{fn} Download MusicXML result
  GET  /api/eastern/pipeline/midi/{fn}    Download MIDI result
  GET  /api/eastern/pipeline/json/{fn}    Download JSON analysis
  GET  /api/eastern/pipeline/health       Health check
"""

import asyncio
import functools
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from models.schema import EasternPipelineResponse
from services.eastern_pipeline_service import run_eastern_pipeline
from shared.logger import logger
from utils.file_handler import MAX_UPLOAD_BYTES, validate_audio_extension


router = APIRouter(prefix="/eastern", tags=["Eastern Pipeline"])

PIPELINE_OUTPUT_DIR = "tmp/pipeline"


def convert_numpy_types(obj: Any) -> Any:
    """Convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(v) for v in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class EasternPipelineResponseModel(BaseModel):
    """Response model for the eastern pipeline endpoint."""

    job_id: str
    sections: list
    musicxml_url: Optional[str] = None
    midi_url: Optional[str] = None
    json_url: Optional[str] = None
    total_duration_s: float


@router.post("/pipeline/analyze", response_model=EasternPipelineResponseModel)
async def eastern_pipeline_analyze(file: UploadFile = File(...)):
    """
    🎵 **Complete Eastern Music Transcription Pipeline**

    Upload audio and get back section-by-section maqam analysis with
    MusicXML sheet music containing quarter-tone accidentals and
    rehearsal marks at section boundaries.

    Pipeline stages:
    1. Demucs separation → vocals stem
    2. CREPE pitch extraction (100 frames/sec)
    3. Frame-to-note segmentation
    4. Multi-cue section detection
    5. Per-section maqam + tonic + tempo analysis
    6. Adjacent section merging
    7. MusicXML + MIDI export
    """
    job_id = str(uuid.uuid4())[:8]

    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    logger.info(f"Eastern pipeline request (job: {job_id}): {file.filename}")

    try:
        loop = asyncio.get_event_loop()
        result: EasternPipelineResponse = await loop.run_in_executor(
            None,
            functools.partial(run_eastern_pipeline, audio_bytes, job_id),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Build download URLs
    musicxml_url = None
    midi_url = None
    json_url = None

    if result.musicxml_filename:
        musicxml_url = f"/api/eastern/pipeline/musicxml/{result.musicxml_filename}"
    if result.midi_filename:
        midi_url = f"/api/eastern/pipeline/midi/{result.midi_filename}"

    # Save JSON analysis
    json_filename = f"eastern_{job_id}.json"
    json_path = Path(PIPELINE_OUTPUT_DIR) / json_filename
    json_path.parent.mkdir(parents=True, exist_ok=True)

    json_data = convert_numpy_types(result.model_dump())
    json_data["job_id"] = job_id
    json_data["timestamp"] = str(datetime.now())

    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)

    json_url = f"/api/eastern/pipeline/json/{json_filename}"

    return EasternPipelineResponseModel(
        job_id=job_id,
        sections=[s.model_dump() for s in result.sections],
        musicxml_url=musicxml_url,
        midi_url=midi_url,
        json_url=json_url,
        total_duration_s=result.total_duration_s,
    )


@router.get("/pipeline/musicxml/{filename}")
def download_eastern_musicxml(filename: str):
    """📄 Download MusicXML sheet music from eastern pipeline."""
    path = Path(PIPELINE_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"MusicXML file '{filename}' not found.",
        )
    return FileResponse(
        path=str(path),
        media_type="application/vnd.recordare.musicxml+xml",
        filename=filename,
    )


@router.get("/pipeline/midi/{filename}")
def download_eastern_midi(filename: str):
    """🎹 Download MIDI file from eastern pipeline."""
    path = Path(PIPELINE_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"MIDI file '{filename}' not found.",
        )
    return FileResponse(
        path=str(path),
        media_type="audio/midi",
        filename=filename,
    )


@router.get("/pipeline/json/{filename}")
def download_eastern_json(filename: str):
    """📊 Download JSON analysis from eastern pipeline."""
    path = Path(PIPELINE_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"JSON file '{filename}' not found.",
        )
    return FileResponse(
        path=str(path),
        media_type="application/json",
        filename=filename,
    )


@router.get("/pipeline/health")
def eastern_pipeline_health():
    """🏥 Health check for eastern pipeline."""
    from models.demucs import Demucs
    from models.crepe import Crepe

    demucs = Demucs()
    crepe = Crepe()

    return {
        "status": "healthy",
        "demucs_ready": demucs.health_check(),
        "crepe_ready": crepe.health_check(),
        "features": [
            "note_segmentation",
            "section_detection",
            "maqam_detection",
            "quarter_tone_enrichment",
            "section_merging",
            "musicxml_export",
        ],
    }
