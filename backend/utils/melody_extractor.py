"""
Melody extraction utilities for filtering polyphonic MIDI transcriptions.

This module provides functions to extract clean melodic lines from dense
polyphonic transcriptions by filtering notes based on amplitude, reducing
polyphony, and selecting dominant melodic content.
"""

import numpy as np
from typing import List, Dict, Any


def filter_by_amplitude(
    notes: List[Dict[str, Any]], min_amplitude: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Filter notes by minimum amplitude threshold.

    Removes quiet notes that are likely accompaniment or artifacts.

    Args:
        notes: List of note dictionaries with 'amplitude' field
        min_amplitude: Minimum amplitude threshold (0.0 to 1.0)

    Returns:
        Filtered list of notes above amplitude threshold
    """
    return [note for note in notes if note.get("amplitude", 0.0) >= min_amplitude]


def extract_monophonic_melody(
    notes: List[Dict[str, Any]], time_window: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Extract a monophonic melody by selecting the dominant note in each time window.

    For overlapping notes, selects the note with highest amplitude.
    This creates a single melodic line suitable for sheet music.

    Args:
        notes: List of note dictionaries with 'start_time_s', 'end_time_s', 'amplitude'
        time_window: Time window size in seconds for grouping notes

    Returns:
        List of non-overlapping notes representing the melody
    """
    if not notes:
        return []

    # Sort notes by start time
    sorted_notes = sorted(notes, key=lambda n: n["start_time_s"])

    melody = []
    current_time = 0.0

    while current_time <= sorted_notes[-1]["end_time_s"]:
        # Find all notes active in current window
        window_end = current_time + time_window
        active_notes = [
            note
            for note in sorted_notes
            if note["start_time_s"] <= current_time < note["end_time_s"]
            or current_time <= note["start_time_s"] < window_end
        ]

        if active_notes:
            # Select note with highest amplitude
            dominant = max(active_notes, key=lambda n: n["amplitude"])

            # Avoid duplicates - check if this note is already in melody
            if not melody or dominant != melody[-1]:
                melody.append(dominant)
                # Jump to the end of this note to avoid selecting it again
                current_time = dominant["end_time_s"]
        else:
            current_time += time_window

    return melody


def reduce_polyphony(
    notes: List[Dict[str, Any]], max_simultaneous: int = 2
) -> List[Dict[str, Any]]:
    """
    Reduce polyphony by limiting the number of simultaneous notes.

    When more than max_simultaneous notes overlap, keeps only the loudest ones.

    Args:
        notes: List of note dictionaries
        max_simultaneous: Maximum number of notes allowed to play simultaneously

    Returns:
        List of notes with reduced polyphony
    """
    if not notes or max_simultaneous < 1:
        return notes

    sorted_notes = sorted(notes, key=lambda n: n["start_time_s"])
    result = []

    for note in sorted_notes:
        # Find notes currently playing at this note's start time
        overlapping = [
            n
            for n in result
            if n["start_time_s"] <= note["start_time_s"] < n["end_time_s"]
        ]

        if len(overlapping) < max_simultaneous:
            # Room for this note
            result.append(note)
        else:
            # Too many notes - replace the quietest one if this note is louder
            overlapping_sorted = sorted(overlapping, key=lambda n: n["amplitude"])
            quietest = overlapping_sorted[0]

            if note["amplitude"] > quietest["amplitude"]:
                result.remove(quietest)
                result.append(note)

    return result


def filter_short_notes(
    notes: List[Dict[str, Any]], min_duration: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Remove very short notes that are likely artifacts or ornamentations.

    Args:
        notes: List of note dictionaries
        min_duration: Minimum note duration in seconds

    Returns:
        List of notes with duration >= min_duration
    """
    return [
        note
        for note in notes
        if (note["end_time_s"] - note["start_time_s"]) >= min_duration
    ]


def apply_melody_extraction(
    notes: List[Dict[str, Any]],
    melody_only: bool = False,
    min_amplitude: float = 0.5,
    polyphony_limit: int = 1,
    min_note_duration: float = 0.1,
) -> List[Dict[str, Any]]:
    """
    Apply full melody extraction pipeline.

    Combines all filtering techniques to extract a clean melodic line
    suitable for sheet music.

    Args:
        notes: List of note dictionaries from Basic Pitch
        melody_only: If True, extract monophonic melody (1 note at a time)
        min_amplitude: Minimum amplitude threshold (0.0 to 1.0)
        polyphony_limit: Maximum simultaneous notes (1 = monophonic)
        min_note_duration: Minimum note duration in seconds

    Returns:
        Filtered list of notes representing the melody
    """
    if not notes:
        return notes

    # 1. Filter by amplitude (remove quiet accompaniment)
    filtered = filter_by_amplitude(notes, min_amplitude)

    # 2. Remove very short notes (artifacts)
    filtered = filter_short_notes(filtered, min_note_duration)

    # 3. Apply melody extraction or polyphony reduction
    if melody_only:
        filtered = extract_monophonic_melody(filtered, time_window=0.1)
    elif polyphony_limit > 1:
        filtered = reduce_polyphony(filtered, max_simultaneous=polyphony_limit)

    return filtered


def get_melody_stats(
    original_notes: List[Dict[str, Any]], filtered_notes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Get statistics comparing original and filtered note sets.

    Args:
        original_notes: Original note list
        filtered_notes: Filtered note list

    Returns:
        Dict with statistics (reduction percentage, avg amplitude, etc.)
    """
    if not original_notes:
        return {"reduction_pct": 0.0}

    reduction_pct = (1 - len(filtered_notes) / len(original_notes)) * 100

    original_avg_amp = np.mean([n["amplitude"] for n in original_notes])
    filtered_avg_amp = (
        np.mean([n["amplitude"] for n in filtered_notes]) if filtered_notes else 0.0
    )

    return {
        "original_note_count": len(original_notes),
        "filtered_note_count": len(filtered_notes),
        "reduction_pct": round(reduction_pct, 1),
        "original_avg_amplitude": round(original_avg_amp, 3),
        "filtered_avg_amplitude": round(filtered_avg_amp, 3),
    }
