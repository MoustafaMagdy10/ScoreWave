import io
import os
import time
import uuid
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Any
from tqdm import tqdm

from basic_pitch.inference import predict

from models.basic_pitch import BasicPitch
from shared.logger import logger
from utils.melody_extractor import apply_melody_extraction, get_melody_stats


# ── Module-level singleton ─────────────────────────────────────────────────
_basic_pitch = BasicPitch()

# Basic Pitch expects 44.1kHz audio (or will resample internally)
DEFAULT_SAMPLE_RATE = 44100


def _bar(desc: str, total: int = 1, unit: str = "step") -> tqdm:
    return tqdm(
        total=total,
        desc=f"  {desc}",
        unit=unit,
        ncols=70,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit} [{elapsed}]",
        colour="green",
    )


def _load_audio_stereo_44k(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """
    Decode raw audio bytes → stereo float32 numpy array at 44.1kHz.
    Basic Pitch works best with 44.1kHz stereo audio.
    """
    waveform, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)

    # Convert mono to stereo if needed
    if waveform.shape[1] == 1:
        waveform = np.column_stack([waveform, waveform])

    # Resample to 44.1kHz if needed
    if sr != DEFAULT_SAMPLE_RATE:
        from scipy.signal import resample

        num_samples = int(len(waveform) * DEFAULT_SAMPLE_RATE / sr)
        waveform = resample(waveform, num_samples, axis=0)

    return waveform, DEFAULT_SAMPLE_RATE


def _note_event_to_dict(note_event: tuple) -> dict:
    """
    Convert a Basic Pitch NoteEvent tuple to a dictionary.

    NoteEvent tuple format: (start_time, end_time, pitch, amplitude, pitch_bends)
    - start_time: float (seconds)
    - end_time: float (seconds)
    - pitch: int (MIDI note number)
    - amplitude: float (0-1)
    - pitch_bends: Optional[List[int]] - pitch bend values
    """
    import numpy as np

    start_time, end_time, pitch, amplitude, pitch_bends = note_event

    def to_python_type(val):
        if isinstance(val, (np.integer, np.int64, np.int32)):
            return int(val)
        if isinstance(val, (np.floating, np.float64, np.float32)):
            return float(val)
        if isinstance(val, np.ndarray):
            return [int(x) for x in val.tolist()]
        if isinstance(val, list):
            return [to_python_type(x) for x in val]
        return val

    start_time = to_python_type(start_time)
    end_time = to_python_type(end_time)
    pitch = to_python_type(pitch)
    amplitude = to_python_type(amplitude)
    pitch_bends = to_python_type(pitch_bends) if pitch_bends else None

    return {
        "start_time_s": start_time,
        "end_time_s": end_time,
        "pitch": pitch,
        "frequency": _midi_to_frequency(pitch),
        "note": _midi_to_note_name(pitch),
        "amplitude": amplitude,
        "pitch_bends": pitch_bends,
    }


def _midi_to_note_name(midi_note: int) -> str:
    """Convert MIDI note number to note name (e.g., 60 -> C4)."""
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi_note // 12) - 1
    note_name = note_names[midi_note % 12]
    return f"{note_name}{octave}"


