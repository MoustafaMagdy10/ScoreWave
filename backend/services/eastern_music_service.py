"""
Eastern music support: Maqam detection, quarter tones, and Arabic ornaments.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from shared.logger import logger
from services.pitch_histogram_service import extract_pitch_histogram

# Maqam scales (intervals in quarter tones, 24-TET)
# Standard semitone = 2 quarter tones
MAQAMAT = {
    "Rast": [0, 4, 7, 10, 14, 18, 21, 24],  # C D E-half F G A B-half C
    "Bayati": [0, 3, 6, 10, 14, 17, 20, 24],  # D E-half F G A Bb C D
    "Saba": [0, 3, 6, 8, 14, 16, 20, 24],  # D E-half F Gb A Bbb C D
    "Sikah": [0, 3, 7, 10, 14, 17, 21, 24],  # E-half F# A B C# D E-half
    "Hijaz": [0, 2, 8, 10, 14, 16, 22, 24],  # D Eb F# G A Bb C# D
    "Nahawand": [0, 4, 6, 10, 14, 16, 22, 24],  # C D Eb F G Ab B C (harmonic minor-ish)
    "Kurd": [0, 2, 6, 10, 14, 16, 20, 24],  # D Eb F G A Bb C D
    "Ajam": [0, 4, 8, 10, 14, 18, 22, 24],  # C D E F G A B C (major scale)
}

# Quarter tone pitch adjustments
QUARTER_TONE_FLAT = -0.5  # Lower by quarter tone
QUARTER_TONE_SHARP = 0.5  # Raise by quarter tone


def _midi_to_quarter_tones(midi: float, tonic: float) -> int:
    """
    Convert a MIDI pitch to its quarter-tone interval from the tonic.

    Args:
        midi: Continuous MIDI value (pitch + cents_dev/100).
        tonic: Continuous tonic MIDI value.

    Returns:
        Quarter-tone interval (0–23) in 24-TET.
        (1 semitone = 2 quarter tones, octave = 24 quarter tones)
    """
    continuous_diff = midi - tonic
    quarter_tone_interval = int(round(continuous_diff * 2))
    return quarter_tone_interval % 24


def detect_maqam(notes: List[Dict[str, Any]]) -> Tuple[str, int, float]:
    """
    Detect the maqam from note data using corrected quarter-tone interval analysis.

    Args:
        notes: List of note dicts, each with at least a ``pitch`` key (MIDI int)
               and optionally a ``midi_continuous`` key (float with cents deviation).

    Returns:
        Tuple of (maqam_name, tonic_midi, confidence) where tonic_midi is the
        detected tonic as an integer MIDI note number.
    """
    if len(notes) < 4:
        return "Unknown", 60, 0.0

    pitches = [
        n.get("midi_continuous", n["pitch"])
        for n in notes
        if n.get("frequency", 0) > 0 or n.get("pitch", 0) > 20
    ]

    # Vote for tonic using ROUNDED integer pitches (floats are too unique)
    rounded_pitches = [int(round(p)) for p in pitches]
    tonic = max(set(rounded_pitches), key=rounded_pitches.count)
    tonic_continuous = float(tonic)

    # Build the set of quarter-tone intervals present in this piece
    intervals = {_midi_to_quarter_tones(p, tonic_continuous) for p in pitches}

    # Match against known maqam patterns
    best_match, best_score = "Ajam", 0.0
    for name, pattern in MAQAMAT.items():
        pattern_set = set(pattern)
        score = len(intervals & pattern_set) / max(len(intervals), len(pattern_set))
        if score > best_score:
            best_score, best_match = score, name

    confidence = min(1.0, best_score * 1.2)
    logger.info(
        f"Detected maqam: {best_match} on tonic {tonic} (confidence: {confidence:.2f})"
    )
    return best_match, tonic, confidence


def detect_quarter_tones(
    notes: List[Dict[str, Any]], pitch_data: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Analyze notes for quarter-tone inflections (microtonal pitches).

    If pitch_data (from CREPE) is available, use actual frequency analysis.
    Otherwise, use statistical estimation.
    """
    enhanced_notes = []

    for note in notes:
        new_note = note.copy()

        # Check if note has microtonal data
        if "frequency_hz" in note:
            # Calculate deviation from equal temperament
            midi_pitch = note["pitch"]
            expected_freq = 440.0 * (2 ** ((midi_pitch - 69) / 12))
            actual_freq = note["frequency_hz"]

            # Deviation in cents (100 cents = 1 semitone)
            cents_deviation = 1200 * np.log2(actual_freq / expected_freq)

            # Quarter tone is ~50 cents
            if cents_deviation < -35:
                new_note["quarter_tone"] = "flat"
                new_note["cents_deviation"] = cents_deviation
            elif cents_deviation > 35:
                new_note["quarter_tone"] = "sharp"
                new_note["cents_deviation"] = cents_deviation
            else:
                new_note["quarter_tone"] = None

        enhanced_notes.append(new_note)

    quarter_count = sum(1 for n in enhanced_notes if n.get("quarter_tone"))
    if quarter_count > 0:
        logger.info(f"Detected {quarter_count} quarter-tone notes")

    return enhanced_notes


