"""
Pipeline router for complete audio-to-melody workflow.

This module provides a single endpoint that orchestrates the complete pipeline:
1. Demucs separation (vocals, drums, bass, other)
2. Transcribe vocals and instruments separately
3. Vocal-guided melody analysis
4. Return simple, melody-focused MIDI
"""

import uuid
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from shared.logger import logger
from utils.file_handler import validate_audio_extension, MAX_UPLOAD_BYTES
from services.demucs_service import separate_audio
from services.melody_analysis_service import (
    analyze_and_extract_melody,
    notes_to_midi,
    enrich_notes_with_metadata
)


router = APIRouter()


# Output directories
STEMS_DIR = "tmp/stems"
PIPELINE_OUTPUT_DIR = "tmp/pipeline"


# ── Response Schemas ────────────────────────────────────────────────────────

class PipelineStats(BaseModel):
    """Statistics from melody extraction pipeline."""
    original_count: int
    after_range_filter: int
    after_melodic_filter: int
    after_pattern_filter: int
    final_count: int
    reduction_pct: float
    vocal_guided: bool
    vocal_note_count: int


class PipelineResponse(BaseModel):
    """Response from the complete pipeline."""
    job_id: str
    melody_midi_url: str
    melody_json_url: str
    note_count: int
    duration_s: float
    tempo_bpm: Optional[float]
    stats: PipelineStats
    stems: dict


# ── Pipeline Endpoint ───────────────────────────────────────────────────────

@router.post("/pipeline", response_model=PipelineResponse)
async def run_melody_pipeline(
    file: UploadFile = File(...),
):
    """
    🎵 **Complete Audio-to-Melody Pipeline** (Auto-configured for best results)
    
    This endpoint automatically:
    
    1. **Separates audio** using Demucs (vocals, drums, bass, other)
    2. **Transcribes vocals** - Extracts sung melody as reference
    3. **Transcribes instruments** - Extracts all instrumental notes  
    4. **Intelligently filters** - Removes ONLY accompaniment, keeps ALL melody
    5. **Detects tempo** - Automatically determines BPM
    
    **Result:** Clean, accurate MIDI suitable for sheet music (~150-600 notes depending on song complexity).
    
    **No configuration needed!** Just upload audio and get good sheet music MIDI.
    
    **Best for:**
    - Creating accurate sheet music from piano tutorials
    - Extracting main melodic lines
    - Learning songs with proper note timing
    - Getting playable MIDI from any song
    
    **Processing time:** 1-3 minutes for typical songs
    """
    # Validate file
    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    audio_bytes = await file.read()
    
    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")
    
    job_id = str(uuid.uuid4())[:8]
    
    logger.info(f"Starting melody pipeline (job: {job_id})...")
    
    # ── Step 1: Separate Audio ──────────────────────────────────────────────
    try:
        logger.info("Step 1/4: Separating audio with Demucs...")
        stems = separate_audio(audio_bytes, STEMS_DIR)
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Audio separation failed: {str(e)}"
        )
    
    # ── Step 2: Load Stems ──────────────────────────────────────────────────
    vocals_path = Path(stems['vocals'])
    other_path = Path(stems['other'])  # or no_vocals
    
    if not vocals_path.exists() or not other_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Failed to load separated stems"
        )
    
    vocals_audio = vocals_path.read_bytes()
    instruments_audio = other_path.read_bytes()
    
    # ── Step 3: Analyze and Extract Melody ──────────────────────────────────
    try:
        logger.info("Step 2/4: Transcribing vocals...")
        logger.info("Step 3/4: Transcribing instruments...")
        logger.info("Step 4/4: Extracting melody...")
        
        # Always keep_all_melody=True for best results (auto-configured)
        result = analyze_and_extract_melody(
            vocals_audio,
            instruments_audio,
            keep_all_melody=True  # Smart default: keep all melody notes
        )
    except Exception as e:
        logger.error(f"Melody analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Melody analysis failed: {str(e)}"
        )
    
    melody_notes = result['melody_notes']
    stats = result['stats']
    tempo_bpm = result.get('tempo_bpm')
    
    # ── Step 4: Save Outputs ────────────────────────────────────────────────
    output_dir = Path(PIPELINE_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save MIDI
    midi_filename = f"melody_{job_id}.mid"
    midi_path = output_dir / midi_filename
    notes_to_midi(melody_notes, str(midi_path))
    
    # Save JSON with enriched metadata
    json_filename = f"melody_{job_id}.json"
    json_path = output_dir / json_filename
    
    enriched_notes = enrich_notes_with_metadata(melody_notes)
    duration_s = enriched_notes[-1]['end_time_s'] if enriched_notes else 0.0
    
    with open(json_path, 'w') as f:
        json.dump({
            "job_id": job_id,
            "note_count": len(enriched_notes),
            "duration_s": round(duration_s, 2),
            "tempo_bpm": tempo_bpm,
            "notes": enriched_notes,
            "stats": stats,
        }, f, indent=2)
    
    logger.info(f"Pipeline complete (job: {job_id})")
    
    # ── Build Response ──────────────────────────────────────────────────────
    return PipelineResponse(
        job_id=job_id,
        melody_midi_url=f"/api/pipeline/midi/{midi_filename}",
        melody_json_url=f"/api/pipeline/json/{json_filename}",
        note_count=len(melody_notes),
        duration_s=round(duration_s, 2),
        tempo_bpm=tempo_bpm,
        stats=PipelineStats(**stats),
        stems={
            "vocals": f"/api/stems/{Path(stems['vocals']).name}",
            "other": f"/api/stems/{Path(stems['other']).name}",
        }
    )


# ── Download Endpoints ──────────────────────────────────────────────────────

@router.get("/pipeline/midi/{filename}")
def download_pipeline_midi(filename: str):
    """Download a melody MIDI file from pipeline."""
    path = Path(PIPELINE_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"MIDI file '{filename}' not found. Run POST /api/pipeline first."
        )
    return FileResponse(
        path=str(path),
        media_type="audio/midi",
        filename=filename,
    )


@router.get("/pipeline/json/{filename}")
def download_pipeline_json(filename: str):
    """Download melody JSON from pipeline."""
    path = Path(PIPELINE_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"JSON file '{filename}' not found. Run POST /api/pipeline first."
        )
    return FileResponse(
        path=str(path),
        media_type="application/json",
        filename=filename,
    )


@router.get("/health/pipeline")
def health_check():
    """Health check for pipeline endpoint."""
    from models.demucs import Demucs
    from models.basic_pitch import BasicPitch
    
    demucs = Demucs()
    bp = BasicPitch()
    
    return {
        "status": "ok" if (demucs.health_check() and bp.health_check()) else "error",
        "demucs_ready": demucs.health_check(),
        "basic_pitch_ready": bp.health_check(),
    }
