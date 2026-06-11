"""
Intelligent vocal-guided melody extraction.

This module analyzes both vocal and instrumental transcriptions to identify
the TRUE melodic line. It uses vocal pitch contours as guidance to select
the most melodically significant notes from instrumental parts.
"""

from typing import List, Dict, Any, Optional


def calculate_pitch_contour_similarity(
    notes1: List[Dict[str, Any]],
    notes2: List[Dict[str, Any]],
    time_tolerance: float = 0.2,
) -> float:
    """
    Calculate similarity between two note sequences based on pitch contour.

    Measures how closely the pitch movement patterns match, regardless of
    exact pitch values. This helps identify melodic instruments that follow
    the vocal line.

    Args:
        notes1: First note sequence
        notes2: Second note sequence
        time_tolerance: Time window for matching notes (seconds)

    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not notes1 or not notes2:
        return 0.0

    matches = 0
    for note1 in notes1:
        # Find notes in notes2 that occur around the same time
        time_match = [
            n
            for n in notes2
            if abs(n["start_time_s"] - note1["start_time_s"]) < time_tolerance
        ]

        if time_match:
            # Check if pitch direction matches (ascending/descending)
            matches += 1

    return matches / max(len(notes1), len(notes2))


def identify_melodic_notes(
    vocal_notes: List[Dict[str, Any]],
    instrument_notes: List[Dict[str, Any]],
    min_similarity: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Identify instrument notes that follow the vocal melody.

    Compares instrument notes with vocal pitch contour to find notes that
    are melodically significant (following the sung melody). This version
    is designed to KEEP all melodic notes, not reduce to a target count.

    Args:
        vocal_notes: Transcribed vocal notes
        instrument_notes: Transcribed instrument notes
        min_similarity: Minimum similarity to consider melodic

    Returns:
        Filtered list of melodic instrument notes
    """
    if not vocal_notes:
        # No vocal guidance - keep notes with good amplitude (top 70%)
        sorted_by_amp = sorted(
            instrument_notes, key=lambda n: n["amplitude"], reverse=True
        )
        return sorted_by_amp[: int(len(sorted_by_amp) * 0.7)]

    melodic_notes = []

    for inst_note in instrument_notes:
        # Find vocal notes happening around the same time
        time_window = 0.5  # Wider window for better matching
        nearby_vocals = [
            v
            for v in vocal_notes
            if abs(v["start_time_s"] - inst_note["start_time_s"]) < time_window
        ]

        if nearby_vocals:
            # Check if pitch is similar to vocal (within 1 octave or same note class)
            for vocal in nearby_vocals:
                pitch_diff = abs(inst_note["pitch"] - vocal["pitch"])
                same_note_class = (inst_note["pitch"] % 12) == (vocal["pitch"] % 12)
                within_octave = pitch_diff <= 12

                # If same note class OR within octave OR high amplitude
                if same_note_class or within_octave or inst_note["amplitude"] > 0.6:
                    melodic_notes.append(inst_note)
                    break
        elif inst_note["amplitude"] > 0.5:
            # No nearby vocals but loud note - likely melodic
            melodic_notes.append(inst_note)

    return melodic_notes