def analyze_eastern_music(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Complete Eastern music analysis.
    """
    maqam, tonic, maqam_confidence = detect_maqam(notes)
    notes_with_microtones = detect_quarter_tones(notes)

    quarter_tone_count = sum(1 for n in notes_with_microtones if n.get("quarter_tone"))

    return {
        "maqam": maqam,
        "tonic": tonic,
        "maqam_confidence": maqam_confidence,
        "quarter_tone_count": quarter_tone_count,
        "is_eastern": maqam_confidence > 0.5 or quarter_tone_count > len(notes) * 0.1,
        "notes": notes_with_microtones,
    }


def get_maqam_info(maqam_name: str) -> Dict[str, Any]:
    """Get information about a specific maqam."""
    if maqam_name not in MAQAMAT:
        return {"error": f"Unknown maqam: {maqam_name}"}

    intervals = MAQAMAT[maqam_name]

    # Convert to note names (approximate)
    note_names = []
    base_notes = [
        "C",
        "C+",
        "C#",
        "D-",
        "D",
        "D+",
        "D#",
        "E-",
        "E",
        "E+",
        "F",
        "F+",
        "F#",
        "G-",
        "G",
        "G+",
        "G#",
        "A-",
        "A",
        "A+",
        "A#",
        "B-",
        "B",
        "B+",
    ]
    for interval in intervals:
        note_names.append(base_notes[interval % 24])

    return {
        "name": maqam_name,
        "intervals_quarter_tones": intervals,
        "notes": note_names,
        "has_quarter_tones": any(i % 2 != 0 for i in intervals),
    }


def list_maqamat() -> List[Dict[str, Any]]:
    """List all available maqamat with basic info."""
    return [get_maqam_info(name) for name in MAQAMAT.keys()]


# ── Audio-based detection (histogram path) ────────────────────────────────────


def detect_maqam_from_audio(audio_input: str | bytes) -> Dict[str, Any]:
    """
    High-level maqam detection from raw audio bytes or a file path.

    Strategy:
    1. Extract a cents-based pitch histogram (Essentia → librosa fallback).
    2. Match the histogram scale degrees against the MAQAMAT dictionary.
    3. Return maqam name, tonic note, confidence, and histogram metadata.

    Args:
        audio_input: Either a file path (str) or raw audio bytes.

    Returns:
        Dict with keys: ``maqam``, ``confidence``, ``tonic_note``,
        ``tonic_hz``, ``tonic_cents``, ``peak_cents``, ``hist``,
        ``essentia_used``, ``method``.
    """
    logger.info("Starting audio-based maqam detection...")

    try:
        histogram_result = extract_pitch_histogram(audio_input)
    except Exception as exc:
        logger.error(f"Pitch histogram extraction failed: {exc}")
        return {
            "maqam": "Unknown",
            "confidence": 0.0,
            "tonic_note": "?",
            "tonic_hz": 0.0,
            "tonic_cents": 0.0,
            "peak_cents": [],
            "hist": [],
            "essentia_used": False,
            "method": "failed",
            "error": str(exc),
        }

    maqam_name, confidence = _match_histogram_to_maqam(
        histogram_result["peak_cents"],
        histogram_result["tonic_cents"],
    )

    logger.info(
        f"Histogram detection: {maqam_name} "
        f"(confidence={confidence:.2f}, "
        f"tonic={histogram_result['tonic_note']} @ {histogram_result['tonic_cents']:.0f}¢)"
    )

    return {
        "maqam": maqam_name,
        "confidence": confidence,
        "tonic_note": histogram_result["tonic_note"],
        "tonic_hz": histogram_result["tonic_hz"],
        "tonic_cents": histogram_result["tonic_cents"],
        "peak_cents": histogram_result["peak_cents"],
        "hist": histogram_result["hist"],
        "essentia_used": histogram_result["essentia_used"],
        "method": "pitch_histogram",
    }


def _match_histogram_to_maqam(
    peak_cents: List[float],
    tonic_cents: float,
    tolerance: float = 60.0,
) -> Tuple[str, float]:
    """
    Match a list of pitch histogram peaks to the closest MAQAM pattern.

    Converts peak positions to cents-from-tonic intervals and scores each
    maqam by Jaccard similarity against its canonical scale_cents.

    Args:
        peak_cents: Detected pitch peak positions in cents (0–1200).
        tonic_cents: Detected tonic position in cents.
        tolerance: Max cents deviation to count a peak as matching a scale
                   degree (default 60¢ = one quarter tone ± half).

    Returns:
        Tuple of (maqam_name, confidence).
    """
    # MAQAMAT patterns are in quarter-tone integers (0–24).
    # Convert to approximate cents: 1 quarter tone ≈ 50 cents.
    QT_TO_CENTS = 50.0

    if not peak_cents:
        return "Unknown", 0.0

    # Express peaks as intervals from tonic in cents
    intervals_cents = sorted({(p - tonic_cents) % 1200.0 for p in peak_cents})

    best_name, best_score = "Ajam", 0.0

    for name, qt_pattern in MAQAMAT.items():
        # Convert quarter-tone pattern to cents
        pattern_cents = [qt * QT_TO_CENTS for qt in qt_pattern]

        # Count how many peaks fall within tolerance of a pattern degree
        matched_pattern = 0
        for pc in pattern_cents:
            if any(abs(ic - pc) <= tolerance for ic in intervals_cents):
                matched_pattern += 1

        matched_peaks = 0
        for ic in intervals_cents:
            if any(abs(ic - pc) <= tolerance for pc in pattern_cents):
                matched_peaks += 1

        # Jaccard-like score
        union = len(pattern_cents) + len(intervals_cents) - matched_pattern
        score = matched_pattern / max(union, 1)

        if score > best_score:
            best_score, best_name = score, name

    confidence = min(1.0, best_score * 1.25)
    return best_name, confidence


async def get_maqam_db_info(name_latin: str, session: Any) -> Optional[Dict[str, Any]]:
    """
    Fetch rich maqam info from the database by Latin name.

    Args:
        name_latin: Latin transliteration (e.g. "Bayati").
        session: SQLAlchemy AsyncSession.

    Returns:
        Maqam dict or None if not found.
    """
    from sqlalchemy import select
    from models.maqam import Maqam

    result = await session.execute(select(Maqam).where(Maqam.name_latin == name_latin))
    maqam = result.scalar_one_or_none()
    return maqam.to_dict() if maqam else None
