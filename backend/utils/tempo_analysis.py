"""
Enhanced tempo detection and analysis using librosa.

Provides accurate tempo detection, beat tracking, and onset detection
for better note quantization and timing analysis.
"""

import librosa
import numpy as np
import soundfile as sf
import io
from typing import Dict, List, Any
from shared.logger import logger


def detect_comprehensive_tempo(audio_bytes: bytes) -> Dict[str, Any]:
    """
    Comprehensive tempo detection using multiple librosa methods.

    Args:
        audio_bytes: Raw audio data

    Returns:
        Dict with tempo info:
        {
            'bpm': float,
            'confidence': float,
            'beat_times': List[float],
            'onset_times': List[float],
            'tempo_std': float,
            'time_signature': str,
            'is_stable': bool
        }
    """
    try:
        logger.info("Performing comprehensive tempo analysis...")

        # Load audio
        y, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if len(y.shape) > 1:
            y = y.mean(axis=1)  # Convert to mono

        # Ensure we have enough audio (minimum 5 seconds)
        min_samples = 5 * sr
        if len(y) < min_samples:
            logger.warning(f"Audio too short ({len(y) / sr:.1f}s), padding to 5s")
            y = np.pad(y, (0, max(0, min_samples - len(y))), mode="constant")

        # 1. Beat tracking with multiple methods
        logger.info("  Running beat tracking...")
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="time")

        # 2. Onset detection for rhythm analysis
        logger.info("  Detecting onsets...")
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="time")

        # 3. Tempo estimation with different approaches
        logger.info("  Multi-method tempo estimation...")

        # Method 1: Standard beat tracker
        tempo_1 = float(tempo)

        # Method 2: Onset-based tempo
        if len(onset_frames) > 10:
            onset_intervals = np.diff(onset_frames)
            # Filter out very short intervals (likely subdivisions)
            onset_intervals = onset_intervals[onset_intervals > 0.2]  # Min 300 BPM
            if len(onset_intervals) > 5:
                median_interval = np.median(onset_intervals)
                tempo_2 = 60.0 / median_interval
            else:
                tempo_2 = tempo_1
        else:
            tempo_2 = tempo_1

        # Method 3: Spectral-based tempo
        try:
            hop_length = 512
            S = librosa.stft(y, hop_length=hop_length)
            tempo_3, _ = librosa.beat.beat_track(
                S=np.abs(S), sr=sr, hop_length=hop_length
            )
            tempo_3 = float(tempo_3)
        except Exception as e:
            logger.warning(f"Spectral tempo estimation failed: {e}")
            tempo_3 = tempo_1

        # Combine tempo estimates
        tempos = np.array([tempo_1, tempo_2, tempo_3])
        # Remove outliers (more than 50% different from median)
        median_tempo = np.median(tempos)
        valid_tempos = tempos[np.abs(tempos - median_tempo) < median_tempo * 0.5]

        if len(valid_tempos) > 0:
            final_tempo = np.mean(valid_tempos)
            tempo_std = np.std(valid_tempos)
            confidence = max(0.1, 1.0 - (tempo_std / final_tempo))
        else:
            final_tempo = median_tempo
            tempo_std = np.std(tempos)
            confidence = 0.5

        # 4. Time signature estimation (basic)
        if len(beat_frames) > 8:
            # Look at beat strength patterns — simple 4/4 vs 3/4 detection
            time_sig = "4/4"  # Default, could be enhanced
        else:
            time_sig = "4/4"

        # 5. Stability check
        is_stable = tempo_std < final_tempo * 0.1 and confidence > 0.6

        result = {
            "bpm": final_tempo,
            "confidence": confidence,
            "beat_times": beat_frames.tolist(),
            "onset_times": onset_frames.tolist(),
            "tempo_std": tempo_std,
            "time_signature": time_sig,
            "is_stable": is_stable,
            "methods": {
                "beat_tracker": tempo_1,
                "onset_based": tempo_2,
                "spectral": tempo_3,
            },
        }

        logger.info(
            f"  Final tempo: {final_tempo:.1f} BPM (confidence: {confidence:.2f})"
        )
        logger.info(f"  Stability: {'✓' if is_stable else '⚠'} (std: {tempo_std:.1f})")
        logger.info(f"  Beat frames: {len(beat_frames)}, Onsets: {len(onset_frames)}")

        return result

    except Exception as e:
        logger.error(f"Tempo detection failed: {e}")
        return {
            "bpm": 120.0,
            "confidence": 0.1,
            "beat_times": [],
            "onset_times": [],
            "tempo_std": 0.0,
            "time_signature": "4/4",
            "is_stable": False,
            "methods": {},
        }


