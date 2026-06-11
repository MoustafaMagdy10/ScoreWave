"""
Enhanced MIDI export with microtonal support using pitch bend.

This module provides MIDI generation that can represent quarter tones
and other microtonal intervals using pitch bend events.
"""

import pretty_midi
import numpy as np
from typing import List, Dict, Any

from shared.logger import logger


def cents_to_pitch_bend(cents: float, pitch_bend_range: int = 2) -> int:
    """
    Convert cents deviation to MIDI pitch bend value.

    Args:
        cents: Deviation in cents from base note
        pitch_bend_range: Pitch bend range in semitones (default: 2)

    Returns:
        MIDI pitch bend value (-8192 to 8191, center=0)
    """
    # MIDI pitch bend range: -8192 to 8191, center=0 (pretty_midi uses signed values)
    # Default range is ±2 semitones (200 cents)
    max_cents = pitch_bend_range * 100

    # Clamp cents to range
    cents = max(-max_cents, min(max_cents, cents))

    # Convert to pitch bend value
    bend_ratio = cents / max_cents
    pitch_bend = int(bend_ratio * 8192)  # ±8192 range

    return max(-8192, min(8191, pitch_bend))


def create_microtonal_midi(
    notes: List[Dict[str, Any]],
    output_path: str,
    tempo_bpm: float = 120.0,
    use_pitch_bend: bool = True,
    program: int = 0,
) -> str:
    """
    Create MIDI file with microtonal support using pitch bend.

    Args:
        notes: List of note events with microtonal information
        output_path: Path to save MIDI file
        tempo_bpm: Tempo in BPM
        use_pitch_bend: Whether to use pitch bend for quarter tones
        program: MIDI program (instrument) number

    Returns:
        Path to created MIDI file
    """
    if not notes:
        logger.warning("No notes to convert to microtonal MIDI")
        # Create empty MIDI file
        midi = pretty_midi.PrettyMIDI(initial_tempo=tempo_bpm)
        instrument = pretty_midi.Instrument(program=program, name="Microtonal Melody")
        midi.instruments.append(instrument)
        midi.write(output_path)
        return output_path

    logger.info(f"Creating microtonal MIDI with {len(notes)} notes...")
    logger.info(f"Pitch bend: {'enabled' if use_pitch_bend else 'disabled'}")

    # Create MIDI object
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo_bpm)

    # Create instrument
    instrument = pretty_midi.Instrument(program=program, name="Microtonal Melody")

    # Track pitch bend events
    pitch_bend_events = []

    # Sort notes by start time
    sorted_notes = sorted(notes, key=lambda n: n["start_time_s"])

    for note_data in sorted_notes:
        start_time = note_data["start_time_s"]
        end_time = note_data.get(
            "end_time_s", start_time + note_data.get("duration_s", 0.5)
        )

        # Get pitch information
        if "pitch" in note_data and isinstance(note_data["pitch"], float):
            # Microtonal pitch (fractional MIDI note)
            full_pitch = note_data["pitch"]
            base_pitch = int(full_pitch)
            pitch_fraction = full_pitch - base_pitch
            pitch_bend_cents = pitch_fraction * 100
        elif "pitch_bend_cents" in note_data:
            # Explicit pitch bend information
            base_pitch = note_data.get("midi_note_base", int(note_data["pitch"]))
            pitch_bend_cents = note_data["pitch_bend_cents"]
        else:
            # Standard MIDI note
            base_pitch = int(note_data["pitch"])
            pitch_bend_cents = 0

        # Create MIDI note with base pitch
        velocity = note_data.get("velocity", 80)
        if "amplitude" in note_data:
            velocity = max(1, min(127, int(note_data["amplitude"] * 100)))

        midi_note = pretty_midi.Note(
            velocity=velocity, pitch=base_pitch, start=start_time, end=end_time
        )

        instrument.notes.append(midi_note)

        # Add pitch bend if needed and enabled
        if use_pitch_bend and abs(pitch_bend_cents) > 5:  # 5 cent threshold
            pitch_bend_value = cents_to_pitch_bend(pitch_bend_cents)

            # Add pitch bend slightly before note start
            bend_start_time = max(0, start_time - 0.01)
            pitch_bend_events.append(
                {"time": bend_start_time, "pitch_bend": pitch_bend_value}
            )

            # Return to center after note (if this is a quarter tone)
            if abs(pitch_bend_cents - 50) < 10 or abs(pitch_bend_cents + 50) < 10:
                bend_end_time = end_time + 0.01
                pitch_bend_events.append(
                    {
                        "time": bend_end_time,
                        "pitch_bend": 0,  # Center (signed value)
                    }
                )

    # Sort and add pitch bend events
    if pitch_bend_events:
        pitch_bend_events.sort(key=lambda x: x["time"])

        for event in pitch_bend_events:
            # Create pitch bend control change
            pitch_bend = pretty_midi.PitchBend(
                pitch=event["pitch_bend"], time=event["time"]
            )
            instrument.pitch_bends.append(pitch_bend)

        logger.info(f"Added {len(pitch_bend_events)} pitch bend events")

    # Add instrument to MIDI
    midi.instruments.append(instrument)

    # Write MIDI file
    midi.write(output_path)

    quarter_tone_count = sum(
        1
        for n in notes
        if n.get("is_quarter_tone", False)
        or abs(n.get("pitch_bend_cents", 0) - 50) < 10
        or abs(n.get("pitch_bend_cents", 0) + 50) < 10
    )

    logger.info(f"Microtonal MIDI created: {output_path}")
    logger.info(f"Quarter-tone notes: {quarter_tone_count}/{len(notes)}")

    return output_path


