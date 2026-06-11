"""
test_audio_generator.py
=======================
Utility to generate synthetic audio (sine waves) for testing.

Why sine waves?
---------------
A pure sine wave at frequency F Hz is the simplest possible audio signal.
It has exactly ONE pitch — no harmonics, no noise. So we know EXACTLY what
CREPE should report back. This makes it a perfect "known input → known output"
test.

In C++ terms: this is like a fixture / test helper file.
You would #include this in your test files.
"""

import struct
import math
import numpy as np


def generate_sine_wave_bytes(
    frequency_hz: float,
    duration_seconds: float,
    sample_rate: int = 44100,
    amplitude: float = 0.8,
) -> bytes:
    """
    Generate a pure sine wave and return it as WAV file bytes.

    A sine wave at frequency F produces the formula:
        sample[i] = amplitude * sin(2 * pi * F * t)
    where t = i / sample_rate  (time in seconds for sample i)

    Args:
        frequency_hz     : The pitch you want (e.g., 440.0 for A4)
        duration_seconds : How long the audio should be
        sample_rate      : Samples per second (44100 is CD quality)
        amplitude        : Volume, 0.0 to 1.0

    Returns:
        bytes: A valid WAV file in memory
    """
    # ── Step 1: Calculate how many samples we need ─────────────────────────
    total_samples = int(sample_rate * duration_seconds)

    # ── Step 2: Build the time axis ────────────────────────────────────────
    # t[i] = i / sample_rate
    # e.g. at 44100 Hz: t[44100] = 1.0 second
    time_axis = np.linspace(
        start=0.0,
        stop=duration_seconds,
        num=total_samples,
        endpoint=False,  # Don't include the endpoint (avoid overlap if looped)
    )

    # ── Step 3: Compute the sine wave ──────────────────────────────────────
    # sin(2π * F * t) oscillates at exactly F cycles per second
    sine_wave = amplitude * np.sin(2.0 * math.pi * frequency_hz * time_axis)

    # ── Step 4: Convert float64 [-1, 1] → int16 [-32768, 32767] ──────────
    # WAV files store samples as 16-bit signed integers
    max_int16 = 32767
    samples_int16 = (sine_wave * max_int16).astype(np.int16)

    # ── Step 5: Pack into a WAV file in memory ─────────────────────────────
    # WAV format is: [44-byte header] + [raw PCM sample data]
    wav_bytes = _pack_as_wav(samples_int16, sample_rate, num_channels=1)

    return wav_bytes


def generate_chord_bytes(
    frequencies_hz: list[float],
    duration_seconds: float,
    sample_rate: int = 44100,
    amplitude_per_tone: float = 0.4,
) -> bytes:
    """
    Generate a chord by mixing multiple sine waves.

    Useful for testing polyphonic situations.

    Args:
        frequencies_hz      : List of frequencies to mix (e.g., [261.6, 329.6, 392.0] = C major chord)
        duration_seconds    : Duration
        sample_rate         : Sample rate
        amplitude_per_tone  : Volume of each individual tone (keep low to avoid clipping)
    """
    total_samples = int(sample_rate * duration_seconds)
    time_axis = np.linspace(0.0, duration_seconds, total_samples, endpoint=False)

    # Start with silence
    mixed_wave = np.zeros(total_samples, dtype=np.float64)

    # Add each sine wave on top
    for freq in frequencies_hz:
        sine = amplitude_per_tone * np.sin(2.0 * math.pi * freq * time_axis)
        mixed_wave += sine

    # Clamp to [-1, 1] to avoid distortion
    mixed_wave = np.clip(mixed_wave, -1.0, 1.0)

    # Convert to int16 and pack as WAV
    samples_int16 = (mixed_wave * 32767).astype(np.int16)
    wav_bytes = _pack_as_wav(samples_int16, sample_rate, num_channels=1)

    return wav_bytes


def _pack_as_wav(
    samples_int16: np.ndarray, sample_rate: int, num_channels: int
) -> bytes:
    """
    Write a minimal valid WAV file into a bytes object (no file on disk).

    WAV file format (RIFF/WAVE):
      Offset  Size  Content
      0       4     "RIFF"
      4       4     file size - 8
      8       4     "WAVE"
      12      4     "fmt "
      16      4     16 (chunk size for PCM)
      20      2     1 (PCM format code)
      22      2     num_channels
      24      4     sample_rate
      28      4     byte_rate = sample_rate * channels * bytes_per_sample
      32      2     block_align = channels * bytes_per_sample
      34      2     bits_per_sample (16)
      36      4     "data"
      40      4     data size in bytes
      44      ...   raw PCM samples

    In C++ terms: this is like fwrite() of a struct to a memory buffer.
    """
    num_samples = len(samples_int16)
    bits_per_sample = 16
    bytes_per_sample = bits_per_sample // 8  # = 2
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    data_chunk_size = num_samples * bytes_per_sample
    riff_chunk_size = 36 + data_chunk_size  # everything after the first 8 bytes

    # Build the 44-byte header using struct.pack
    # '<' = little-endian (WAV spec), I = uint32, H = uint16
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",  # chunk ID
        riff_chunk_size,  # chunk size
        b"WAVE",  # format
        b"fmt ",  # subchunk1 ID
        16,  # subchunk1 size (16 for PCM)
        1,  # audio format (1 = PCM)
        num_channels,  # num channels
        sample_rate,  # sample rate
        byte_rate,  # byte rate
        block_align,  # block align
        bits_per_sample,  # bits per sample
        b"data",  # subchunk2 ID
        data_chunk_size,  # subchunk2 size
    )

    # Combine header + raw sample bytes
    raw_samples = samples_int16.tobytes()
    return header + raw_samples


# =============================================================================
# Reference frequency table (useful for assertions in tests)
# =============================================================================

# Standard western note frequencies (A4 = 440 Hz tuning)
WESTERN_NOTES = {
    "C4": 261.63,
    "C#4": 277.18,
    "D4": 293.66,
    "D#4": 311.13,
    "E4": 329.63,
    "F4": 349.23,
    "F#4": 369.99,
    "G4": 392.00,
    "G#4": 415.30,
    "A4": 440.00,
    "A#4": 466.16,
    "B4": 493.88,
    "C5": 523.25,
}

# Quarter-tone frequencies for common eastern pitches
# A quarter tone = 50 cents = multiply by 2^(50/1200) ≈ 1.02930
_QUARTER_TONE_RATIO = 2.0 ** (50.0 / 1200.0)

EASTERN_NOTES = {
    # Format: "Note+half" means a quarter tone above the note
    # (half = half of a semitone = quarter tone)
    "D+half": WESTERN_NOTES["D4"] * _QUARTER_TONE_RATIO,  # ~302.3 Hz  (Sikah area)
    "E-half": WESTERN_NOTES["E4"]
    / _QUARTER_TONE_RATIO,  # ~320.2 Hz  (used in Bayati/Rast)
    "G+half": WESTERN_NOTES["G4"] * _QUARTER_TONE_RATIO,  # ~403.5 Hz
    "A-half": WESTERN_NOTES["A4"] / _QUARTER_TONE_RATIO,  # ~426.8 Hz
    "B-half": WESTERN_NOTES["B4"] / _QUARTER_TONE_RATIO,  # ~479.8 Hz  (used in Rast)
}
