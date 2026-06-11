"""
Sheet music generation service using music21.

This service converts quantized note data into proper music notation,
including key detection, dynamics, and MusicXML export.
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np

from music21 import (
    stream,
    note,
    meter,
    tempo,
    key,
    clef,
    instrument,
    dynamics,
    expressions,
    pitch as m21_pitch,
    metadata as m21metadata,
)

from shared.logger import logger


# ── Constants ───────────────────────────────────────────────────────────────

# Treble clef comfortable range (G3 to C6)
TREBLE_CLEF_MIN = 55  # G3
TREBLE_CLEF_MAX = 84  # C6

# Key profiles for Krumhansl-Schmuckler key detection
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

KEY_NAMES_MAJOR = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
KEY_NAMES_MINOR = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]


# ── Key Detection ───────────────────────────────────────────────────────────


def detect_key_signature(notes: List[Dict[str, Any]]) -> Tuple[str, float]:
    """
    Detect the key signature from note data using Krumhansl-Schmuckler algorithm.

    Args:
        notes: List of note dictionaries with 'pitch' field (MIDI number)

    Returns:
        Tuple of (key_name, confidence) e.g. ('G major', 0.85)
    """
    if not notes:
        return "C major", 0.0

    # Count pitch classes (0-11)
    pitch_class_counts = np.zeros(12)
    for note_data in notes:
        pc = note_data["pitch"] % 12
        # Weight by duration and amplitude
        weight = note_data.get("duration_s", 0.5) * note_data.get("amplitude", 0.5)
        pitch_class_counts[pc] += weight

    # Normalize
    total = pitch_class_counts.sum()
    if total == 0:
        return "C major", 0.0
    pitch_class_counts /= total

    # Find best key match using correlation
    best_key = "C major"
    best_correlation = -1

    # Test all major keys
    for i in range(12):
        rotated_profile = np.roll(MAJOR_PROFILE, i)
        correlation = np.corrcoef(pitch_class_counts, rotated_profile)[0, 1]
        if correlation > best_correlation:
            best_correlation = correlation
            best_key = f"{KEY_NAMES_MAJOR[i]} major"

    # Test all minor keys
    for i in range(12):
        rotated_profile = np.roll(MINOR_PROFILE, i)
        correlation = np.corrcoef(pitch_class_counts, rotated_profile)[0, 1]
        if correlation > best_correlation:
            best_correlation = correlation
            best_key = f"{KEY_NAMES_MINOR[i]} minor"

    confidence = max(0, min(1, (best_correlation + 1) / 2))  # Normalize to 0-1

    logger.info(f"Detected key: {best_key} (confidence: {confidence:.2f})")
    return best_key, confidence


def parse_key_string(key_str: str) -> key.Key:
    """Convert key string like 'G major' to music21 Key object."""
    parts = key_str.split()
    if len(parts) == 2:
        tonic, mode = parts
        return key.Key(tonic, mode)
    return key.Key("C", "major")


# ── Dynamics Mapping ────────────────────────────────────────────────────────


def amplitude_to_dynamic(amplitude: float) -> Optional[dynamics.Dynamic]:
    """
    Convert amplitude (0-1) to music21 Dynamic marking.

    Args:
        amplitude: Note amplitude from 0.0 to 1.0

    Returns:
        music21 Dynamic object or None
    """
    if amplitude < 0.15:
        return dynamics.Dynamic("pp")
    elif amplitude < 0.30:
        return dynamics.Dynamic("p")
    elif amplitude < 0.45:
        return dynamics.Dynamic("mp")
    elif amplitude < 0.60:
        return dynamics.Dynamic("mf")
    elif amplitude < 0.75:
        return dynamics.Dynamic("f")
    elif amplitude < 0.90:
        return dynamics.Dynamic("ff")
    else:
        return dynamics.Dynamic("fff")


def should_add_dynamic(
    current_amp: float, previous_amp: Optional[float], threshold: float = 0.15
) -> bool:
    """Determine if a dynamic marking should be added based on amplitude change."""
    if previous_amp is None:
        return True
    return abs(current_amp - previous_amp) > threshold


# ── Note Value Detection ────────────────────────────────────────────────────

# Standard expressible quarter lengths for music21
STANDARD_DURATIONS = [
    4.0,  # whole
    3.0,  # dotted half
    2.0,  # half
    1.5,  # dotted quarter
    1.0,  # quarter
    0.75,  # dotted eighth
    0.5,  # eighth
    0.375,  # dotted 16th
    0.25,  # 16th
    0.125,  # 32nd
    0.0625,  # 64th
]


def quantize_duration(duration_beats: float) -> float:
    """
    Quantize a duration to the nearest expressible note value.

    This prevents "inexpressible duration" errors in MusicXML export.

    Args:
        duration_beats: Raw duration in quarter note beats

    Returns:
        Quantized duration that can be expressed in standard notation
    """
    if duration_beats <= 0:
        return 0.25  # Default to 16th note minimum

    # Find the closest standard duration
    closest = min(STANDARD_DURATIONS, key=lambda d: abs(d - duration_beats))

    # For very long notes, use whole notes
    if duration_beats > 4.0:
        # Round to nearest whole note multiple
        return round(duration_beats)

    return closest


def duration_to_note_type(duration_beats: float) -> Tuple[str, int]:
    """
    Convert duration in beats to note type and dots.

    Args:
        duration_beats: Duration in quarter note beats

    Returns:
        Tuple of (note_type, dots) e.g. ('quarter', 0) or ('half', 1)
    """
    # Common note durations (in beats)
    note_types = [
        (4.0, "whole", 0),
        (3.0, "half", 1),  # Dotted half
        (2.0, "half", 0),
        (1.5, "quarter", 1),  # Dotted quarter
        (1.0, "quarter", 0),
        (0.75, "eighth", 1),  # Dotted eighth
        (0.5, "eighth", 0),
        (0.375, "16th", 1),  # Dotted 16th
        (0.25, "16th", 0),
        (0.125, "32nd", 0),
    ]

    # Find closest match
    for dur, note_type, dots in note_types:
        if abs(duration_beats - dur) < 0.1:
            return note_type, dots

    # Default to quarter note for ambiguous durations
    if duration_beats >= 0.5:
        return "quarter", 0
    else:
        return "eighth", 0


# ── Note Ordering & Validation ──────────────────────────────────────────────


def validate_and_order_notes(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and strictly order notes by start time.
    Removes invalid or out-of-order notes.

    Args:
        notes: Raw note list

    Returns:
        Cleaned, ordered note list
    """
    if not notes:
        return []

    # Filter invalid notes
    valid_notes = []
    for n in notes:
        if "pitch" not in n or "start_time_s" not in n:
            continue
        if n.get("duration_s", 0) <= 0:
            continue
        if n["pitch"] < 21 or n["pitch"] > 108:  # Valid MIDI range
            continue
        valid_notes.append(n)

    # Sort by start time
    sorted_notes = sorted(valid_notes, key=lambda x: x["start_time_s"])

    # Remove overlapping notes of same pitch
    cleaned = []
    for n in sorted_notes:
        if not cleaned:
            cleaned.append(n)
            continue

        last = cleaned[-1]
        # If same pitch and overlapping, keep the louder one
        if n["pitch"] == last["pitch"] and n["start_time_s"] < last.get(
            "end_time_s", last["start_time_s"] + last["duration_s"]
        ):
            if n.get("amplitude", 0) > last.get("amplitude", 0):
                cleaned[-1] = n
        else:
            cleaned.append(n)

    logger.info(f"Note validation: {len(notes)} → {len(cleaned)} notes")
    return cleaned


