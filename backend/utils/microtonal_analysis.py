"""
Microtonal music analysis for quarter-tone and maqamat support.

This module provides detection and analysis of microtonal intervals,
specifically targeting Middle Eastern maqamat and other quarter-tone systems.
"""

import numpy as np
import librosa
from typing import Dict, List, Any, Optional

from shared.logger import logger


# Maqamat scales with quarter-tone intervals (in cents from root)
MAQAMAT_SCALES = {
    "rast": [0, 200, 300, 500, 700, 900, 1000, 1200],  # Major-like
    "bayati": [0, 150, 300, 500, 700, 850, 1000, 1200],  # Minor-like with quarter tones
    "saba": [
        0,
        150,
        250,
        500,
        700,
        850,
        950,
        1200,
    ],  # Distinctive quarter-tone character
    "hijaz": [0, 100, 400, 500, 700, 800, 1100, 1200],  # Spanish/Middle Eastern
    "sikah": [0, 150, 350, 500, 700, 850, 1050, 1200],  # Quarter-tone on 3rd and 7th
    "kurd": [0, 100, 300, 500, 700, 800, 1000, 1200],  # Kurdish scale
    "nahawand": [0, 200, 300, 500, 700, 800, 1000, 1200],  # Natural minor
    "ajam": [0, 200, 400, 500, 700, 900, 1100, 1200],  # Major scale
}

# Quarter-tone intervals (in cents)
QUARTER_TONE_GRID = np.arange(0, 1200, 50)  # 24-TET: 0, 50, 100, 150, 200...


def cents_to_midi(cents: float, root_midi: int = 60) -> float:
    """
    Convert cents interval to MIDI note number with fractional part for microtones.

    Args:
        cents: Interval in cents from root
        root_midi: MIDI note number of root (default C4 = 60)

    Returns:
        MIDI note number with fractional part for quarter tones
    """
    return root_midi + (cents / 100.0)


def midi_to_cents(midi_note: float, root_midi: int = 60) -> float:
    """
    Convert MIDI note number to cents interval from root.

    Args:
        midi_note: MIDI note number (can be fractional)
        root_midi: MIDI note number of root

    Returns:
        Interval in cents from root
    """
    return (midi_note - root_midi) * 100.0


def detect_quarter_tones(
    frequencies: np.ndarray, confidence: np.ndarray, min_confidence: float = 0.3
) -> Dict[str, Any]:
    """
    Detect quarter-tone intervals in frequency data.

    Args:
        frequencies: Array of frequencies in Hz
        confidence: Confidence scores for frequency estimates
        min_confidence: Minimum confidence threshold

    Returns:
        Dict with quarter-tone analysis results
    """
    logger.info("Detecting quarter-tone intervals...")

    # Filter by confidence
    valid_mask = confidence >= min_confidence
    valid_freqs = frequencies[valid_mask]

    if len(valid_freqs) == 0:
        return {
            "quarter_tones_detected": False,
            "microtonal_ratio": 0.0,
            "suggested_tuning": "12-TET",
            "quarter_tone_notes": [],
        }

    # Convert to MIDI notes with fractional parts
    midi_notes = librosa.hz_to_midi(valid_freqs)

    # Calculate deviations from 12-TET grid
    rounded_midi = np.round(midi_notes)
    deviations_cents = (midi_notes - rounded_midi) * 100

    # Count significant quarter-tone deviations (around ±50 cents)
    quarter_tone_mask = (np.abs(deviations_cents - 50) < 15) | (
        np.abs(deviations_cents + 50) < 15
    )
    quarter_tone_count = np.sum(quarter_tone_mask)
    microtonal_ratio = quarter_tone_count / len(midi_notes)

    # Extract quarter-tone notes
    quarter_tone_notes = []
    if quarter_tone_count > 0:
        qt_indices = np.where(quarter_tone_mask)[0]
        for idx in qt_indices[:20]:  # Limit to first 20 examples
            midi_note = midi_notes[idx]
            deviation = deviations_cents[idx]
            quarter_tone_notes.append(
                {
                    "midi_note": float(midi_note),
                    "frequency_hz": float(valid_freqs[idx]),
                    "deviation_cents": float(deviation),
                    "is_quarter_tone_flat": deviation < -25,
                    "is_quarter_tone_sharp": deviation > 25,
                }
            )

    # Determine suggested tuning system
    if microtonal_ratio > 0.15:  # 15% threshold
        suggested_tuning = "24-TET"
        quarter_tones_detected = True
    elif microtonal_ratio > 0.05:  # 5% threshold
        suggested_tuning = "Mixed"
        quarter_tones_detected = True
    else:
        suggested_tuning = "12-TET"
        quarter_tones_detected = False

    logger.info(f"Quarter-tone analysis: {microtonal_ratio:.1%} microtonal content")
    logger.info(f"Suggested tuning: {suggested_tuning}")

    return {
        "quarter_tones_detected": quarter_tones_detected,
        "microtonal_ratio": microtonal_ratio,
        "suggested_tuning": suggested_tuning,
        "quarter_tone_count": int(quarter_tone_count),
        "total_notes": len(midi_notes),
        "quarter_tone_notes": quarter_tone_notes,
        "deviation_stats": {
            "mean_deviation": float(np.mean(deviations_cents)),
            "std_deviation": float(np.std(deviations_cents)),
            "max_deviation": float(np.max(np.abs(deviations_cents))),
        },
    }


