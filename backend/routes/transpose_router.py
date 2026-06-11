"""
API routes for note transposition.
"""

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.transpose_service import transpose_notes, get_available_keys

router = APIRouter()


# ── Request/Response Schemas ────────────────────────────────────────────────


class TransposeRequest(BaseModel):
    """Request body for transposing notes."""

    notes: List[Dict[str, Any]] = Field(
        ..., description="List of note objects with 'pitch' field (MIDI note number)"
    )
    semitones: Optional[int] = Field(
        default=None,
        description="Number of semitones to shift (positive = up, negative = down)",
    )
    from_key: Optional[str] = Field(
        default=None, description="Source key (e.g., 'G major', 'A minor')"
    )
    to_key: Optional[str] = Field(
        default=None, description="Target key (e.g., 'C major', 'E minor')"
    )


class TransposeResponse(BaseModel):
    """Response containing transposed notes."""

    notes: List[Dict[str, Any]]
    semitones_applied: int
    note_count: int


class AvailableKeysResponse(BaseModel):
    """Response containing available keys for transposition."""

    keys: List[str]


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/transpose", response_model=TransposeResponse)
async def transpose_route(request: TransposeRequest):
    """
    Transpose notes by semitones or from one key to another.

    **Options:**
    - Provide `semitones` to shift by a fixed interval
    - Provide `from_key` and `to_key` to transpose between keys
    - If both are provided, key-based transposition takes precedence

    **Examples:**
    - Transpose up a perfect fifth: `semitones: 7`
    - Transpose from G major to C major: `from_key: "G major", to_key: "C major"`
    """
    if not request.notes:
        raise HTTPException(status_code=400, detail="Notes list cannot be empty")

    # Validate that notes have pitch field
    for i, note in enumerate(request.notes):
        if "pitch" not in note:
            raise HTTPException(
                status_code=400, detail=f"Note at index {i} missing 'pitch' field"
            )

    # Determine semitones to apply
    semitones = request.semitones or 0

    try:
        transposed = transpose_notes(
            notes=request.notes,
            semitones=semitones,
            from_key=request.from_key,
            to_key=request.to_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Calculate actual semitones applied (for key-based transposition)
    if request.from_key and request.to_key and transposed and request.notes:
        semitones = transposed[0]["pitch"] - request.notes[0]["pitch"]

    return TransposeResponse(
        notes=transposed,
        semitones_applied=semitones,
        note_count=len(transposed),
    )


@router.get("/transpose/keys", response_model=AvailableKeysResponse)
async def get_keys_route():
    """
    Get list of available keys for transposition.

    Returns major and minor keys in circle-of-fifths order.
    """
    return AvailableKeysResponse(keys=get_available_keys())