def constrain_to_treble_clef(
    notes: List[Dict[str, Any]],
    min_pitch: int = TREBLE_CLEF_MIN,
    max_pitch: int = TREBLE_CLEF_MAX,
) -> List[Dict[str, Any]]:
    """
    Constrain notes to treble clef range by transposing outliers.

    Args:
        notes: Note list
        min_pitch: Minimum MIDI pitch (default G3 = 55)
        max_pitch: Maximum MIDI pitch (default C6 = 84)

    Returns:
        Adjusted note list
    """
    adjusted = []
    for n in notes:
        note_copy = n.copy()
        pitch = note_copy["pitch"]

        # Transpose notes below range up by octave(s)
        while pitch < min_pitch:
            pitch += 12

        # Transpose notes above range down by octave(s)
        while pitch > max_pitch:
            pitch -= 12

        # If still out of range, skip the note
        if pitch < min_pitch or pitch > max_pitch:
            logger.debug(
                f"Skipping note {n['pitch']} - out of range even after transposition"
            )
            continue

        note_copy["pitch"] = pitch
        note_copy["transposed"] = pitch != n["pitch"]
        adjusted.append(note_copy)

    transposed_count = sum(1 for n in adjusted if n.get("transposed", False))
    if transposed_count > 0:
        logger.info(f"Transposed {transposed_count} notes to fit treble clef range")

    return adjusted