def quantize_notes_to_tempo(
    notes: List[Dict[str, Any]],
    tempo_info: Dict[str, Any],
    quantize_level: str = "sixteenth",
) -> List[Dict[str, Any]]:
    """
    Quantize note timings to musical grid based on detected tempo.

    Args:
        notes: List of note events with start_time_s, duration_s, pitch, amplitude
        tempo_info: Result from detect_comprehensive_tempo()
        quantize_level: "quarter", "eighth", "sixteenth", "thirty_second"

    Returns:
        Quantized notes with corrected timings
    """
    if not notes or tempo_info["bpm"] <= 0:
        return notes

    logger.info(
        f"Quantizing {len(notes)} notes to {quantize_level} note grid at {tempo_info['bpm']:.1f} BPM"
    )

    # Calculate quantization grid
    bpm = tempo_info["bpm"]
    beat_duration = 60.0 / bpm  # Duration of one quarter note in seconds

    # Quantization levels (fractions of a beat)
    quantize_divisions = {
        "quarter": 1.0,  # Quarter notes
        "eighth": 0.5,  # Eighth notes
        "sixteenth": 0.25,  # Sixteenth notes
        "thirty_second": 0.125,  # Thirty-second notes
    }

    division = quantize_divisions.get(quantize_level, 0.25)
    grid_size = beat_duration * division

    logger.info(f"  Grid size: {grid_size:.3f}s ({quantize_level} notes)")

    quantized_notes = []

    for note in notes:
        start_time = note["start_time_s"]
        duration = note.get("duration_s", 0.1)

        # Quantize start time to nearest grid point
        grid_start = round(start_time / grid_size) * grid_size

        # Quantize duration to musical values
        min_duration = grid_size  # Minimum: one grid unit
        quantized_duration = max(min_duration, round(duration / grid_size) * grid_size)

        # Avoid negative times
        grid_start = max(0.0, grid_start)

        quantized_note = note.copy()
        quantized_note["start_time_s"] = grid_start
        quantized_note["duration_s"] = quantized_duration
        quantized_note["end_time_s"] = grid_start + quantized_duration

        # Add quantization info
        quantized_note["quantized"] = True
        quantized_note["original_start"] = start_time
        quantized_note["original_duration"] = duration
        quantized_note["timing_adjustment"] = abs(grid_start - start_time)

        quantized_notes.append(quantized_note)

    # Sort by quantized start time
    quantized_notes.sort(key=lambda n: n["start_time_s"])

    # Calculate statistics
    total_adjustments = sum(n["timing_adjustment"] for n in quantized_notes)
    avg_adjustment = total_adjustments / len(quantized_notes) if quantized_notes else 0

    logger.info(f"  Average timing adjustment: {avg_adjustment:.3f}s")
    logger.info(f"  Quantized notes: {len(quantized_notes)}")

    return quantized_notes


