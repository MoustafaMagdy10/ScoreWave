"""
Transpose service for shifting notes by interval or to target key.
"""

from typing import List, Dict, Any, Optional

from shared.logger import logger

# Semitone mappings
KEY_TO_SEMITONES = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}


def transpose_notes(
    notes: List[Dict[str, Any]],
    semitones: int = 0,
    from_key: Optional[str] = None,
    to_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Transpose notes by semitones or from one key to another.

    Args:
        notes: List of note dictionaries with 'pitch' field (MIDI note number).
        semitones: Number of semitones to shift (positive = up, negative = down).
        from_key: Source key (e.g., "G major", "A minor"). Used with to_key.
        to_key: Target key (e.g., "C major", "E minor"). Used with from_key.

    Returns:
        List of transposed note dictionaries.

    Raises:
        ValueError: If from_key or to_key contains an invalid root note.
    """
    if from_key and to_key:
        # Parse keys (e.g., "G major" -> "G")
        from_root = from_key.split()[0].replace("minor", "").strip()
        to_root = to_key.split()[0].replace("minor", "").strip()

        if from_root not in KEY_TO_SEMITONES:
            raise ValueError(f"Invalid source key root: {from_root}")
        if to_root not in KEY_TO_SEMITONES:
            raise ValueError(f"Invalid target key root: {to_root}")

        semitones = KEY_TO_SEMITONES[to_root] - KEY_TO_SEMITONES[from_root]

    if semitones == 0:
        return notes

    transposed = []
    for note in notes:
        new_note = note.copy()
        new_note["pitch"] = note["pitch"] + semitones
        # Keep within valid MIDI range (piano range: 21-108)
        while new_note["pitch"] < 21:
            new_note["pitch"] += 12
        while new_note["pitch"] > 108:
            new_note["pitch"] -= 12
        transposed.append(new_note)

    logger.info(f"Transposed {len(notes)} notes by {semitones} semitones")
    return transposed


def get_available_keys() -> List[str]:
    """
    Return list of available keys for transposition.

    Returns:
        List of key names in format "X major" or "x minor".
    """
    majors = [
        f"{k} major"
        for k in ["C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db"]
    ]
    minors = [
        f"{k.lower()} minor"
        for k in ["A", "E", "B", "F#", "C#", "G#", "D", "G", "C", "F", "Bb", "Eb"]
    ]
    return majors + minors