def create_maqam_midi_template(
    maqam_name: str, root_midi: int = 60, output_path: str = None, octaves: int = 2
) -> str:
    """
    Create a MIDI template for a specific maqam scale.

    Args:
        maqam_name: Name of the maqam
        root_midi: MIDI note number for root
        output_path: Path to save template (if None, returns path only)
        octaves: Number of octaves to span

    Returns:
        Path where template would be/was saved
    """
    from utils.microtonal_analysis import MAQAMAT_SCALES, get_maqam_info

    if maqam_name not in MAQAMAT_SCALES:
        raise ValueError(f"Unknown maqam: {maqam_name}")

    if output_path is None:
        output_path = f"maqam_{maqam_name}_template.mid"

    # Get maqam scale
    maqam_info = get_maqam_info(maqam_name)
    scale_degrees = maqam_info["scale_degrees_cents"]

    # Create notes for the scale
    notes = []
    current_time = 0.0
    note_duration = 1.0  # 1 second per note

    for octave in range(octaves):
        for i, cents in enumerate(
            scale_degrees[:-1]
        ):  # Exclude octave to avoid duplication
            pitch_midi = root_midi + octave * 12 + (cents / 100.0)

            note = {
                "start_time_s": current_time,
                "end_time_s": current_time + note_duration,
                "duration_s": note_duration,
                "pitch": pitch_midi,
                "amplitude": 0.8,
                "velocity": 80,
                "is_quarter_tone": cents % 100 == 50,
                "pitch_bend_cents": (cents % 100) if cents % 100 != 0 else 0,
                "maqam_degree": i + 1,
            }

            notes.append(note)
            current_time += note_duration

    # Create MIDI file
    create_microtonal_midi(
        notes=notes,
        output_path=output_path,
        tempo_bpm=80,  # Slow tempo for template
        use_pitch_bend=True,
        program=0,  # Piano
    )

    logger.info(f"Created maqam template: {maqam_name} -> {output_path}")

    return output_path