def detect_maqam_scale(
    midi_notes: List[float], root_midi: Optional[int] = None
) -> Dict[str, Any]:
    """
    Detect which maqam scale best fits the given MIDI notes.

    Args:
        midi_notes: List of MIDI note numbers (can be fractional for quarter tones)
        root_midi: Root note in MIDI (if None, will try to detect)

    Returns:
        Dict with maqam detection results
    """
    logger.info("Detecting maqam scale...")

    if len(midi_notes) < 4:
        return {"maqam_detected": False, "best_maqam": None, "confidence": 0.0}

    # Convert to unique pitch classes (mod 12 with quarter-tone precision)
    unique_notes = np.unique(midi_notes)

    best_maqam = None
    best_score = 0
    best_root = None
    maqam_scores = {}

    # Try different roots if not specified
    roots_to_try = (
        [root_midi]
        if root_midi
        else range(int(min(unique_notes)), int(max(unique_notes)) + 1)
    )

    for root in roots_to_try:
        if root is None:
            continue

        # Convert notes to cents from this root
        notes_cents = [(note - root) * 100 for note in unique_notes]
        notes_cents = [c % 1200 for c in notes_cents]  # Normalize to one octave

        for maqam_name, maqam_scale in MAQAMAT_SCALES.items():
            # Calculate how well the notes fit this maqam
            score = 0
            for note_cents in notes_cents:
                # Find closest maqam scale degree
                distances = [abs(note_cents - degree) for degree in maqam_scale]
                min_distance = min(distances)

                # Score based on proximity (closer = higher score)
                if min_distance <= 25:  # Within quarter tone
                    score += 1.0
                elif min_distance <= 50:  # Within semitone
                    score += 0.5
                elif min_distance <= 75:
                    score += 0.2

            # Normalize score by number of notes
            normalized_score = score / len(notes_cents) if notes_cents else 0

            key = f"{maqam_name}_root_{root}"
            maqam_scores[key] = {
                "maqam": maqam_name,
                "root_midi": root,
                "score": normalized_score,
            }

            if normalized_score > best_score:
                best_score = normalized_score
                best_maqam = maqam_name
                best_root = root

    maqam_detected = best_score > 0.6  # Confidence threshold

    logger.info(
        f"Best maqam: {best_maqam} (root: {best_root}, score: {best_score:.2f})"
    )

    return {
        "maqam_detected": maqam_detected,
        "best_maqam": best_maqam,
        "root_midi": best_root,
        "confidence": best_score,
        "all_scores": dict(
            sorted(maqam_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:5]
        ),
    }