# ── Rest Insertion ──────────────────────────────────────────────────────────


def insert_rests(
    notes: List[Dict[str, Any]], tempo_bpm: float, min_rest_beats: float = 0.25
) -> List[Dict[str, Any]]:
    """
    Insert rest markers between notes where gaps exist.

    Args:
        notes: Ordered note list
        tempo_bpm: Tempo in BPM
        min_rest_beats: Minimum gap to insert a rest (in beats)

    Returns:
        Note list with rest markers inserted
    """
    if not notes or len(notes) < 2:
        return notes

    beat_duration = 60.0 / tempo_bpm
    min_gap_seconds = min_rest_beats * beat_duration

    result = []
    for i, n in enumerate(notes):
        if i > 0:
            prev = notes[i - 1]
            prev_end = prev.get("end_time_s", prev["start_time_s"] + prev["duration_s"])
            gap = n["start_time_s"] - prev_end

            if gap >= min_gap_seconds:
                # Insert a rest marker
                rest_duration = gap
                rest_beats = rest_duration / beat_duration
                result.append(
                    {
                        "type": "rest",
                        "start_time_s": prev_end,
                        "duration_s": rest_duration,
                        "duration_beats": rest_beats,
                    }
                )

        result.append(n)

    rest_count = sum(1 for n in result if n.get("type") == "rest")
    if rest_count > 0:
        logger.info(f"Inserted {rest_count} rests")

    return result


# ── Main Conversion Function ────────────────────────────────────────────────


