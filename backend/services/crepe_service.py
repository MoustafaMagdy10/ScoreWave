"""
crepe_service.py
================
Pitch detection service using torchcrepe (CREPE model).

What is CREPE?
--------------
CREPE (Convolutional Representation for Pitch Estimation) is a deep learning
model that listens to audio and tells you: "at this moment in time, what
frequency (pitch) is being sung or played?"

It outputs:
  - time[]      : array of timestamps (in seconds), one per frame
  - frequency[] : the detected pitch in Hz at each timestamp
  - confidence[]: how sure the model is (0.0 = not sure, 1.0 = very sure)

Why is this useful for eastern music?
--------------------------------------
Western music uses 12 equally-spaced notes per octave (semitones).
Eastern (maqam) music uses additional pitches BETWEEN those notes, called
quarter tones (~50 cents between two semitones). CREPE gives us the EXACT
frequency in Hz, so we can detect these microtonal inflections precisely.

Pipeline position:
  Audio bytes → [this file] → pitch contour with cents deviation → next step
"""

# =============================================================================
# Imports
# =============================================================================

# Standard library
import io
import time
import threading

# Numeric / audio
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd

# PyTorch + CREPE
import torch
import torchcrepe

# Progress bar
from tqdm import tqdm

# Project-local
from models.crepe import Crepe
from shared.logger import logger


# =============================================================================
# Module-level Constants
# =============================================================================

# CREPE was trained on 16 kHz audio, so we always resample to this rate.
CREPE_SR: int = 16_000

# Map our internal model size names → torchcrepe model names.
# torchcrepe only has "tiny" and "full"; everything medium+ maps to "full".
_CAPACITY_MAP: dict[str, str] = {
    "tiny": "tiny",
    "small": "full",
    "medium": "full",
    "large": "full",
    "full": "full",
}

# Quarter-tone tolerance in cents.
# A quarter tone is exactly 50 cents. We flag a note as "quarter-tone" if
# its deviation from the nearest semitone is within this window around ±50.
# Example: if QUARTER_TONE_TOLERANCE = 15, we flag deviations in [-65, -35]
# or [35, 65] cents as quarter-tones.
QUARTER_TONE_TOLERANCE: int = 15


# =============================================================================
# Singleton model instance
# =============================================================================

# We load the model ONCE when this module is first imported.
# Loading a neural network is expensive (~seconds), so we don't want to do it
# on every function call.
_crepe: Crepe = Crepe(model_capacity="medium")


# =============================================================================
# Progress helpers
# =============================================================================


def _make_progress_bar(
    description: str, total_steps: int = 1, unit: str = "step"
) -> tqdm:
    """
    Create a tqdm progress bar with a consistent style.

    In C++ terms: this is like a utility function that creates a
    formatted console output object.
    """
    return tqdm(
        total=total_steps,
        desc=f"  {description}",
        unit=unit,
        ncols=70,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit} [{elapsed}]",
        colour="cyan",
    )


def _start_spinner(description: str, stop_event: threading.Event) -> threading.Thread:
    """
    Start a spinner animation in a background thread.

    Used while torchcrepe is running, because it doesn't expose frame-by-frame
    progress — we just know it's working.

    In C++ terms: this launches a detached thread that writes to stdout in a loop.
    The caller signals it to stop via stop_event (like a std::atomic<bool> flag).
    """
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _spin_loop():
        frame_index = 0
        while not stop_event.is_set():
            # Overwrite the current line with the next spinner frame
            current_char = spinner_chars[frame_index % len(spinner_chars)]
            print(f"\r  {current_char}  {description}", end="", flush=True)
            frame_index += 1
            # Wait 100ms before next frame (or until stop is signaled)
            stop_event.wait(timeout=0.1)
        # Print a checkmark when done
        print(f"\r  ✓  {description}", flush=True)

    background_thread = threading.Thread(target=_spin_loop, daemon=True)
    background_thread.start()
    return background_thread


# =============================================================================
# Audio loading
# =============================================================================


