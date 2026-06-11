"""
Microtonal music analysis router for cultural music support.

This router provides endpoints for analyzing and working with
microtonal music, particularly Middle Eastern maqamat.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

from shared.logger import logger
from utils.microtonal_analysis import (
    analyze_microtonal_content,
    get_maqam_info,
    MAQAMAT_SCALES,
)
from utils.microtonal_midi import (
    create_maqam_midi_template,
    validate_microtonal_support,
)
from utils.file_handler import validate_audio_extension

router = APIRouter(prefix="/api/microtonal", tags=["Microtonal Music"])


# Response models
class MicrotonalAnalysisResponse(BaseModel):
    quarter_tones_detected: bool
    microtonal_ratio: float
    suggested_tuning: str
    maqam_detected: bool
    best_maqam: Optional[str]
    maqam_confidence: float
    cultural_context: Optional[str]


class MaqamInfo(BaseModel):
    name: str
    scale_degrees_cents: List[int]
    has_quarter_tones: bool
    quarter_tone_positions: List[int]


# ── Analysis Endpoints ──────────────────────────────────────────────────────


@router.post("/analyze", response_model=MicrotonalAnalysisResponse)
async def analyze_microtonal_music(file: UploadFile = File(...)):
    """
    🎼 **Analyze audio for microtonal content and maqamat**

    Upload an audio file to detect:
    - Quarter-tone intervals (24-TET vs 12-TET)
    - Arabic maqamat scale patterns
    - Cultural musical context
    - Recommended processing approach

    **Best for:**
    - Middle Eastern, Arabic, Turkish music
    - Persian and Central Asian music
    - Any music with quarter tones or microtones

    **Processing time:** 10-30 seconds depending on audio length
    """
    try:
        validate_audio_extension(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        logger.info(f"Starting microtonal analysis: {file.filename}")

        # Read audio data
        audio_bytes = await file.read()

        # Perform microtonal analysis
        result = analyze_microtonal_content(audio_bytes)

        if not result.get("microtonal_analysis_available", False):
            error_msg = result.get("error", "Analysis failed")
            raise HTTPException(
                status_code=500, detail=f"Microtonal analysis failed: {error_msg}"
            )

        # Extract results
        quarter_tone_analysis = result["quarter_tone_analysis"]
        maqam_analysis = result.get("maqam_analysis")

        # Format response
        response = MicrotonalAnalysisResponse(
            quarter_tones_detected=quarter_tone_analysis["quarter_tones_detected"],
            microtonal_ratio=quarter_tone_analysis["microtonal_ratio"],
            suggested_tuning=quarter_tone_analysis["suggested_tuning"],
            maqam_detected=bool(
                maqam_analysis and maqam_analysis.get("maqam_detected", False)
            ),
            best_maqam=maqam_analysis.get("best_maqam") if maqam_analysis else None,
            maqam_confidence=maqam_analysis.get("confidence", 0.0)
            if maqam_analysis
            else 0.0,
            cultural_context=result["recommended_processing"].get("cultural_context"),
        )

        logger.info(f"Microtonal analysis complete: {response.suggested_tuning}")
        return response

    except Exception as e:
        logger.error(f"Microtonal analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Maqamat Information Endpoints ───────────────────────────────────────────


@router.get("/maqamat")
def list_supported_maqamat():
    """
    📋 **List all supported maqamat scales**

    Returns information about all maqamat that can be detected and analyzed.
    """
    maqamat = []
    for maqam_name in MAQAMAT_SCALES.keys():
        info = get_maqam_info(maqam_name)
        maqamat.append(
            {
                "name": maqam_name,
                "has_quarter_tones": info["has_quarter_tones"],
                "quarter_tone_count": len(info["quarter_tone_positions"]),
                "description": f"{'Quarter-tone' if info['has_quarter_tones'] else 'Diatonic'} maqam",
            }
        )

    return {
        "supported_maqamat": maqamat,
        "total_count": len(maqamat),
        "quarter_tone_maqamat": [m["name"] for m in maqamat if m["has_quarter_tones"]],
    }


@router.get("/maqamat/{maqam_name}", response_model=MaqamInfo)
def get_maqam_details(maqam_name: str):
    """
    🎵 **Get detailed information about a specific maqam**

    Returns scale degrees, quarter-tone positions, and musical characteristics.
    """
    if maqam_name not in MAQAMAT_SCALES:
        raise HTTPException(
            status_code=404,
            detail=f"Maqam '{maqam_name}' not found. Available: {list(MAQAMAT_SCALES.keys())}",
        )

    info = get_maqam_info(maqam_name)

    return MaqamInfo(
        name=info["name"],
        scale_degrees_cents=info["scale_degrees_cents"],
        has_quarter_tones=info["has_quarter_tones"],
        quarter_tone_positions=info["quarter_tone_positions"],
    )


# ── MIDI Template Endpoints ─────────────────────────────────────────────────


@router.get("/maqamat/{maqam_name}/midi")
def generate_maqam_midi_template(maqam_name: str, root_note: str = "C4"):
    """
    🎹 **Generate MIDI template for a maqam scale**

    Creates a MIDI file demonstrating the maqam scale with quarter-tone pitch bends.

    **Parameters:**
    - `maqam_name`: Name of the maqam (e.g., "bayati", "saba", "hijaz")
    - `root_note`: Root note in scientific notation (e.g., "C4", "D4", "F#3")

    **Returns:** Downloadable MIDI file with microtonal pitch bends
    """
    if maqam_name not in MAQAMAT_SCALES:
        raise HTTPException(status_code=404, detail=f"Maqam '{maqam_name}' not found")

    try:
        import librosa

        # Convert root note to MIDI number
        try:
            root_midi = int(librosa.note_to_midi(root_note))
        except Exception:
            root_midi = 60  # Default to C4
            logger.warning(f"Invalid root note '{root_note}', using C4")

        # Generate MIDI template
        filename = f"maqam_{maqam_name}_{root_note.replace('#', 'sharp')}.mid"
        output_path = f"tmp/{filename}"

        create_maqam_midi_template(
            maqam_name=maqam_name,
            root_midi=root_midi,
            output_path=output_path,
            octaves=2,
        )

        logger.info(f"Generated maqam MIDI template: {filename}")

        return FileResponse(
            path=output_path, filename=filename, media_type="audio/midi"
        )

    except Exception as e:
        logger.error(f"MIDI template generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── System Information Endpoints ────────────────────────────────────────────


@router.get("/capabilities")
def get_microtonal_capabilities():
    """
    ⚙️ **Get system microtonal capabilities**

    Returns information about supported features and system status.
    """
    try:
        # Test capabilities
        validation_result = validate_microtonal_support("tmp/capability_test")

        return {
            "microtonal_midi_support": validation_result["microtonal_midi_support"],
            "maqam_template_support": validation_result["maqam_template_support"],
            "quarter_tone_detection": True,
            "supported_maqamat_count": len(MAQAMAT_SCALES),
            "pitch_bend_midi": True,
            "cultural_analysis": True,
            "system_ready": validation_result["validation_passed"],
        }

    except Exception as e:
        logger.error(f"Capability check failed: {e}")
        return {"error": str(e), "system_ready": False}


@router.get("/health")
def microtonal_health_check():
    """🏥 Health check for microtonal analysis system"""
    try:
        # Quick validation
        test_result = validate_microtonal_support("tmp/health_check")

        return {
            "status": "healthy" if test_result["validation_passed"] else "degraded",
            "microtonal_analysis": "available",
            "midi_generation": "available"
            if test_result["microtonal_midi_support"]
            else "unavailable",
            "maqamat_support": f"{len(MAQAMAT_SCALES)} maqamat available",
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