def filter_notes_by_musical_rules(
    notes: List[Dict[str, Any]], tempo_info: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Apply musical rules to filter out unlikely or problematic notes.

    Args:
        notes: Quantized notes
        tempo_info: Tempo analysis result

    Returns:
        Filtered notes
    """
    if not notes:
        return notes

    logger.info(f"Applying musical filtering to {len(notes)} notes...")

    bpm = tempo_info["bpm"]
    beat_duration = 60.0 / bpm

    filtered_notes = []

    for i, note in enumerate(notes):
        keep_note = True
        filter_reasons = []

        # Rule 1: Minimum duration (32nd note at current tempo)
        min_duration = beat_duration * 0.125  # 32nd note
        if note["duration_s"] < min_duration:
            keep_note = False
            filter_reasons.append("too_short")

        # Rule 2: Maximum duration (4 beats)
        max_duration = beat_duration * 4.0
        if note["duration_s"] > max_duration:
            # Trim instead of removing
            note["duration_s"] = max_duration
            note["end_time_s"] = note["start_time_s"] + max_duration
            filter_reasons.append("trimmed_long")

        # Rule 3: Remove notes that are too quiet compared to surrounding notes
        if i > 0 and i < len(notes) - 1:
            prev_amp = notes[i - 1]["amplitude"]
            next_amp = notes[i + 1]["amplitude"]
            current_amp = note["amplitude"]
            avg_surrounding = (prev_amp + next_amp) / 2

            if current_amp < avg_surrounding * 0.3:  # Less than 30% of surrounding
                keep_note = False
                filter_reasons.append("too_quiet")

        # Rule 4: Remove rapid repetitions of same pitch (likely artifacts)
        if i > 0:
            prev_note = notes[i - 1]
            time_gap = note["start_time_s"] - prev_note["start_time_s"]
            pitch_same = note["pitch"] == prev_note["pitch"]

            if pitch_same and time_gap < min_duration * 2:
                # Keep the louder one
                if note["amplitude"] <= prev_note["amplitude"]:
                    keep_note = False
                    filter_reasons.append("rapid_repeat")
                else:
                    # Remove previous note instead
                    if filtered_notes:
                        filtered_notes.pop()

        # Rule 5: Amplitude threshold (dynamic based on overall level)
        if notes:
            amplitudes = [n["amplitude"] for n in notes]
            median_amp = np.median(amplitudes)
            if note["amplitude"] < median_amp * 0.2:  # Less than 20% of median
                keep_note = False
                filter_reasons.append("low_amplitude")

        if keep_note:
            filtered_notes.append(note)
        elif filter_reasons:
            logger.debug(
                f"  Filtered note at {note['start_time_s']:.2f}s: {', '.join(filter_reasons)}"
            )

    # Final pass: smooth out timing inconsistencies
    if len(filtered_notes) > 1:
        smoothed_notes = []
        for i, note in enumerate(filtered_notes):
            if i > 0:
                # Ensure no negative gaps between notes
                prev_end = smoothed_notes[-1]["end_time_s"]
                if note["start_time_s"] < prev_end:
                    # Adjust start time to avoid overlap
                    note["start_time_s"] = prev_end + 0.001
                    note["end_time_s"] = note["start_time_s"] + note["duration_s"]

            smoothed_notes.append(note)
        filtered_notes = smoothed_notes

    reduction_pct = (
        ((len(notes) - len(filtered_notes)) / len(notes) * 100) if notes else 0
    )
    logger.info(
        f"  Musical filtering: {len(notes)} → {len(filtered_notes)} notes ({reduction_pct:.1f}% reduction)"
    )

    return filtered_notes


def enhance_notes_with_tempo_info(
    notes: List[Dict[str, Any]], tempo_info: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Add musical timing information to notes based on tempo analysis.

    Args:
        notes: List of note events
        tempo_info: Tempo detection result

    Returns:
        Notes enhanced with musical timing info
    """
    if not notes or tempo_info["bpm"] <= 0:
        return notes

    bpm = tempo_info["bpm"]
    beat_duration = 60.0 / bpm
    beat_times = tempo_info.get("beat_times", [])

    enhanced_notes = []

    for note in notes:
        enhanced_note = note.copy()

        # Calculate musical position
        start_time = note["start_time_s"]

        # Find nearest beat
        if beat_times:
            beat_distances = [abs(start_time - bt) for bt in beat_times]
            nearest_beat_idx = np.argmin(beat_distances)
            nearest_beat_time = beat_times[nearest_beat_idx]

            # Calculate beat position (e.g., beat 1.25 = quarter note + sixteenth)
            beats_from_start = start_time / beat_duration
            beat_number = int(beats_from_start) + 1
            beat_fraction = beats_from_start % 1.0

            enhanced_note["musical_beat"] = beat_number
            enhanced_note["beat_fraction"] = beat_fraction
            enhanced_note["nearest_beat_time"] = nearest_beat_time
            enhanced_note["beat_distance"] = abs(start_time - nearest_beat_time)

        # Calculate note value based on duration
        duration_beats = note["duration_s"] / beat_duration

        # Classify note length
        if duration_beats >= 3.5:
            note_type = "whole"
        elif duration_beats >= 1.5:
            note_type = "half"
        elif duration_beats >= 0.75:
            note_type = "quarter"
        elif duration_beats >= 0.375:
            note_type = "eighth"
        elif duration_beats >= 0.1875:
            note_type = "sixteenth"
        else:
            note_type = "thirty_second"

        enhanced_note["note_type"] = note_type
        enhanced_note["duration_beats"] = duration_beats
        enhanced_note["bpm_context"] = bpm

        enhanced_notes.append(enhanced_note)

    return enhanced_notes