def _resample_audio(
    waveform: np.ndarray, original_sr: int, target_sr: int
) -> np.ndarray:
    """
    Resample audio from original_sr to target_sr using scipy's polyphase resampler.

    Why polyphase? It's implemented in pure C (no numba JIT compiler needed),
    making it compatible with Python 3.12+.

    How it works:
      Resampling by a ratio (target_sr / original_sr) is done as:
        1. Upsample by target_sr / gcd
        2. Downsample by original_sr / gcd
      The GCD step simplifies the fraction to avoid unnecessary work.

    Example: 44100 Hz → 16000 Hz
      gcd(44100, 16000) = 100
      up = 160, down = 441
    """
    # If already at the right rate, do nothing
    if original_sr == target_sr:
        return waveform

    # Simplify the resampling ratio
    common_divisor = gcd(original_sr, target_sr)
    upsample_factor = target_sr // common_divisor
    downsample_factor = original_sr // common_divisor

    # Resample and cast back to float32
    resampled = resample_poly(waveform, upsample_factor, downsample_factor)
    return resampled.astype(np.float32)


def _load_audio_as_mono_16k(audio_bytes: bytes) -> tuple[np.ndarray, float]:
    """
    Decode audio bytes → mono float32 numpy array resampled to 16 kHz.

    Steps:
      1. Decode the bytes (MP3 / WAV / FLAC / M4A) using libsndfile
      2. Mix stereo channels down to mono by averaging them
      3. Resample to CREPE_SR (16000 Hz)

    Returns:
      (waveform, duration_seconds)
    """
    # Step 1: Decode audio bytes into a numpy array
    # soundfile returns shape (num_samples, num_channels)
    waveform, sample_rate = sf.read(
        io.BytesIO(audio_bytes), dtype="float32", always_2d=True
    )

    # Step 2: Convert to mono
    num_channels = waveform.shape[1]
    if num_channels > 1:
        # Average all channels together: (L + R) / 2  →  mono
        mono_waveform = waveform.mean(axis=1)
    else:
        # Already mono, just remove the channel dimension
        mono_waveform = waveform[:, 0]

    # Step 3: Resample to 16 kHz (what CREPE expects)
    mono_16k = _resample_audio(mono_waveform, sample_rate, CREPE_SR)

    # Calculate duration in seconds from the resampled length
    duration_seconds = len(mono_16k) / CREPE_SR

    return mono_16k, duration_seconds


# =============================================================================
# Pitch → Note conversion (Eastern music aware)
# =============================================================================

# Western note names in chromatic order (C = 0, C# = 1, ... B = 11)
_NOTE_NAMES: list[str] = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
]


