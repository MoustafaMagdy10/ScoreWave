from typing import Optional
from pydantic import BaseModel, Field


class StemPaths(BaseModel):
    vocals:    str
    no_vocals: str   # bass + drums + other mixed — fed into CREPE next step
    drums:     str
    bass:      str
    other:     str


class SeparationResponse(BaseModel):
    stems: StemPaths


# ── Melody Extraction Schemas ──────────────────────────────────────────────

class MelodyExtractionParams(BaseModel):
    """Parameters for melody extraction and note filtering."""
    melody_only: bool = Field(
        default=False,
        description="Extract monophonic melody (1 note at a time)"
    )
    min_amplitude: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum amplitude threshold (0.0-1.0)"
    )
    polyphony_limit: int = Field(
        default=1,
        ge=1,
        description="Maximum simultaneous notes (1 = monophonic)"
    )
    min_note_duration: float = Field(
        default=0.1,
        ge=0.01,
        description="Minimum note duration in seconds"
    )


class MelodyStats(BaseModel):
    """Statistics comparing original and filtered notes."""
    original_note_count: int
    filtered_note_count: int
    reduction_pct: float
    original_avg_amplitude: float
    filtered_avg_amplitude: float


class TranscriptionResponse(BaseModel):
    """Response for transcription endpoints."""
    midi_url: str
    json_url: str
    note_count: int
    duration_s: float
    melody_applied: bool = False
    melody_stats: Optional[MelodyStats] = None
