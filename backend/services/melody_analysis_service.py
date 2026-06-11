"""
Melody analysis service for intelligent transcription.

This service coordinates transcription of multiple stems and applies
vocal-guided melody extraction to produce simple, melody-focused output.
Enhanced with comprehensive tempo detection and note quantization.
"""

import io
import tempfile
import pretty_midi
import soundfile as sf
from typing import Dict, Any, List

from shared.logger import logger
from models.basic_pitch import BasicPitch
from utils.vocal_guided_melody import apply_vocal_guided_extraction
from utils.tempo_analysis import detect_comprehensive_tempo
from utils.note_quantization import quantize_notes_comprehensive
from basic_pitch.inference import predict


# Module-level singleton
_basic_pitch = BasicPitch()


def transcribe_stem_to_notes(
    audio_bytes: bytes, stem_name: str
) -> List[Dict[str, Any]]:
    """
    Transcribe a single audio stem to note events.

    Args:
        audio_bytes: Raw audio bytes
        stem_name: Name of stem (for logging)

    Returns:
        List of note dictionaries
    """
    if not _basic_pitch.health_check():
        raise RuntimeError("Basic Pitch model is not ready.")

    logger.info(f"Transcribing {stem_name}...")

    # Load audio
    waveform, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)

    # Resample to 44.1kHz if needed
    if sr != 44100:
        from scipy.signal import resample

        num_samples = int(len(waveform) * 44100 / sr)
        waveform = resample(waveform, num_samples, axis=0)
        sr = 44100

    # Convert to mono for transcription
    if waveform.shape[1] > 1:
        mono_audio = waveform.mean(axis=1)
    else:
        mono_audio = waveform[:, 0]

    # Save to temporary file for Basic Pitch
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name
        sf.write(temp_path, mono_audio, sr)

    try:
        # Basic Pitch inference - use our pre-loaded ONNX model
        model_output, midi_data, note_events = predict(
            temp_path, model_or_model_path=_basic_pitch.model
        )

        # Extract note information
        notes = []
        for note_event in note_events:
            start_time_s = float(note_event[0])
            end_time_s = float(note_event[1])
            pitch = int(note_event[2])
            amplitude = float(note_event[3])

            notes.append(
                {
                    "start_time_s": start_time_s,
                    "end_time_s": end_time_s,
                    "duration_s": end_time_s - start_time_s,
                    "pitch": int(pitch),
                    "amplitude": float(amplitude),
                }
            )

        logger.info(f"  {stem_name}: {len(notes)} notes detected")
        return notes

    finally:
        # Clean up temp file
        import os

        if os.path.exists(temp_path):
            os.remove(temp_path)


