"""
Melody analysis service for intelligent transcription.

This service coordinates transcription of multiple stems and applies
vocal-guided melody extraction to produce simple, melody-focused output.
"""

import io
import tempfile
import pretty_midi
import soundfile as sf
from typing import Dict, Any, List

from shared.logger import logger
from models.basic_pitch import BasicPitch
from utils.vocal_guided_melody import apply_vocal_guided_extraction
from basic_pitch.inference import predict


# Module-level singleton
_basic_pitch = BasicPitch()


def transcribe_stem_to_notes(
    audio_bytes: bytes,
    stem_name: str
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
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, waveform, sr)
        temp_path = tmp.name
    
    try:
        # Run Basic Pitch
        model_output, midi_data, note_events = predict(
            audio_path=temp_path,
            model_or_model_path=_basic_pitch.model,
            onset_threshold=0.5,
            frame_threshold=0.3,
            minimum_note_length=50.0,
        )
        
        # Convert to dict format
        notes = []
        for ne in note_events:
            start_time, end_time, pitch, amplitude, pitch_bends = ne
            notes.append({
                "start_time_s": float(start_time),
                "end_time_s": float(end_time),
                "pitch": int(pitch),
                "amplitude": float(amplitude),
            })
        
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
    keep_all_melody: bool = True
) -> Dict[str, Any]:
    """
    Analyze vocals and instruments to extract intelligent melody.
    
    Transcribes both stems separately, then uses vocal-guided analysis
    to extract the true melodic line from instruments. Now preserves ALL
    melodic notes instead of reducing to a target count.
    
    Args:
        vocals_audio: Raw bytes of vocals stem
        instruments_audio: Raw bytes of instruments stem (other/no_vocals)
        keep_all_melody: If True, keeps all melodic notes (default: True)
        
    Returns:
        Dict with melody notes, tempo, and analysis stats
    """
    logger.info("Starting melody analysis...")
    
    # Transcribe vocals
    vocal_notes = transcribe_stem_to_notes(vocals_audio, "vocals")
    
    # Transcribe instruments
    instrument_notes = transcribe_stem_to_notes(instruments_audio, "instruments")
    
    # Apply vocal-guided extraction
    logger.info("Applying vocal-guided melody extraction...")
    result = apply_vocal_guided_extraction(
        vocal_notes,
        instrument_notes,
        keep_all_melody=keep_all_melody
    )
    
    # Detect tempo
    logger.info("Detecting tempo...")
    try:
        import librosa
        y, sr = sf.read(io.BytesIO(instruments_audio), dtype="float32")
        if len(y.shape) > 1:
            y = y.mean(axis=1)  # Convert to mono
        
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo)
        logger.info(f"  Detected tempo: {tempo:.1f} BPM")
    except Exception as e:
        logger.warning(f"  Tempo detection failed: {e}")
        tempo = None
    
    result['tempo_bpm'] = tempo
    
    logger.info(
        f"Melody extraction complete: {result['stats']['original_count']} → "
        f"{result['stats']['final_count']} notes "
        f"({result['stats']['reduction_pct']}% reduction)"
    )
    
    return result


def notes_to_midi(notes: List[Dict[str, Any]], output_path: str) -> None:
    """
    Convert note list to MIDI file.
    
    Args:
        notes: List of note dictionaries
        output_path: Path to write MIDI file
    """
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano
    
    for note_dict in notes:
        note = pretty_midi.Note(
            velocity=int(note_dict['amplitude'] * 127),
            pitch=note_dict['pitch'],
            start=note_dict['start_time_s'],
            end=note_dict['end_time_s']
        )
        instrument.notes.append(note)
    
    midi.instruments.append(instrument)
    midi.write(output_path)


def _midi_to_note_name(midi_note: int) -> str:
    """Convert MIDI note number to note name."""
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi_note // 12) - 1
    note_name = note_names[midi_note % 12]
    return f"{note_name}{octave}"


def _midi_to_frequency(midi_note: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def enrich_notes_with_metadata(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add note names and frequencies to note dictionaries."""
    for note in notes:
        note['note'] = _midi_to_note_name(note['pitch'])
        note['frequency'] = round(_midi_to_frequency(note['pitch']), 2)
    return notes
