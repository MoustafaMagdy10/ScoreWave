"""
Advanced note quantization and musical filtering system.

Provides intelligent note timing correction, duration normalization,
and musical quality improvements based on tempo analysis.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from shared.logger import logger


def quantize_notes_comprehensive(
    notes: List[Dict[str, Any]],
    tempo_info: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Comprehensive note quantization with multiple quality improvements.

    Args:
        notes: Raw note events
        tempo_info: Tempo analysis from tempo_analysis.detect_comprehensive_tempo()
        settings: Quantization settings

    Returns:
        Dict with quantized notes and statistics
    """
    if not notes:
        return {"quantized_notes": [], "stats": {"original_count": 0, "final_count": 0}}

    # Default settings
    default_settings = {
        "quantize_level": "sixteenth",  # sixteenth, eighth, quarter
        "swing_feel": 0.0,  # 0.0 = straight, 0.67 = full swing
        "humanize_amount": 0.02,  # Slight timing variations (seconds)
        "velocity_smoothing": True,  # Smooth amplitude variations
        "remove_grace_notes": True,  # Remove very short ornamental notes
        "merge_overlaps": True,  # Merge overlapping notes of same pitch
        "snap_threshold": 0.05,  # Max time adjustment for snapping (seconds)
        "min_note_gap": 0.01,  # Minimum gap between consecutive notes
    }

    settings = {**default_settings, **(settings or {})}

    logger.info(
        f"Comprehensive quantization: {len(notes)} notes at {tempo_info['bpm']:.1f} BPM"
    )
    logger.info(
        f"  Settings: {settings['quantize_level']} grid, swing={settings['swing_feel']:.2f}"
    )

    original_count = len(notes)

    # Phase 1: Pre-processing
    logger.info("Phase 1: Pre-processing...")
    processed_notes = _preprocess_notes(notes, tempo_info, settings)

    # Phase 2: Tempo-based quantization
    logger.info("Phase 2: Tempo-based quantization...")
    quantized_notes = _quantize_to_musical_grid(processed_notes, tempo_info, settings)

    # Phase 3: Musical filtering and cleanup
    logger.info("Phase 3: Musical filtering...")
    filtered_notes = _apply_musical_filters(quantized_notes, tempo_info, settings)

    # Phase 4: Post-processing refinements
    logger.info("Phase 4: Post-processing refinements...")
    final_notes = _postprocess_notes(filtered_notes, tempo_info, settings)

    # Calculate statistics
    stats = _calculate_quantization_stats(notes, final_notes, tempo_info)

    logger.info(f"Quantization complete: {original_count} → {len(final_notes)} notes")
    logger.info(f"  Timing accuracy: {stats['timing_improvement']:.1f}% better")
    logger.info(f"  Musical quality: {stats['musical_score']:.1f}/10")

    return {"quantized_notes": final_notes, "stats": stats, "settings_used": settings}


