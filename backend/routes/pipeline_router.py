"""
Pipeline router for complete audio-to-melody workflow.

This module provides a single endpoint that orchestrates the complete pipeline:
1. Demucs separation (vocals, drums, bass, other)
2. Transcribe vocals and instruments separately
3. Vocal-guided melody analysis
4. Generate sheet music with MusicXML export
5. Return MIDI, JSON, and MusicXML outputs
"""

import asyncio
import functools
import uuid
import json
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from shared.logger import logger
from utils.file_handler import validate_audio_extension, MAX_UPLOAD_BYTES
from services.demucs_service import separate_audio
from services.melody_analysis_service import (
    analyze_and_extract_melody,
    notes_to_midi,
    enrich_notes_with_metadata,
)
from services.sheet_music_service import generate_sheet_music
from services.progress_service import get_progress_service, ProcessingStage


router = APIRouter()


# Output directories
STEMS_DIR = "tmp/stems"
PIPELINE_OUTPUT_DIR = "tmp/pipeline"
SHEET_OUTPUT_DIR = "tmp/sheets"


def convert_numpy_types(obj: Any) -> Any:
    """Recursively convert numpy types to native Python types for JSON serialization."""
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


class SheetMusicInfo(BaseModel):
    """Sheet music generation info."""

    musicxml_url: str
    sheet_midi_url: str
    key_signature: str
    key_confidence: float
    dynamics_added: int
    rest_count: int