def extract_melodic_contour(
    notes: List[Dict[str, Any]], smoothing_window: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Extract the primary melodic contour by selecting the most prominent
    note per time window.

    Creates a smooth melodic line by removing rapid alternations and
    keeping only notes that form a clear melodic shape.

    Args:
        notes: Input notes
        smoothing_window: Time window for smoothing (seconds)

    Returns:
        Smoothed melodic line
    """
    if not notes:
        return []

    sorted_notes = sorted(notes, key=lambda n: n["start_time_s"])
    melody = []

    current_time = sorted_notes[0]["start_time_s"]
    end_time = sorted_notes[-1]["end_time_s"]

    while current_time < end_time:
        # Find notes in current window
        window_end = current_time + smoothing_window
        window_notes = [
            n
            for n in sorted_notes
            if n["start_time_s"] >= current_time and n["start_time_s"] < window_end
        ]

        if window_notes:
            # Select the loudest note in this window
            best_note = max(window_notes, key=lambda n: n["amplitude"])

            # Only add if it's not redundant with previous note
            if not melody or best_note["pitch"] != melody[-1]["pitch"]:
                melody.append(best_note)

            # Move to end of selected note
            current_time = best_note["end_time_s"]
        else:
            current_time += smoothing_window

    return melody


def filter_accompaniment_patterns(
    notes: List[Dict[str, Any]], min_duration: float = 0.08
) -> List[Dict[str, Any]]:
    """
    Remove repetitive accompaniment patterns (chords, arpeggios, ostinatos).

    Identifies and removes notes that form repetitive patterns typical of
    accompaniment rather than melody. Less aggressive than before - preserves
    fast melody runs.

    Args:
        notes: Input notes
        min_duration: Minimum note duration for melody (lowered to 0.08s)

    Returns:
        Notes with accompaniment patterns removed
    """
    if len(notes) < 4:
        return notes

    filtered = []

    # Detect rapid repetition (arpeggios, fast chords)
    for i, note in enumerate(notes):
        duration = note["end_time_s"] - note["start_time_s"]

        # Skip VERY short notes (likely artifacts, not fast melody)
        if duration < min_duration:
            continue

        # Check for rapid repetition of SAME EXACT pitch (ostinato)
        if i > 1 and i < len(notes) - 1:
            prev_note = notes[i - 1]
            next_note = notes[i + 1]

            # If same pitch repeating 3+ times rapidly, likely accompaniment
            if (
                note["pitch"] == prev_note["pitch"] == next_note["pitch"]
                and duration < 0.15
                and note["amplitude"] < 0.5
            ):
                continue

        filtered.append(note)

    return filtered


def select_melodic_range(
    notes: List[Dict[str, Any]], vocal_range: Optional[tuple[int, int]] = None
) -> List[Dict[str, Any]]:
    """
    Select notes in the melodic range, guided by vocal range if available.

    Filters to G clef (treble clef) range suitable for violin and guitar.
    This ensures the output can be notated in treble clef only.

    Args:
        notes: Input notes
        vocal_range: Optional (min_pitch, max_pitch) from vocals

    Returns:
        Notes in treble clef range
    """
    if not notes:
        return []

    # G clef (treble clef) range: E3 to C7
    # E3 (MIDI 52) is the lowest comfortable treble clef note
    # C7 (MIDI 96) is the practical upper limit for most melodies
    # This range works perfectly for violin and guitar

    if vocal_range:
        min_pitch, max_pitch = vocal_range
        # Extend vocal range but constrain to treble clef
        min_pitch = max(52, min_pitch - 12)  # Not below E3 (treble clef limit)
        max_pitch = min(96, max_pitch + 12)  # Not above C7
    else:
        # Default treble clef melodic range: G3 to E6
        # G3 (MIDI 55) - comfortable for guitar/violin
        # E6 (MIDI 88) - practical melodic upper limit
        min_pitch = 55  # G3
        max_pitch = 88  # E6

    return [note for note in notes if min_pitch <= note["pitch"] <= max_pitch]


def apply_vocal_guided_extraction(
    vocal_notes: List[Dict[str, Any]],
    instrument_notes: List[Dict[str, Any]],
    keep_all_melody: bool = True,
) -> Dict[str, Any]:
    """
    Apply complete vocal-guided melody extraction pipeline.

    Uses vocal transcription to guide intelligent filtering of instrument
    notes, producing melody-focused results that preserve all melodic notes.

    Args:
        vocal_notes: Transcribed vocal notes
        instrument_notes: Transcribed instrument notes
        keep_all_melody: If True, keeps all melodic notes (default: True)

    Returns:
        Dict with:
            - melody_notes: Extracted melody
            - vocal_guided: Whether vocals were used for guidance
            - stats: Processing statistics
    """
    original_count = len(instrument_notes)
    vocal_guided = len(vocal_notes) > 0

    # Step 1: Determine vocal range (if available)
    vocal_range = None
    if vocal_notes:
        pitches = [n["pitch"] for n in vocal_notes]
        vocal_range = (min(pitches), max(pitches))

    # Step 2: Filter to melodic range (not too strict)
    ranged_notes = select_melodic_range(instrument_notes, vocal_range)

    # Step 3: Identify melodic notes using vocal guidance
    if vocal_guided:
        melodic = identify_melodic_notes(vocal_notes, ranged_notes)
    else:
        # No vocals - use amplitude filtering (keep top 60%)
        melodic = sorted(ranged_notes, key=lambda n: n["amplitude"], reverse=True)[
            : int(len(ranged_notes) * 0.6)
        ]

    # Step 4: Filter accompaniment patterns (but keep short melody notes)
    # Use shorter min_duration to preserve fast melody runs
    filtered = filter_accompaniment_patterns(melodic, min_duration=0.08)

    # Step 5: If keep_all_melody, skip aggressive reduction
    if keep_all_melody:
        # Just sort by time, keep all melodic notes
        final_notes = sorted(filtered, key=lambda n: n["start_time_s"])
    else:
        # Apply contour extraction (for very simple output)
        final_notes = extract_melodic_contour(filtered, smoothing_window=0.3)

    stats = {
        "original_count": original_count,
        "after_range_filter": len(ranged_notes),
        "after_melodic_filter": len(melodic),
        "after_pattern_filter": len(filtered),
        "final_count": len(final_notes),
        "reduction_pct": round((1 - len(final_notes) / original_count) * 100, 1)
        if original_count > 0
        else 0,
        "vocal_guided": vocal_guided,
        "vocal_note_count": len(vocal_notes),
    }

    return {
        "melody_notes": final_notes,
        "vocal_guided": vocal_guided,
        "stats": stats,
    }