def notes_to_music21_score(
    notes: List[Dict[str, Any]],
    tempo_bpm: float = 120.0,
    time_signature: str = "4/4",
    title: str = "Transcribed Melody",
    composer: str = "Songify",
    auto_key: bool = True,
    key_override: Optional[str] = None,
    add_dynamics: bool = True,
    treble_only: bool = True,
) -> Tuple[stream.Score, Dict[str, Any]]:
    """
    Convert quantized note data to a music21 Score object.

    Args:
        notes: List of note dictionaries with pitch, start_time_s, duration_s, amplitude
        tempo_bpm: Tempo in beats per minute
        time_signature: Time signature string (e.g., '4/4', '3/4')
        title: Piece title
        composer: Composer name
        auto_key: Automatically detect key signature
        key_override: Manual key override (e.g., 'G major')
        add_dynamics: Add dynamic markings based on amplitude
        treble_only: Constrain to treble clef range

    Returns:
        Tuple of (music21 Score, metadata dict)
    """
    logger.info(f"Converting {len(notes)} notes to music21 score...")

    beat_duration = 60.0 / tempo_bpm

    # ── Step 1: Validate and order notes ────────────────────────────────────
    clean_notes = validate_and_order_notes(notes)

    # ── Step 2: Constrain to treble clef if requested ───────────────────────
    if treble_only:
        clean_notes = constrain_to_treble_clef(clean_notes)

    # ── Step 3: Detect key signature ────────────────────────────────────────
    if key_override:
        detected_key = key_override
        key_confidence = 1.0
    elif auto_key:
        detected_key, key_confidence = detect_key_signature(clean_notes)
    else:
        detected_key = "C major"
        key_confidence = 0.0

    # ── Step 4: Insert rests ────────────────────────────────────────────────
    notes_with_rests = insert_rests(clean_notes, tempo_bpm)

    # ── Step 5: Create score structure ──────────────────────────────────────
    score = stream.Score()

    # Add metadata
    score.insert(0, m21metadata.Metadata())
    score.metadata.title = title
    score.metadata.composer = composer

    # Create part with instrument
    part = stream.Part()
    part.insert(0, instrument.Piano())
    part.insert(0, clef.TrebleClef())
    part.insert(0, meter.TimeSignature(time_signature))
    part.insert(0, tempo.MetronomeMark(number=tempo_bpm))
    part.insert(0, parse_key_string(detected_key))

    # ── Step 6: Add notes and rests ─────────────────────────────────────────
    current_offset = 0.0
    previous_amplitude = None
    dynamics_added = 0

    for item in notes_with_rests:
        if item.get("type") == "rest" or item.get("pitch", 0) == 0:
            # Add rest - quantize to expressible duration
            rest_beats = item.get("duration_beats", item["duration_s"] / beat_duration)
            rest_beats = quantize_duration(rest_beats)
            r = note.Rest()
            r.quarterLength = rest_beats
            part.append(r)
            current_offset += r.quarterLength
        else:
            # Calculate note duration in beats
            duration_s = item.get("duration_s", 0.5)
            duration_beats = duration_s / beat_duration

            # Quantize to expressible duration (prevents MusicXML errors)
            duration_beats = quantize_duration(duration_beats)

            # Create note
            n = note.Note()
            n.pitch.midi = item["pitch"]
            if item.get("is_quarter"):
                cents = item["cents_dev"]
                n.pitch.microtone = cents / 100.0
                if cents < -25:
                    n.pitch.accidental = m21_pitch.Accidental("quarter-flat")
                elif cents > 25:
                    n.pitch.accidental = m21_pitch.Accidental("quarter-sharp")
            n.quarterLength = duration_beats

            # Set velocity (amplitude → velocity)
            amplitude = item.get("amplitude", 0.7)
            n.volume.velocity = int(amplitude * 100)

            # Add dynamic marking if significant change
            if add_dynamics and should_add_dynamic(amplitude, previous_amplitude):
                dyn = amplitude_to_dynamic(amplitude)
                if dyn:
                    part.append(dyn)
                    dynamics_added += 1

            previous_amplitude = amplitude

            # Add the note
            part.append(n)
            current_offset += duration_beats

    score.append(part)

    # ── Step 7: Compile metadata ────────────────────────────────────────────
    score_metadata = {
        "original_note_count": len(notes),
        "final_note_count": sum(1 for n in notes_with_rests if n.get("type") != "rest"),
        "rest_count": sum(1 for n in notes_with_rests if n.get("type") == "rest"),
        "dynamics_added": dynamics_added,
        "key_signature": detected_key,
        "key_confidence": key_confidence,
        "tempo_bpm": tempo_bpm,
        "time_signature": time_signature,
        "duration_beats": current_offset,
        "duration_measures": current_offset / float(time_signature.split("/")[0]),
    }

    logger.info(
        f"Score created: {score_metadata['final_note_count']} notes, "
        f"{score_metadata['rest_count']} rests, key: {detected_key}"
    )

    return score, score_metadata


# ── Export Functions ────────────────────────────────────────────────────────


def export_musicxml(score: stream.Score, output_path: str) -> str:
    """
    Export music21 Score to MusicXML file.

    Args:
        score: music21 Score object
        output_path: Output file path (with .musicxml or .xml extension)

    Returns:
        Absolute path to the written file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure proper extension
    if output_path.suffix not in [".musicxml", ".xml"]:
        output_path = output_path.with_suffix(".musicxml")

    score.write("musicxml", fp=str(output_path))
    logger.info(f"MusicXML exported: {output_path}")

    return str(output_path.absolute())


def export_midi_from_score(score: stream.Score, output_path: str) -> str:
    """
    Export music21 Score to MIDI file (with proper notation timing).

    Args:
        score: music21 Score object
        output_path: Output file path

    Returns:
        Absolute path to the written file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix != ".mid":
        output_path = output_path.with_suffix(".mid")

    score.write("midi", fp=str(output_path))
    logger.info(f"MIDI exported from score: {output_path}")

    return str(output_path.absolute())