def _midi_to_frequency(midi_note: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def transcribe_to_midi(
    audio_bytes: bytes,
    output_dir: str,
    melody_only: bool = False,
    min_amplitude: float = 0.5,
    polyphony_limit: int = 1,
    min_note_duration: float = 0.1,
) -> dict[str, Any]:
    """
    Transcribe audio to MIDI using Basic Pitch with optional melody extraction.

    Uses default parameters optimized for general transcription:
    - onset_threshold: 0.5
    - frame_threshold: 0.3
    - minimum_note_length: 50ms

    Args:
        audio_bytes: Raw bytes of the audio file (MP3 / WAV / FLAC / M4A).
        output_dir: Directory where MIDI and JSON will be written.
        melody_only: If True, extract monophonic melody (1 note at a time)
        min_amplitude: Minimum amplitude threshold (0.0 to 1.0)
        polyphony_limit: Maximum simultaneous notes (1 = monophonic)
        min_note_duration: Minimum note duration in seconds

    Returns:
        Dict with:
            - midi_path: str - absolute path to the MIDI file
            - json_path: str - absolute path to the note events JSON
            - note_count: int - number of detected notes (after filtering)
            - duration_s: float - audio duration in seconds
            - melody_applied: bool - whether melody extraction was applied
            - melody_stats: dict - statistics about filtering (if applied)

    Raises:
        RuntimeError: If the model is not loaded or transcription fails.
    """
    if not _basic_pitch.health_check():
        raise RuntimeError("Basic Pitch model is not ready.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()
    print()
    logger.info("Starting transcription (Basic Pitch)")

    # ── 1. Decode audio ─────────────────────────────────────────────────────
    with _bar("Decoding audio      ") as bar:
        waveform, sample_rate = _load_audio_stereo_44k(audio_bytes)
        duration_s = len(waveform) / sample_rate
        bar.update(1)

    logger.info(
        f"  Audio: {duration_s:.1f}s | {sample_rate} Hz | {waveform.shape[1]}ch"
    )

    # ── 2. Save audio to temp WAV file for Basic Pitch ─────────────────────
    # Basic Pitch's predict() requires a file path, not raw bytes
    temp_audio_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, waveform, sample_rate)
            temp_audio_path = tmp.name

        # ── 3. Run Basic Pitch prediction ─────────────────────────────────────
        logger.info("Running Basic Pitch transcription...")

        with _bar("Transcribing         ") as bar:
            model_output, midi_data, note_events = predict(
                audio_path=temp_audio_path,
                model_or_model_path=_basic_pitch.model,
                onset_threshold=0.5,
                frame_threshold=0.3,
                minimum_note_length=50.0,
            )
            bar.update(1)
    finally:
        # Clean up temp file
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

    # ── 3. Save MIDI file ───────────────────────────────────────────────────
    job_id = str(uuid.uuid4())[:8]
    midi_filename = f"transcription_{job_id}.mid"
    midi_path = output_dir / midi_filename

    with _bar("Saving MIDI          ") as bar:
        midi_data.write(midi_path)
        bar.update(1)

    # ── 4. Convert note events to dict format ──────────────────────────────
    note_list_original = [_note_event_to_dict(n) for n in note_events]

    # ── 5. Apply melody extraction (if requested) ──────────────────────────
    melody_applied = melody_only or min_amplitude > 0.0 or polyphony_limit < 999
    melody_stats = None

    if melody_applied:
        with _bar("Extracting melody    ") as bar:
            note_list_filtered = apply_melody_extraction(
                note_list_original,
                melody_only=melody_only,
                min_amplitude=min_amplitude,
                polyphony_limit=polyphony_limit,
                min_note_duration=min_note_duration,
            )
            melody_stats = get_melody_stats(note_list_original, note_list_filtered)
            bar.update(1)

        logger.info(
            f"  Melody extraction: {melody_stats['original_note_count']} → "
            f"{melody_stats['filtered_note_count']} notes "
            f"({melody_stats['reduction_pct']:.1f}% reduction)"
        )

        # Use filtered notes for MIDI and JSON
        note_list_final = note_list_filtered

        # Recreate MIDI from filtered notes
        with _bar("Rebuilding MIDI      ") as bar:
            import pretty_midi

            midi_data_filtered = pretty_midi.PrettyMIDI()
            instrument = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano

            for note_dict in note_list_filtered:
                note_obj = pretty_midi.Note(
                    velocity=int(note_dict["amplitude"] * 127),
                    pitch=note_dict["pitch"],
                    start=note_dict["start_time_s"],
                    end=note_dict["end_time_s"],
                )
                instrument.notes.append(note_obj)

            midi_data_filtered.instruments.append(instrument)
            midi_data_filtered.write(midi_path)
            bar.update(1)
    else:
        note_list_final = note_list_original

    # ── 6. Save note events to JSON ─────────────────────────────────────────
    json_filename = f"transcription_{job_id}.json"
    json_path = output_dir / json_filename

    with _bar("Saving JSON          ") as bar:
        import json

        json_output = {
            "note_count": len(note_list_final),
            "duration_s": duration_s,
            "notes": note_list_final,
        }

        if melody_stats:
            json_output["melody_stats"] = melody_stats

        with open(json_path, "w") as f:
            json.dump(json_output, f, indent=2)
        bar.update(1)

    note_count = len(note_list_final)
    elapsed = time.time() - t_start
    print()
    logger.info(f"Transcription complete -- {note_count} notes in {elapsed:.1f}s")

    result = {
        "midi_path": str(midi_path),
        "json_path": str(json_path),
        "note_count": note_count,
        "duration_s": round(duration_s, 2),
        "melody_applied": melody_applied,
    }

    if melody_stats:
        result["melody_stats"] = melody_stats

    return result