def analyze_and_extract_melody(
    vocals_audio: bytes,
    instruments_audio: bytes,
    keep_all_melody: bool = True,
    quantization_settings: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Analyze vocals and instruments to extract intelligent melody with enhanced processing.

    Args:
        vocals_audio: Vocal stem audio data
        instruments_audio: Instrumental stem audio data
        keep_all_melody: Whether to keep all melodic notes (True recommended)
        quantization_settings: Settings for note quantization

    Returns:
        Dict with melody notes, statistics, and tempo information
    """
    logger.info("=== Enhanced Melody Analysis Pipeline ===")

    # Step 1: Enhanced tempo detection
    logger.info("Step 1: Comprehensive tempo detection...")
    tempo_info = detect_comprehensive_tempo(instruments_audio)

    logger.info("Tempo analysis results:")
    logger.info(
        f"  BPM: {tempo_info['bpm']:.1f} (confidence: {tempo_info['confidence']:.2f})"
    )
    logger.info(f"  Stability: {'✓' if tempo_info['is_stable'] else '⚠'}")
    logger.info(f"  Time signature: {tempo_info['time_signature']}")

    # Step 2: Transcribe stems
    logger.info("Step 2: Transcribing audio stems...")
    vocal_notes = transcribe_stem_to_notes(vocals_audio, "vocals")
    instrument_notes = transcribe_stem_to_notes(instruments_audio, "instruments")

    # Step 3: Apply vocal-guided extraction
    logger.info("Step 3: Applying vocal-guided melody extraction...")
    vocal_guided_result = apply_vocal_guided_extraction(
        vocal_notes, instrument_notes, keep_all_melody=keep_all_melody
    )

    raw_melody_notes = vocal_guided_result["melody_notes"]
    logger.info(
        f"Vocal-guided extraction: {len(instrument_notes)} → {len(raw_melody_notes)} notes"
    )

    # Step 4: Enhanced quantization and musical filtering
    logger.info("Step 4: Note quantization and musical enhancement...")

    # Default quantization settings
    default_quantization = {
        "quantize_level": "sixteenth",
        "swing_feel": 0.0,
        "humanize_amount": 0.01,
        "velocity_smoothing": True,
        "remove_grace_notes": True,
        "merge_overlaps": True,
        "snap_threshold": 0.05,
        "min_note_gap": 0.01,
    }

    # Adapt settings based on tempo
    if tempo_info["bpm"] > 140:
        # Fast tempo - use eighth note grid
        default_quantization["quantize_level"] = "eighth"
        default_quantization["remove_grace_notes"] = True
    elif tempo_info["bpm"] < 80:
        # Slow tempo - allow thirty-second notes
        default_quantization["quantize_level"] = "thirty_second"
        default_quantization["remove_grace_notes"] = False

    final_settings = {**default_quantization, **(quantization_settings or {})}

    quantization_result = quantize_notes_comprehensive(
        raw_melody_notes, tempo_info, final_settings
    )

    final_melody_notes = quantization_result["quantized_notes"]
    quantization_stats = quantization_result["stats"]

    logger.info(
        f"Quantization complete: {len(raw_melody_notes)} → {len(final_melody_notes)} notes"
    )
    logger.info(
        f"  Musical quality score: {quantization_stats['musical_score']:.1f}/10"
    )

    # Step 5: Generate comprehensive statistics
    combined_stats = {
        **vocal_guided_result["stats"],
        "tempo_info": tempo_info,
        "quantization": quantization_stats,
        "final_quality_score": quantization_stats["musical_score"],
    }

    original_count = combined_stats["original_count"]
    final_count = len(final_melody_notes)
    total_reduction = (
        ((original_count - final_count) / original_count * 100)
        if original_count > 0
        else 0
    )
    combined_stats["total_reduction_pct"] = total_reduction

    logger.info("=== Melody Analysis Complete ===")
    logger.info(
        f"Overall pipeline: {original_count} → {final_count} notes ({total_reduction:.1f}% reduction)"
    )
    logger.info(
        f"Tempo: {tempo_info['bpm']:.1f} BPM ({'stable' if tempo_info['is_stable'] else 'variable'})"
    )
    logger.info(f"Quality: {quantization_stats['musical_score']:.1f}/10")

    return {
        "melody_notes": final_melody_notes,
        "stats": combined_stats,
        "tempo_bpm": tempo_info["bpm"],
        "tempo_info": tempo_info,
        "quantization_settings": final_settings,
    }


def notes_to_midi(
    notes: List[Dict[str, Any]], output_path: str, tempo_bpm: float = 120.0
) -> None:
    """
    Convert note events to MIDI file with enhanced timing and tempo information.

    Args:
        notes: List of note events with enhanced musical information
        output_path: Path to save MIDI file
        tempo_bpm: Tempo in BPM for MIDI timing
    """
    if not notes:
        logger.warning("No notes to convert to MIDI")
        # Create empty MIDI file
        midi = pretty_midi.PrettyMIDI(initial_tempo=tempo_bpm)
        instrument = pretty_midi.Instrument(program=0, name="Melody")
        midi.instruments.append(instrument)
        midi.write(output_path)
        return

    logger.info(f"Converting {len(notes)} notes to MIDI at {tempo_bpm:.1f} BPM...")

    # Create MIDI object with detected tempo
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo_bpm)

    # Create melody instrument (piano)
    instrument = pretty_midi.Instrument(program=0, name="Melody")  # Piano

    # Convert notes to MIDI
    for note_data in notes:
        start_time = note_data["start_time_s"]
        end_time = note_data.get("end_time_s", start_time + note_data["duration_s"])
        pitch = note_data["pitch"]

        # Convert amplitude to MIDI velocity (0-127)
        amplitude = note_data.get("amplitude", 0.8)
        velocity = max(1, min(127, int(amplitude * 100)))

        # Create MIDI note
        midi_note = pretty_midi.Note(
            velocity=velocity, pitch=pitch, start=start_time, end=end_time
        )

        instrument.notes.append(midi_note)

    midi.instruments.append(instrument)

    # Write MIDI file
    midi.write(output_path)
    logger.info(f"MIDI saved: {output_path}")


def enrich_notes_with_metadata(
    notes: List[Dict[str, Any]], metadata: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Enrich notes with additional metadata for JSON export.

    Args:
        notes: List of note events
        metadata: Additional metadata (tempo_info, etc.)

    Returns:
        Enriched notes with metadata
    """
    if metadata is None:
        metadata = {}

    enriched_notes = []

    for note in notes:
        enriched_note = note.copy()

        # Add metadata context
        enriched_note["metadata"] = {
            "tempo_bpm": metadata.get("tempo_bpm", 120),
            "tempo_stable": metadata.get("tempo_info", {}).get("is_stable", False),
            "quality_score": note.get("quality_score", 0.5),
            "quantized": note.get("quantized", False),
            "note_value": note.get("note_value", "quarter"),
            "musical_beat": note.get("beat_position", 1.0),
        }

        enriched_notes.append(enriched_note)

    return enriched_notes