def _preprocess_notes(
    notes: List[Dict[str, Any]], tempo_info: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Phase 1: Clean up and prepare notes for quantization."""

    processed = []

    for note in notes:
        # Ensure required fields
        note = note.copy()
        note.setdefault("duration_s", 0.1)
        note.setdefault("amplitude", 0.5)
        note.setdefault("end_time_s", note["start_time_s"] + note["duration_s"])

        # Remove extremely short notes (grace notes) if requested
        min_duration = 60.0 / tempo_info["bpm"] * 0.0625  # 64th note
        if settings["remove_grace_notes"] and note["duration_s"] < min_duration:
            logger.debug(f"  Removed grace note at {note['start_time_s']:.3f}s")
            continue

        # Basic amplitude filtering (remove very quiet notes)
        if note["amplitude"] < 0.05:  # Less than 5% amplitude
            continue

        processed.append(note)

    # Sort by start time
    processed.sort(key=lambda n: n["start_time_s"])

    # Merge overlapping notes of same pitch if requested
    if settings["merge_overlaps"]:
        processed = _merge_overlapping_notes(processed)

    logger.info(f"  Pre-processing: {len(notes)} → {len(processed)} notes")
    return processed


def _merge_overlapping_notes(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge overlapping notes of the same pitch."""
    if len(notes) <= 1:
        return notes

    merged = []
    current_note = notes[0].copy()

    for next_note in notes[1:]:
        # Check if notes overlap and have same pitch
        if (
            next_note["pitch"] == current_note["pitch"]
            and next_note["start_time_s"] <= current_note["end_time_s"] + 0.01
        ):
            # Merge notes: extend duration and average amplitude
            new_end = max(current_note["end_time_s"], next_note["end_time_s"])
            total_duration = new_end - current_note["start_time_s"]

            # Weight amplitudes by duration
            current_weight = current_note["duration_s"]
            next_weight = next_note["duration_s"]
            total_weight = current_weight + next_weight

            if total_weight > 0:
                current_note["amplitude"] = (
                    current_note["amplitude"] * current_weight
                    + next_note["amplitude"] * next_weight
                ) / total_weight

            current_note["duration_s"] = total_duration
            current_note["end_time_s"] = new_end

        else:
            # No overlap, add current note and move to next
            merged.append(current_note)
            current_note = next_note.copy()

    # Add the last note
    merged.append(current_note)

    return merged


def _quantize_to_musical_grid(
    notes: List[Dict[str, Any]], tempo_info: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Phase 2: Snap notes to musical timing grid."""

    bpm = tempo_info["bpm"]
    beat_duration = 60.0 / bpm

    # Define grid sizes
    grid_divisions = {
        "quarter": 1.0,
        "eighth": 0.5,
        "sixteenth": 0.25,
        "thirty_second": 0.125,
    }

    division = grid_divisions[settings["quantize_level"]]
    grid_size = beat_duration * division
    swing_amount = settings["swing_feel"]
    snap_threshold = settings["snap_threshold"]

    logger.info(f"  Grid size: {grid_size:.3f}s ({settings['quantize_level']} notes)")

    quantized = []

    for note in notes:
        quantized_note = note.copy()

        start_time = note["start_time_s"]
        duration = note["duration_s"]

        # Find nearest grid points
        grid_position = start_time / grid_size
        lower_grid = int(grid_position) * grid_size
        upper_grid = (int(grid_position) + 1) * grid_size

        # Choose closest grid point
        if abs(start_time - lower_grid) <= abs(start_time - upper_grid):
            target_grid = lower_grid
        else:
            target_grid = upper_grid

        # Apply swing timing if requested
        if swing_amount > 0 and settings["quantize_level"] in ["eighth", "sixteenth"]:
            # Apply swing to off-beats
            beat_position = (target_grid / beat_duration) % 1.0

            if settings["quantize_level"] == "eighth":
                # Swing eighth notes
                if abs(beat_position - 0.5) < 0.1:  # Second eighth note
                    swing_offset = grid_size * swing_amount * 0.33
                    target_grid += swing_offset
            elif settings["quantize_level"] == "sixteenth":
                # Swing sixteenth notes
                if abs(beat_position - 0.25) < 0.05 or abs(beat_position - 0.75) < 0.05:
                    swing_offset = grid_size * swing_amount * 0.2
                    target_grid += swing_offset

        # Only snap if within threshold
        if abs(start_time - target_grid) <= snap_threshold:
            quantized_note["start_time_s"] = max(0, target_grid)
            quantized_note["timing_adjusted"] = True
            quantized_note["adjustment_amount"] = abs(start_time - target_grid)
        else:
            quantized_note["timing_adjusted"] = False
            quantized_note["adjustment_amount"] = 0

        # Quantize duration to musical values
        duration_grids = round(duration / grid_size)
        quantized_duration = max(
            grid_size, duration_grids * grid_size
        )  # Minimum one grid unit

        quantized_note["duration_s"] = quantized_duration
        quantized_note["end_time_s"] = (
            quantized_note["start_time_s"] + quantized_duration
        )

        # Add humanization (slight random timing variations)
        if settings["humanize_amount"] > 0:
            humanize_offset = np.random.uniform(
                -settings["humanize_amount"], settings["humanize_amount"]
            )
            quantized_note["start_time_s"] = max(
                0, quantized_note["start_time_s"] + humanize_offset
            )
            quantized_note["end_time_s"] = (
                quantized_note["start_time_s"] + quantized_note["duration_s"]
            )

        quantized.append(quantized_note)

    # Sort by quantized start time
    quantized.sort(key=lambda n: n["start_time_s"])

    # Calculate timing statistics
    adjusted_count = sum(1 for n in quantized if n["timing_adjusted"])
    avg_adjustment = (
        np.mean([n["adjustment_amount"] for n in quantized if n["timing_adjusted"]])
        if adjusted_count > 0
        else 0
    )

    logger.info(
        f"  Quantized {adjusted_count}/{len(quantized)} notes (avg adjustment: {avg_adjustment:.3f}s)"
    )

    return quantized


def _apply_musical_filters(
    notes: List[Dict[str, Any]], tempo_info: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Phase 3: Apply musical rules and quality filters."""

    if not notes:
        return notes

    bpm = tempo_info["bpm"]
    beat_duration = 60.0 / bpm
    min_gap = settings["min_note_gap"]

    filtered = []

    for i, note in enumerate(notes):
        keep_note = True
        reasons = []

        # Filter 1: Minimum duration (32nd note)
        min_duration = beat_duration * 0.125
        if note["duration_s"] < min_duration * 0.8:  # 80% of 32nd note
            keep_note = False
            reasons.append("too_short")

        # Filter 2: Maximum duration (whole note + half)
        max_duration = beat_duration * 6.0
        if note["duration_s"] > max_duration:
            note["duration_s"] = max_duration
            note["end_time_s"] = note["start_time_s"] + max_duration
            reasons.append("trimmed")

        # Filter 3: Amplitude relative to local context
        if i >= 2 and i < len(notes) - 2:
            # Check amplitude against 4-note neighborhood
            neighborhood = [
                notes[j]["amplitude"] for j in range(i - 2, i + 3) if j != i
            ]
            median_local_amp = np.median(neighborhood)

            if note["amplitude"] < median_local_amp * 0.25:
                keep_note = False
                reasons.append("quiet_outlier")

        # Filter 4: Prevent rapid repetitions (likely artifacts)
        if i > 0:
            prev_note = filtered[-1] if filtered else notes[i - 1]
            time_gap = note["start_time_s"] - prev_note["end_time_s"]
            same_pitch = note["pitch"] == prev_note["pitch"]

            if same_pitch and time_gap < min_gap:
                # Keep the note with better "quality score"
                prev_score = prev_note["amplitude"] * prev_note["duration_s"]
                current_score = note["amplitude"] * note["duration_s"]

                if current_score <= prev_score:
                    keep_note = False
                    reasons.append("rapid_repeat")
                else:
                    # Replace previous note
                    if filtered:
                        filtered.pop()

        # Filter 5: Musical interval validation (basic)
        if i > 0 and keep_note:
            prev_pitch = filtered[-1]["pitch"] if filtered else notes[i - 1]["pitch"]
            interval = abs(note["pitch"] - prev_pitch)

            # Flag very large jumps (over 2 octaves) as potentially problematic
            if interval > 24:  # 2 octaves
                # Don't remove, just mark for attention
                note["large_interval"] = True
                reasons.append("large_jump")

        if keep_note:
            # Apply velocity smoothing if requested
            if settings["velocity_smoothing"] and filtered:
                # Simple smoothing with previous note
                prev_amp = filtered[-1]["amplitude"]
                smoothing_factor = 0.3
                note["amplitude"] = (
                    note["amplitude"] * (1 - smoothing_factor)
                    + prev_amp * smoothing_factor
                )
                note["velocity_smoothed"] = True

            filtered.append(note)

        if reasons:
            logger.debug(
                f"  Note {i} at {note['start_time_s']:.2f}s: {', '.join(reasons)}"
            )

    # Final pass: ensure minimum gaps between notes
    if len(filtered) > 1:
        gapped_notes = []
        for i, note in enumerate(filtered):
            if i > 0:
                prev_end = gapped_notes[-1]["end_time_s"]
                gap = note["start_time_s"] - prev_end

                if gap < min_gap:
                    # Adjust start time to create minimum gap
                    note["start_time_s"] = prev_end + min_gap
                    note["end_time_s"] = note["start_time_s"] + note["duration_s"]
                    note["gap_adjusted"] = True

            gapped_notes.append(note)
        filtered = gapped_notes

    reduction_pct = ((len(notes) - len(filtered)) / len(notes) * 100) if notes else 0
    logger.info(
        f"  Musical filtering: {len(notes)} → {len(filtered)} notes ({reduction_pct:.1f}% reduction)"
    )

    return filtered


def _postprocess_notes(
    notes: List[Dict[str, Any]], tempo_info: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Phase 4: Final refinements and enhancements."""

    if not notes:
        return notes

    # Add musical context information
    enhanced_notes = []
    bpm = tempo_info["bpm"]
    beat_duration = 60.0 / bpm

    for i, note in enumerate(notes):
        enhanced_note = note.copy()

        # Calculate musical position
        beats_from_start = note["start_time_s"] / beat_duration
        measure_length = 4.0  # Assume 4/4 time for now

        enhanced_note["beat_position"] = (beats_from_start % measure_length) + 1
        enhanced_note["measure_number"] = int(beats_from_start / measure_length) + 1

        # Classify note value
        duration_beats = note["duration_s"] / beat_duration
        enhanced_note["duration_beats"] = duration_beats

        if duration_beats >= 3.5:
            note_value = "whole"
        elif duration_beats >= 1.5:
            note_value = "half"
        elif duration_beats >= 0.75:
            note_value = "quarter"
        elif duration_beats >= 0.375:
            note_value = "eighth"
        elif duration_beats >= 0.1875:
            note_value = "sixteenth"
        else:
            note_value = "thirty_second"

        enhanced_note["note_value"] = note_value

        # Calculate note strength based on position
        beat_pos = enhanced_note["beat_position"]
        if abs(beat_pos - 1.0) < 0.1 or abs(beat_pos - 3.0) < 0.1:
            strength = "strong"  # Beats 1 and 3
        elif abs(beat_pos - 2.0) < 0.1 or abs(beat_pos - 4.0) < 0.1:
            strength = "medium"  # Beats 2 and 4
        else:
            strength = "weak"  # Off-beats

        enhanced_note["metric_strength"] = strength

        # Add quality score
        quality_factors = []

        # Timing accuracy
        if enhanced_note.get("timing_adjusted", False):
            timing_score = max(0, 1.0 - enhanced_note.get("adjustment_amount", 0) * 10)
            quality_factors.append(timing_score)
        else:
            quality_factors.append(0.8)  # Good if no adjustment needed

        # Duration appropriateness
        if note_value in ["quarter", "eighth", "sixteenth"]:
            quality_factors.append(1.0)  # Standard note values
        else:
            quality_factors.append(0.7)  # Less common

        # Amplitude consistency
        if enhanced_note.get("velocity_smoothed", False):
            quality_factors.append(0.9)
        else:
            quality_factors.append(0.8)

        enhanced_note["quality_score"] = np.mean(quality_factors)

        enhanced_notes.append(enhanced_note)

    logger.info(f"  Post-processing complete: {len(enhanced_notes)} notes enhanced")

    return enhanced_notes


def _calculate_quantization_stats(
    original_notes: List[Dict[str, Any]],
    quantized_notes: List[Dict[str, Any]],
    tempo_info: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate comprehensive statistics for quantization results."""

    if not original_notes or not quantized_notes:
        return {
            "original_count": len(original_notes),
            "final_count": len(quantized_notes),
            "reduction_pct": 0.0,
            "timing_improvement": 0.0,
            "musical_score": 0.0,
        }

    # Basic counts
    original_count = len(original_notes)
    final_count = len(quantized_notes)
    reduction_pct = (
        ((original_count - final_count) / original_count * 100)
        if original_count > 0
        else 0
    )

    # Timing improvement estimation
    adjusted_notes = [n for n in quantized_notes if n.get("timing_adjusted", False)]
    timing_improvement = (
        (len(adjusted_notes) / final_count * 100) if final_count > 0 else 0
    )

    # Musical quality score (0-10)
    if quantized_notes:
        quality_scores = [n.get("quality_score", 0.5) for n in quantized_notes]
        musical_score = np.mean(quality_scores) * 10
    else:
        musical_score = 0.0

    # Note distribution analysis
    note_values = {}
    for note in quantized_notes:
        note_value = note.get("note_value", "unknown")
        note_values[note_value] = note_values.get(note_value, 0) + 1

    # Tempo stability
    tempo_confidence = tempo_info.get("confidence", 0.5)

    return {
        "original_count": original_count,
        "final_count": final_count,
        "reduction_pct": reduction_pct,
        "timing_improvement": timing_improvement,
        "musical_score": musical_score,
        "tempo_confidence": tempo_confidence,
        "note_distribution": note_values,
        "adjusted_notes": len(adjusted_notes),
        "avg_quality": musical_score / 10.0,
    }