def analyze_midi_microtonality(midi_path: str) -> Dict[str, Any]:
    """
    Analyze existing MIDI file for microtonal content.

    Args:
        midi_path: Path to MIDI file

    Returns:
        Dict with microtonality analysis
    """
    try:
        midi = pretty_midi.PrettyMIDI(midi_path)

        total_notes = 0
        total_pitch_bends = 0
        pitch_bend_ranges = []

        for instrument in midi.instruments:
            if instrument.is_drum:
                continue

            total_notes += len(instrument.notes)
            total_pitch_bends += len(instrument.pitch_bends)

            if instrument.pitch_bends:
                # Analyze pitch bend ranges
                bend_values = [pb.pitch for pb in instrument.pitch_bends]
                pitch_bend_ranges.extend(bend_values)

        # Analyze pitch bend usage
        has_pitch_bends = total_pitch_bends > 0
        microtonal_likely = False

        if has_pitch_bends:
            bend_array = np.array(pitch_bend_ranges)
            # Check if pitch bends are used for microtonality (not just vibrato/expression)
            # Quarter tones would be around ±2048 bend values from center (0)
            significant_bends = np.abs(bend_array) > 1000  # Significant deviation
            microtonal_likely = np.sum(significant_bends) > (len(bend_array) * 0.1)

        return {
            "total_notes": total_notes,
            "total_pitch_bends": total_pitch_bends,
            "has_pitch_bends": has_pitch_bends,
            "microtonal_likely": microtonal_likely,
            "pitch_bend_stats": {
                "min_bend": int(np.min(pitch_bend_ranges)) if pitch_bend_ranges else 0,
                "max_bend": int(np.max(pitch_bend_ranges)) if pitch_bend_ranges else 0,
                "mean_bend": float(np.mean(pitch_bend_ranges))
                if pitch_bend_ranges
                else 0,
                "std_bend": float(np.std(pitch_bend_ranges))
                if pitch_bend_ranges
                else 0,
            },
        }

    except Exception as e:
        logger.error(f"MIDI microtonality analysis failed: {e}")
        return {"error": str(e), "analysis_failed": True}


def validate_microtonal_support(
    test_output_dir: str = "tmp/microtonal_test",
) -> Dict[str, Any]:
    """
    Test microtonal MIDI generation capabilities.

    Args:
        test_output_dir: Directory for test files

    Returns:
        Dict with validation results
    """
    import os

    os.makedirs(test_output_dir, exist_ok=True)

    logger.info("Testing microtonal MIDI capabilities...")

    # Test quarter-tone scale
    test_notes = []
    for i in range(8):
        # Create ascending quarter-tone scale
        pitch = 60 + (i * 0.5)  # C4 + quarter tones
        note = {
            "start_time_s": i * 0.5,
            "end_time_s": (i * 0.5) + 0.4,
            "duration_s": 0.4,
            "pitch": pitch,
            "amplitude": 0.8,
            "is_quarter_tone": (i % 2) == 1,
            "pitch_bend_cents": 50 if (i % 2) == 1 else 0,
        }
        test_notes.append(note)

    # Test regular MIDI
    regular_path = os.path.join(test_output_dir, "test_regular.mid")
    try:
        create_microtonal_midi(
            notes=[
                {**n, "pitch": int(n["pitch"])} for n in test_notes
            ],  # Round to integers
            output_path=regular_path,
            use_pitch_bend=False,
        )
        regular_success = os.path.exists(regular_path)
    except Exception as e:
        logger.error(f"Regular MIDI test failed: {e}")
        regular_success = False

    # Test microtonal MIDI
    microtonal_path = os.path.join(test_output_dir, "test_microtonal.mid")
    try:
        create_microtonal_midi(
            notes=test_notes, output_path=microtonal_path, use_pitch_bend=True
        )
        microtonal_success = os.path.exists(microtonal_path)
    except Exception as e:
        logger.error(f"Microtonal MIDI test failed: {e}")
        microtonal_success = False

    # Test maqam template
    maqam_path = os.path.join(test_output_dir, "test_maqam_rast.mid")
    try:
        create_maqam_midi_template(maqam_name="rast", output_path=maqam_path)
        maqam_success = os.path.exists(maqam_path)
    except Exception as e:
        logger.error(f"Maqam template test failed: {e}")
        maqam_success = False

    logger.info("Microtonal MIDI validation complete")

    return {
        "validation_passed": regular_success and microtonal_success and maqam_success,
        "regular_midi_support": regular_success,
        "microtonal_midi_support": microtonal_success,
        "maqam_template_support": maqam_success,
        "test_files_created": [
            f for f in [regular_path, microtonal_path, maqam_path] if os.path.exists(f)
        ],
    }
