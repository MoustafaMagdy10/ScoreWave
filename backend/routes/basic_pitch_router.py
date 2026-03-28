from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from utils.file_handler import validate_audio_extension, MAX_UPLOAD_BYTES
from services.basic_pitch_service import transcribe_to_midi
from models.schema import TranscriptionResponse, MelodyStats

router = APIRouter()


# Where Basic Pitch writes transcriptions
TRANSCRIPTIONS_DIR = "tmp/transcriptions"


# ── Endpoints ───────────────────────────────────────────────────────────

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_route(
    file: UploadFile = File(...),
    melody_only: bool = Query(
        default=False,
        description="Extract monophonic melody (1 note at a time) - recommended for sheet music"
    ),
    min_amplitude: float = Query(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum amplitude threshold (0.0-1.0) - filters quiet notes"
    ),
    polyphony_limit: int = Query(
        default=1,
        ge=1,
        description="Maximum simultaneous notes (1=monophonic, higher for chords)"
    ),
    min_note_duration: float = Query(
        default=0.1,
        ge=0.01,
        description="Minimum note duration in seconds - filters very short notes"
    ),
):
    """
    Transcribe audio to MIDI using Basic Pitch with intelligent melody extraction.
    
    **NEW: Melody Extraction** 🎵
    - Filters out background instruments and accompaniment
    - Extracts clean melodic line suitable for sheet music
    - Reduces crowded MIDI files to readable notation
    
    **Recommended for sheet music:**
    - `melody_only=true` - Extract single melodic line
    - `min_amplitude=0.6` - Keep only prominent notes
    - `polyphony_limit=1` - One note at a time
    
    **For piano/guitar chords:**
    - `melody_only=false`
    - `polyphony_limit=3-4` - Allow multiple simultaneous notes
    
    **Best stem to use:**
    - For melody: Use **vocals.wav** or **other.wav** (with melody extraction enabled)
    - For full transcription: Use original mixed audio
    """
    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audio_bytes = await file.read()

    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB limit.")

    try:
        result = transcribe_to_midi(
            audio_bytes,
            TRANSCRIPTIONS_DIR,
            melody_only=melody_only,
            min_amplitude=min_amplitude,
            polyphony_limit=polyphony_limit,
            min_note_duration=min_note_duration,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Extract filename from path for URL
    midi_filename = Path(result["midi_path"]).name
    json_filename = Path(result["json_path"]).name
    
    # Build response with melody stats if available
    response = TranscriptionResponse(
        midi_url=f"/api/midi/{midi_filename}",
        json_url=f"/api/notes/{json_filename}",
        note_count=result["note_count"],
        duration_s=result["duration_s"],
        melody_applied=result.get("melody_applied", False),
    )
    
    if "melody_stats" in result:
        response.melody_stats = MelodyStats(**result["melody_stats"])
    
    return response


@router.get("/midi/{midi_filename}")
def download_midi(midi_filename: str):
    """Download a transcribed MIDI file."""
    path = Path(TRANSCRIPTIONS_DIR) / midi_filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"MIDI file '{midi_filename}' not found. Run POST /api/transcribe first."
        )
    return FileResponse(
        path=str(path),
        media_type="audio/midi",
        filename=midi_filename,
    )


@router.get("/notes/{json_filename}")
def get_notes(json_filename: str):
    """Get note events as JSON."""
    path = Path(TRANSCRIPTIONS_DIR) / json_filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Notes file '{json_filename}' not found. Run POST /api/transcribe first."
        )
    return FileResponse(
        path=str(path),
        media_type="application/json",
        filename=json_filename,
    )


@router.get("/health/basic-pitch")
def health_check():
    """Health check for Basic Pitch model."""
    from models.basic_pitch import BasicPitch
    bp = BasicPitch()
    return {"status": "ok" if bp.health_check() else "error"}