class PipelineResponse(BaseModel):
    """Response from the complete pipeline."""

    job_id: str
    melody_midi_url: str
    melody_json_url: str
    musicxml_url: Optional[str] = None
    note_count: int
    duration_s: float
    tempo_bpm: Optional[float]
    key_signature: Optional[str] = None
    stats: PipelineStats
    sheet_music: Optional[SheetMusicInfo] = None
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

    **Progress tracking:** Use the returned job_id with GET /api/progress/{job_id} for real-time updates.
    """
    # Generate job_id BEFORE processing for progress tracking
    job_id = str(uuid.uuid4())[:8]
    progress_service = get_progress_service()
    progress_service.create_job(job_id)

    # Validate file
    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        progress_service.fail_job(job_id, str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # Update progress: uploading
    progress_service.update_stage(job_id, ProcessingStage.UPLOADING)
    audio_bytes = await file.read()

    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        progress_service.fail_job(job_id, "File exceeds 50 MB limit.")
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    logger.info(f"Starting melody pipeline (job: {job_id})...")

    # ── Step 1: Separate Audio (CPU-bound — run in thread pool) ────────────
    try:
        progress_service.update_stage(job_id, ProcessingStage.SEPARATING)
        logger.info("Step 1/4: Separating audio with Demucs...")
        loop = asyncio.get_event_loop()
        stems = await loop.run_in_executor(
            None, functools.partial(separate_audio, audio_bytes, STEMS_DIR)
        )
    except RuntimeError as e:
        progress_service.fail_job(job_id, f"Audio separation failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Audio separation failed: {str(e)}"
        )

    # ── Step 2: Load Stems ──────────────────────────────────────────────────
    vocals_path = Path(stems["vocals"])
    other_path = Path(stems["other"])  # or no_vocals

    if not vocals_path.exists() or not other_path.exists():
        progress_service.fail_job(job_id, "Failed to load separated stems")
        raise HTTPException(status_code=500, detail="Failed to load separated stems")

    vocals_audio = vocals_path.read_bytes()
    instruments_audio = other_path.read_bytes()

    # ── Step 3: Analyze and Extract Melody ──────────────────────────────────
    try:
        progress_service.update_stage(job_id, ProcessingStage.TRANSCRIBING)
        logger.info("Step 2/4: Transcribing vocals...")
        logger.info("Step 3/4: Transcribing instruments...")

        # Enhanced melody extraction with quantization settings
        quantization_settings = {
            "quantize_level": "sixteenth",  # musical grid level
            "swing_feel": 0.0,  # 0.0 = straight, 0.2 = moderate swing
            "humanize_amount": 0.01,  # timing variation
            "remove_grace_notes": True,  # filter ornamental notes
            "velocity_smoothing": True,  # smooth velocity changes
            "merge_overlaps": True,  # merge overlapping notes
        }

        progress_service.update_stage(job_id, ProcessingStage.ANALYZING)
        logger.info("Step 4/4: Extracting melody...")

        result = await loop.run_in_executor(
            None,
            functools.partial(
                analyze_and_extract_melody,
                vocals_audio,
                instruments_audio,
                keep_all_melody=True,
                quantization_settings=quantization_settings,
            ),
        )
    except Exception as e:
        logger.error(f"Melody analysis failed: {e}")
        progress_service.fail_job(job_id, f"Melody analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Melody analysis failed: {str(e)}")

    melody_notes = result["melody_notes"]
    stats = result["stats"]
    tempo_bpm = result.get("tempo_bpm", 120.0)
    tempo_info = result.get("tempo_info", {})

    # ── Step 4: Save Outputs ────────────────────────────────────────────────
    output_dir = Path(PIPELINE_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save enhanced MIDI with tempo information
    midi_filename = f"melody_{job_id}.mid"
    midi_path = output_dir / midi_filename
    try:
        from services.melody_analysis_service import (
            notes_to_midi as enhanced_notes_to_midi,
        )

        enhanced_notes_to_midi(melody_notes, str(midi_path), tempo_bpm)
        logger.info(f"Enhanced MIDI saved with tempo {tempo_bpm:.1f} BPM")
    except ImportError:
        # Fallback to basic version
        notes_to_midi(melody_notes, str(midi_path))
        logger.warning("Using basic MIDI export (enhanced version not available)")

    # Save enhanced JSON with comprehensive metadata
    json_filename = f"melody_{job_id}.json"
    json_path = output_dir / json_filename

    try:
        from services.melody_analysis_service import (
            enrich_notes_with_metadata as enhanced_enrich,
        )

        enriched_notes = enhanced_enrich(
            melody_notes,
            {
                "tempo_bpm": tempo_bpm,
                "tempo_info": tempo_info,
                "quantization_settings": result.get("quantization_settings", {}),
            },
        )
        logger.info("Using enhanced note enrichment with tempo metadata")
    except ImportError:
        # Fallback to basic enrichment
        enriched_notes = enrich_notes_with_metadata(melody_notes)
        logger.warning("Using basic note enrichment (enhanced version not available)")

    duration_s = enriched_notes[-1]["end_time_s"] if enriched_notes else 0.0

    enhanced_export = {
        "job_id": job_id,
        "note_count": len(enriched_notes),
        "duration_s": round(float(duration_s), 2),
        "tempo_bpm": float(tempo_bpm) if tempo_bpm else None,
        "tempo_analysis": {
            "bpm": float(tempo_info.get("bpm", tempo_bpm)),
            "confidence": float(tempo_info.get("confidence", 0.5)),
            "time_signature": str(tempo_info.get("time_signature", "4/4")),
            "is_stable": bool(tempo_info.get("is_stable", False)),
        },
        "processing_info": {
            "pipeline_version": "2.0_enhanced",
            "quantization_applied": True,
            "vocal_guidance": bool(stats.get("vocal_guided", False)),
            "quality_score": float(stats.get("final_quality_score", 5.0)),
            "reduction_percentage": float(stats.get("total_reduction_pct", 0.0)),
            "processing_stages": stats.get("processing_stages", []),
        },
        "notes": convert_numpy_types(enriched_notes),
        "stats": convert_numpy_types(stats),
        "timestamp": str(datetime.now()),
    }

    with open(json_path, "w") as f:
        json.dump(enhanced_export, f, indent=2)

    # ── Step 5: Generate Sheet Music (MusicXML) ─────────────────────────────
    sheet_music_info = None
    musicxml_url = None
    key_signature = None

    try:
        progress_service.update_stage(job_id, ProcessingStage.GENERATING)
        logger.info("Step 5/5: Generating sheet music (MusicXML)...")

        sheet_result = await loop.run_in_executor(
            None,
            functools.partial(
                generate_sheet_music,
                notes=melody_notes,
                output_dir=SHEET_OUTPUT_DIR,
                job_id=job_id,
                tempo_bpm=tempo_bpm,
                time_signature=tempo_info.get("time_signature", "4/4"),
                title=file.filename or "Transcribed Melody",
                add_dynamics=True,
                treble_only=True,
            ),
        )

        sheet_metadata = sheet_result["metadata"]
        musicxml_filename = Path(sheet_result["musicxml_path"]).name
        sheet_midi_filename = Path(sheet_result["midi_path"]).name

        musicxml_url = f"/api/sheets/musicxml/{musicxml_filename}"
        key_signature = sheet_metadata["key_signature"]

        sheet_music_info = SheetMusicInfo(
            musicxml_url=musicxml_url,
            sheet_midi_url=f"/api/sheets/midi/{sheet_midi_filename}",
            key_signature=sheet_metadata["key_signature"],
            key_confidence=sheet_metadata["key_confidence"],
            dynamics_added=sheet_metadata["dynamics_added"],
            rest_count=sheet_metadata["rest_count"],
        )

        logger.info(
            f"Sheet music generated: key={key_signature}, "
            f"{sheet_metadata['dynamics_added']} dynamics, "
            f"{sheet_metadata['rest_count']} rests"
        )

    except Exception as e:
        logger.warning(f"Sheet music generation failed (non-critical): {e}")
        # Continue without sheet music - it's not critical

    # Mark job as complete
    progress_service.complete_job(job_id)
    logger.info(f"Pipeline complete (job: {job_id})")

    # ── Build Response ──────────────────────────────────────────────────────
    # Convert stats to native Python types for Pydantic
    clean_stats = convert_numpy_types(stats)

    return PipelineResponse(
        job_id=job_id,
        melody_midi_url=f"/api/pipeline/midi/{midi_filename}",
        melody_json_url=f"/api/pipeline/json/{json_filename}",
        musicxml_url=musicxml_url,
        note_count=len(melody_notes),
        duration_s=round(float(duration_s), 2),
        tempo_bpm=float(tempo_bpm) if tempo_bpm else None,
        key_signature=key_signature,
        stats=PipelineStats(**clean_stats),
        sheet_music=sheet_music_info,
        stems={
            "vocals": f"/api/stems/{Path(stems['vocals']).name}",
            "other": f"/api/stems/{Path(stems['other']).name}",
        },
    )


# ── Download Endpoints ──────────────────────────────────────────────────────


@router.get("/pipeline/midi/{filename}")
def download_pipeline_midi(filename: str):
    """Download a melody MIDI file from pipeline."""
    path = Path(PIPELINE_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"MIDI file '{filename}' not found. Run POST /api/pipeline first.",
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
            detail=f"JSON file '{filename}' not found. Run POST /api/pipeline first.",
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
