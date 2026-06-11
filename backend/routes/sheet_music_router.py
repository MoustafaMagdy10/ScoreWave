"""
Sheet music router for MusicXML generation and download.

Provides endpoints for converting transcribed melodies to proper
sheet music notation in MusicXML format.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


router = APIRouter()

# Output directory for sheet music files
SHEET_OUTPUT_DIR = "tmp/sheets"


# ── Response Models ─────────────────────────────────────────────────────────


class SheetMusicMetadata(BaseModel):
    """Metadata about generated sheet music."""

    original_note_count: int
    final_note_count: int
    rest_count: int
    dynamics_added: int
    key_signature: str
    key_confidence: float
    tempo_bpm: float
    time_signature: str
    duration_beats: float
    duration_measures: float


class SheetMusicResponse(BaseModel):
    """Response from sheet music generation."""

    job_id: str
    musicxml_url: str
    midi_url: str
    metadata: SheetMusicMetadata


# ── Download Endpoints ──────────────────────────────────────────────────────


@router.get("/sheets/musicxml/{filename}")
def download_musicxml(filename: str):
    """
    📄 **Download MusicXML sheet music file**

    Downloads the generated MusicXML file which can be opened in:
    - MuseScore (free)
    - Finale
    - Sibelius
    - Dorico
    - Any notation software supporting MusicXML
    """
    path = Path(SHEET_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"MusicXML file '{filename}' not found. Run the pipeline first.",
        )

    return FileResponse(
        path=str(path),
        media_type="application/vnd.recordare.musicxml+xml",
        filename=filename,
    )


@router.get("/sheets/midi/{filename}")
def download_sheet_midi(filename: str):
    """
    🎹 **Download notation-based MIDI file**

    Downloads a MIDI file generated from the notation score,
    with properly quantized timing and dynamics.
    """
    path = Path(SHEET_OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"MIDI file '{filename}' not found."
        )

    return FileResponse(
        path=str(path),
        media_type="audio/midi",
        filename=filename,
    )


# ── Health Check ────────────────────────────────────────────────────────────


@router.get("/health/sheets")
def sheets_health_check():
    """🏥 Health check for sheet music generation."""
    try:
        from music21 import stream, note

        # Quick test
        s = stream.Stream()
        n = note.Note("C4")
        s.append(n)

        return {
            "status": "healthy",
            "music21": "available",
            "musicxml_export": "available",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