def _frequency_to_note_details(frequency_hz: float) -> dict:
    """
    Convert a frequency in Hz to detailed note information including
    microtonal (cents) deviation — critical for eastern/maqam music.

    Why cents deviation matters for eastern music:
    -------------------------------------------
    In western music, notes are quantized to 12 semitones per octave.
    But maqam scales use pitches BETWEEN semitones — called "quarter tones"
    (roughly 50 cents between two semitones).

    Standard western notation:   C --- 100 cents --- C#
    Eastern quarter tone:        C --- 50 cents --- C+half --- 100 cents --- C#

    By measuring how far a detected frequency is from the nearest semitone
    (in cents), we can flag quarter-tone notes and preserve them for maqam
    analysis downstream.

    How the math works:
    -------------------
    MIDI note 69 = A4 = 440 Hz (international standard reference)

    Number of semitones from A4:
        semitones = 12 * log2(frequency / 440.0) + 69

    We keep this as a float (e.g., 62.47) then:
        midi_rounded  = round(62.47) = 62   ← nearest semitone
        cents_dev     = (62.47 - 62) * 100 = 47 cents above the semitone

    A deviation of ~50 cents means we're halfway between two semitones
    → that's a quarter tone!

    Returns a dict with:
      note        : western note name + octave (e.g., "D4")
      midi        : MIDI note number (integer, nearest semitone)
      cents_dev   : deviation from nearest semitone in cents (-50 to +50)
      is_quarter  : True if this note is a quarter-tone (eastern pitch)
      frequency   : the original frequency in Hz (preserved for downstream)
    """
    # Silence / unvoiced frame → return a "Rest"
    if frequency_hz <= 0.0:
        return {
            "note": "Rest",
            "midi": None,
            "cents_dev": 0,
            "is_quarter": False,
            "frequency": 0.0,
        }

    # Step 1: Convert Hz → exact MIDI semitone position (float, not rounded)
    #   Formula: midi = 12 * log2(f / 440) + 69
    exact_midi_position = 12.0 * np.log2(frequency_hz / 440.0) + 69.0

    # Step 2: Round to nearest integer semitone
    nearest_midi = int(round(exact_midi_position))

    # Step 3: Measure how far off we are from that semitone (in cents)
    #   100 cents = 1 semitone
    cents_deviation = int(round((exact_midi_position - nearest_midi) * 100.0))

    # Step 4: Extract octave and note name from MIDI number
    #   MIDI 60 = C4, MIDI 69 = A4, etc.
    #   octave formula: (midi // 12) - 1
    octave = (nearest_midi // 12) - 1
    pitch_class = nearest_midi % 12  # 0=C, 1=C#, 2=D, ...
    note_name = _NOTE_NAMES[pitch_class]

    # Step 5: Determine if this is a quarter tone
    #   Quarter tone = deviation within [35..65] cents of any direction
    lower_quarter_bound = -(50 + QUARTER_TONE_TOLERANCE)  # e.g., -65
    upper_quarter_bound = -(50 - QUARTER_TONE_TOLERANCE)  # e.g., -35

    is_flat_quarter = lower_quarter_bound <= cents_deviation <= upper_quarter_bound
    is_sharp_quarter = -upper_quarter_bound <= cents_deviation <= -lower_quarter_bound
    is_quarter_tone = is_flat_quarter or is_sharp_quarter

    return {
        "note": f"{note_name}{octave}",
        "midi": nearest_midi,
        "cents_dev": cents_deviation,
        "is_quarter": is_quarter_tone,
        "frequency": frequency_hz,
    }


# =============================================================================
# Main pitch extraction function
# =============================================================================


def extract_pitch(
    audio_bytes: bytes,
    confidence_threshold: float = 0.5,
    step_size_ms: int = 10,
) -> dict:
    """
    Extract a pitch contour from raw audio bytes using the CREPE model.

    This is the main function called by the router. It returns a frame-by-frame
    record of what pitch was detected and how confident the model is.

    Args:
        audio_bytes        : Raw audio file bytes (MP3, WAV, FLAC, M4A, ...)
        confidence_threshold: Frames below this confidence are treated as silence (0 Hz).
                              Range 0.0–1.0. Higher = stricter filter.
        step_size_ms       : How many milliseconds between frames.
                              10ms = 100 frames per second (default, high resolution).
                              20ms = 50 frames per second (faster, less precise).

    Returns a dict with:
        time[]        : timestamps for each frame (seconds)
        frequency[]   : detected pitch in Hz (0.0 for unconfident/silent frames)
        confidence[]  : model confidence per frame (always returned, all frames)
        note_details[]: list of dicts from _frequency_to_note_details() per frame
        duration_s    : total audio duration in seconds
        frames_total  : total number of frames analyzed
        frames_kept   : number of frames above confidence threshold
    """

    # Guard: make sure the model loaded successfully at import time
    if not _crepe.health_check():
        raise RuntimeError("CREPE model is not ready.")

    timer_start = time.time()
    print()  # Blank line for cleaner console output
    logger.info("Starting pitch extraction (torchcrepe)")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Decode and prepare audio
    # ─────────────────────────────────────────────────────────────────────────
    with _make_progress_bar("Decoding audio      ") as progress_bar:
        mono_waveform, duration_seconds = _load_audio_as_mono_16k(audio_bytes)
        progress_bar.update(1)

    logger.info(f"  Audio: {duration_seconds:.1f}s | mono | {CREPE_SR} Hz")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Run torchcrepe pitch estimation
    # ─────────────────────────────────────────────────────────────────────────

    # hop_length = how many audio samples between each analysis frame
    # At 16000 Hz with 10ms steps: hop_length = 160 samples
    hop_length_samples = int(CREPE_SR * step_size_ms / 1000)

    # Which device to run on (CPU or GPU if available)
    compute_device = _crepe._device

    # Map our model capacity to torchcrepe's naming
    torchcrepe_model_name = _CAPACITY_MAP.get(_crepe.model_capacity, "full")

    # torchcrepe expects shape (1, num_samples) — a batch of 1 audio signal
    audio_tensor = torch.from_numpy(mono_waveform).unsqueeze(0).float()

    # Start the spinner (torchcrepe doesn't give us frame-level progress)
    logger.info("Running torchcrepe -- this may take a moment...")
    spinner_stop_event = threading.Event()
    _start_spinner("torchcrepe predicting frames...", spinner_stop_event)

    # Run the model
    # pitch       : shape (1, num_frames) — frequency in Hz per frame
    # periodicity : shape (1, num_frames) — confidence per frame (0 to 1)
    pitch_tensor, periodicity_tensor = torchcrepe.predict(
        audio_tensor,
        sample_rate=CREPE_SR,
        hop_length=hop_length_samples,
        fmin=32.7,  # Lowest detectable pitch (~C1)
        fmax=1975.5,  # Highest detectable pitch (~B6)
        model=torchcrepe_model_name,
        decoder=torchcrepe.decode.viterbi,  # Viterbi = smoother, more musical output
        return_periodicity=True,
        batch_size=512,
        device=compute_device,
        pad=True,  # Pad edges so frame count matches audio length
    )

    # Signal the spinner to stop
    spinner_stop_event.set()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Convert tensors → numpy arrays
    # ─────────────────────────────────────────────────────────────────────────

    # .squeeze() removes the batch dimension: (1, N) → (N,)
    # .cpu()     moves from GPU back to CPU memory (no-op if already CPU)
    # .numpy()   converts PyTorch tensor → numpy array
    frequency_array = pitch_tensor.squeeze().cpu().numpy()
    confidence_array = periodicity_tensor.squeeze().cpu().numpy()
    total_frame_count = len(frequency_array)

    # Build the timestamp for each frame
    # Frame i starts at: i * hop_length_samples / CREPE_SR  seconds
    time_array = np.arange(total_frame_count) * hop_length_samples / CREPE_SR

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Apply confidence filter
    # ─────────────────────────────────────────────────────────────────────────
    # Strategy: instead of REMOVING low-confidence frames (which breaks time
    # alignment), we SET their frequency to 0.0.
    # This way, every frame index still maps to the correct timestamp.
    # Downstream code can treat 0.0 Hz as "silence/rest".
    #
    # In C++ terms: this is like memset-ing low-confidence entries to 0.

    with _make_progress_bar("Filtering confidence") as progress_bar:
        # Build a boolean mask: True where confidence is high enough
        confidence_mask = confidence_array >= confidence_threshold

        # Zero out frequencies below the threshold (keep array same length)
        frequency_filtered = np.where(confidence_mask, frequency_array, 0.0)

        progress_bar.update(1)

    # Count how many frames survived the filter
    frames_above_threshold = int(confidence_mask.sum())
    kept_percentage = (
        (frames_above_threshold / total_frame_count * 100.0)
        if total_frame_count > 0
        else 0.0
    )

    logger.info(
        f"  Kept {frames_above_threshold}/{total_frame_count} frames "
        f"({kept_percentage:.1f}%) at threshold {confidence_threshold}"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Convert each frequency to note details (with cents deviation)
    # ─────────────────────────────────────────────────────────────────────────
    # This is where eastern music magic happens — we preserve the exact cents
    # deviation so downstream maqam detection knows about quarter tones.

    with _make_progress_bar("Converting to notes ") as progress_bar:
        note_details_list = []
        for freq in frequency_filtered:
            note_info = _frequency_to_note_details(freq)
            note_details_list.append(note_info)
        progress_bar.update(1)

    # Log how many quarter-tone notes were detected
    quarter_tone_count = sum(1 for nd in note_details_list if nd["is_quarter"])
    if quarter_tone_count > 0:
        logger.info(f"  Quarter-tone notes detected: {quarter_tone_count} frames")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Return results
    # ─────────────────────────────────────────────────────────────────────────

    elapsed_seconds = time.time() - timer_start
    print()
    logger.info(f"Pitch extraction complete -- {elapsed_seconds:.1f}s")

    return {
        # Frame-by-frame arrays (all same length = total_frame_count)
        "time": time_array.tolist(),
        "frequency": frequency_filtered.tolist(),  # 0.0 = silent/unconfident
        "confidence": confidence_array.tolist(),  # Raw confidence (all frames)
        "note_details": note_details_list,  # Detailed note info per frame
        # Summary
        "duration_s": round(duration_seconds, 2),
        "frames_total": total_frame_count,
        "frames_kept": frames_above_threshold,
    }