def quantize_to_quarter_tones(
    midi_notes: List[Dict[str, Any]], force_24tet: bool = False
) -> List[Dict[str, Any]]:
    """
    Quantize notes to quarter-tone grid (24-TET).

    Args:
        midi_notes: List of note dictionaries with 'pitch' field
        force_24tet: Force quantization even if quarter tones not detected

    Returns:
        List of quantized notes with quarter-tone precision
    """
    logger.info("Quantizing to quarter-tone grid...")

    quantized_notes = []

    for note in midi_notes:
        original_pitch = note["pitch"]

        # Quantize to 24-TET grid (quarter tones = 0.5 semitone steps)
        quantized_pitch = round(original_pitch * 2) / 2  # Round to nearest 0.5

        # Calculate pitch bend for MIDI (in cents)
        pitch_bend_cents = (quantized_pitch - int(quantized_pitch)) * 100

        quantized_note = note.copy()
        quantized_note.update(
            {
                "pitch": quantized_pitch,
                "original_pitch": original_pitch,
                "pitch_bend_cents": pitch_bend_cents,
                "is_quarter_tone": abs(pitch_bend_cents - 50) < 10
                or abs(pitch_bend_cents + 50) < 10,
                "midi_note_base": int(quantized_pitch),
                "microtonal_deviation": quantized_pitch - original_pitch,
            }
        )

        quantized_notes.append(quantized_note)

    quarter_tone_count = sum(1 for n in quantized_notes if n["is_quarter_tone"])
    logger.info(
        f"Quantized {len(quantized_notes)} notes, {quarter_tone_count} with quarter tones"
    )

    return quantized_notes


def analyze_microtonal_content(audio_bytes: bytes) -> Dict[str, Any]:
    """
    Comprehensive microtonal analysis of audio content.

    Args:
        audio_bytes: Raw audio data

    Returns:
        Dict with complete microtonal analysis
    """
    logger.info("=== Microtonal Music Analysis ===")

    try:
        import soundfile as sf
        import io

        # Load audio
        y, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if len(y.shape) > 1:
            y = y.mean(axis=1)  # Convert to mono

        # Pitch tracking with high resolution
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            frame_length=2048,
            hop_length=512,
        )

        # Remove unvoiced sections
        voiced_f0 = f0[voiced_flag]
        voiced_confidence = voiced_probs[voiced_flag]

        if len(voiced_f0) == 0:
            return {
                "microtonal_analysis_available": False,
                "error": "No voiced content detected",
            }

        # Detect quarter tones
        quarter_tone_analysis = detect_quarter_tones(voiced_f0, voiced_confidence)

        # Convert to MIDI for maqam detection
        midi_notes = librosa.hz_to_midi(voiced_f0[voiced_confidence > 0.3])

        # Detect maqam if quarter tones are present
        maqam_analysis = None
        if quarter_tone_analysis["quarter_tones_detected"]:
            maqam_analysis = detect_maqam_scale(midi_notes.tolist())

        logger.info("=== Microtonal Analysis Complete ===")
        logger.info(
            f"Quarter tones: {'✓' if quarter_tone_analysis['quarter_tones_detected'] else '✗'}"
        )
        if maqam_analysis and maqam_analysis["maqam_detected"]:
            logger.info(
                f"Maqam: {maqam_analysis['best_maqam']} (confidence: {maqam_analysis['confidence']:.2f})"
            )

        return {
            "microtonal_analysis_available": True,
            "quarter_tone_analysis": quarter_tone_analysis,
            "maqam_analysis": maqam_analysis,
            "recommended_processing": {
                "use_24tet": quarter_tone_analysis["quarter_tones_detected"],
                "enable_pitch_bend": quarter_tone_analysis["quarter_tones_detected"],
                "cultural_context": maqam_analysis["best_maqam"]
                if maqam_analysis and maqam_analysis["maqam_detected"]
                else None,
            },
        }

    except Exception as e:
        logger.error(f"Microtonal analysis failed: {e}")
        return {"microtonal_analysis_available": False, "error": str(e)}


def get_maqam_info(maqam_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific maqam.

    Args:
        maqam_name: Name of the maqam

    Returns:
        Dict with maqam information
    """
    if maqam_name not in MAQAMAT_SCALES:
        return {"error": f"Unknown maqam: {maqam_name}"}

    scale = MAQAMAT_SCALES[maqam_name]

    return {
        "name": maqam_name,
        "scale_degrees_cents": scale,
        "scale_degrees_midi": [cents_to_midi(c) for c in scale],
        "has_quarter_tones": any(c % 100 == 50 for c in scale),
        "quarter_tone_positions": [i for i, c in enumerate(scale) if c % 100 == 50],
        "characteristic_intervals": {
            "second": scale[1] - scale[0],
            "third": scale[2] - scale[0],
            "fourth": scale[3] - scale[0],
            "fifth": scale[4] - scale[0],
            "sixth": scale[5] - scale[0],
            "seventh": scale[6] - scale[0],
        },
    }