# ── High-Level Pipeline Function ────────────────────────────────────────────


def generate_sheet_music(
    notes: List[Dict[str, Any]],
    output_dir: str,
    job_id: str,
    tempo_bpm: float = 120.0,
    time_signature: str = "4/4",
    title: str = "Transcribed Melody",
    **kwargs,
) -> Dict[str, Any]:
    """
    Complete pipeline to generate sheet music files from notes.

    Args:
        notes: Quantized note list
        output_dir: Directory for output files
        job_id: Job identifier for filenames
        tempo_bpm: Tempo in BPM
        time_signature: Time signature string
        title: Piece title
        **kwargs: Additional arguments for notes_to_music21_score

    Returns:
        Dict with file paths and metadata
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate score
    score, metadata = notes_to_music21_score(
        notes, tempo_bpm=tempo_bpm, time_signature=time_signature, title=title, **kwargs
    )

    # Export files
    musicxml_path = export_musicxml(score, str(output_dir / f"sheet_{job_id}.musicxml"))
    midi_path = export_midi_from_score(score, str(output_dir / f"sheet_{job_id}.mid"))

    return {
        "musicxml_path": musicxml_path,
        "midi_path": midi_path,
        "metadata": metadata,
    }


# ── Section-Aware Sheet Music ────────────────────────────────────────────


def notes_to_music21_score_with_sections(
    sections: List[Dict[str, Any]],
    title: str = "Transcribed Melody",
    composer: str = "Songify",
) -> Tuple[stream.Score, Dict[str, Any]]:
    """
    Convert a list of section analyses into a single music21 Score with
    rehearsal marks and per-section tempo markings.

    Each section dict must have:
        - maqam (str)
        - bpm (float)
        - notes (List[Dict]) with pitch, start_time_s, duration_s, amplitude

    Args:
        sections: List of section analysis dicts.
        title: Piece title.
        composer: Composer name.

    Returns:
        Tuple of (music21 Score, metadata dict).
    """
    score = stream.Score()
    score.insert(0, m21metadata.Metadata())
    score.metadata.title = title
    score.metadata.composer = composer

    part = stream.Part()
    part.insert(0, instrument.Piano())
    part.insert(0, clef.TrebleClef())
    part.insert(0, meter.TimeSignature("4/4"))

    current_offset = 0.0
    total_notes = 0
    total_rests = 0

    for sec in sections:
        bpm = sec.get("bpm", 120.0)
        beat_duration = 60.0 / bpm
        section_notes = sec.get("notes", [])

        # Insert rehearsal mark with maqam label
        rehearsal = expressions.TextExpression(f"[{sec.get('maqam', 'Unknown')}]")
        rehearsal.style.absoluteY = 20
        part.insert(current_offset, rehearsal)

        # Insert metronome mark for this section
        part.insert(current_offset, tempo.MetronomeMark(number=bpm))

        # Process notes
        for item in section_notes:
            duration_s = item.get("duration_s", 0.5)
            duration_beats = duration_s / beat_duration
            duration_beats = quantize_duration(duration_beats)

            if item.get("type") == "rest" or item.get("pitch", 0) == 0:
                r = note.Rest()
                r.quarterLength = duration_beats
                part.insert(current_offset, r)
                total_rests += 1
            else:
                n = note.Note()
                n.pitch.midi = item["pitch"]
                if item.get("is_quarter"):
                    cents = item["cents_dev"]
                    n.pitch.microtone = cents / 100.0
                    if cents < -25:
                        n.pitch.accidental = m21_pitch.Accidental("quarter-flat")
                    elif cents > 25:
                        n.pitch.accidental = m21_pitch.Accidental("quarter-sharp")
                n.quarterLength = duration_beats
                amplitude = item.get("amplitude", 0.7)
                n.volume.velocity = int(amplitude * 100)
                part.insert(current_offset, n)
                total_notes += 1

            current_offset += duration_beats

    score.append(part)

    metadata = {
        "total_notes": total_notes,
        "total_rests": total_rests,
        "section_count": len(sections),
        "duration_beats": current_offset,
    }

    return score, metadata
