from typing import List, Optional
from pydantic import BaseModel, Field


class StemPaths(BaseModel):
    vocals: str
    no_vocals: str  # bass + drums + other mixed — fed into CREPE next step
    drums: str
    bass: str
    other: str


class SeparationResponse(BaseModel):
    stems: StemPaths


# ── Melody Extraction Schemas ──────────────────────────────────────────────


class MelodyExtractionParams(BaseModel):
    """Parameters for melody extraction and note filtering."""

    melody_only: bool = Field(
        default=False, description="Extract monophonic melody (1 note at a time)"
    )
    min_amplitude: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum amplitude threshold (0.0-1.0)"
    )
    polyphony_limit: int = Field(
        default=1, ge=1, description="Maximum simultaneous notes (1 = monophonic)"
    )
    min_note_duration: float = Field(
        default=0.1, ge=0.01, description="Minimum note duration in seconds"
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


# ── Eastern Pipeline Schemas ─────────────────────────────────────────────


class NoteEvent(BaseModel):
    """A single note event with microtonal information."""

    start_time_s: float
    duration_s: float
    pitch: int
    midi_continuous: float
    cents_dev: int
    is_quarter: bool
    frequency: float
    amplitude: float


class SectionBoundary(BaseModel):
    """A detected section boundary in time."""

    start_time: float
    end_time: float


class SectionAnalysis(BaseModel):
    """Analysis of a single section including maqam, tonic, tempo, and notes."""

    label: str
    start_time: float
    end_time: float
    maqam: str
    tonic: int
    confidence: float
    bpm: float
    notes: List[NoteEvent]


class EasternPipelineResponse(BaseModel):
    """Response from the complete eastern music pipeline."""

    sections: List[SectionAnalysis]
    musicxml_filename: Optional[str]
    midi_filename: Optional[str]
    total_duration_s: float
