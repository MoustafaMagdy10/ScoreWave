"""
Pitch histogram extraction for maqam analysis.

Uses Essentia's PitchMelodia (when available) to build a cents-based
pitch histogram from a monophonic audio signal. This histogram is the
foundation of accurate maqam / tonic detection for Eastern music.

If Essentia is not installed, a fallback path using librosa's pyin
estimator is provided. Both paths produce the same output schema.
"""

import io
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, Any, List, Optional
from scipy.signal import find_peaks

from shared.logger import logger

# Attempt to import Essentia (optional C++ extension)
try:
    import essentia.standard as es  # type: ignore[import]

    ESSENTIA_AVAILABLE = True
    logger.info("Essentia available — using PitchMelodia for F0 extraction")
except ImportError:
    ESSENTIA_AVAILABLE = False
    logger.warning(
        "Essentia not installed. Falling back to librosa pyin for pitch histogram. "
        "Install with: pip install essentia"
    )

# Histogram resolution: 5 cents per bin → 240 bins per octave
BINS_PER_OCTAVE = 240
CENTS_PER_BIN = 1200 / BINS_PER_OCTAVE  # 5.0
REF_FREQ = 440.0  # A4 reference
TARGET_SR = 44100  # Essentia requires 44.1 kHz
MIN_CONFIDENCE = 0.4  # Minimum pitch confidence to include in histogram


def extract_pitch_histogram(audio_input: str | bytes) -> Dict[str, Any]:
    """
    Extract F0 contour and cents histogram from an audio file or bytes.

    Args:
        audio_input: Either an absolute file path (str/Path) or raw audio
                     bytes (WAV/MP3/FLAC).  Bytes are written to a temporary
                     file when Essentia is used (it requires a path).

    Returns:
        Dict with keys:
            ``hist``              – normalized 240-float histogram (0–1200 cents)
            ``bin_edges_cents``   – 241-float array of bin edges in cents
            ``tonic_hz``         – estimated tonic frequency in Hz
            ``tonic_cents``      – tonic position within the octave (0–1200)
            ``tonic_note``       – human-readable tonic name (e.g. "D", "E½")
            ``peak_cents``       – list of all significant pitch peak positions
            ``essentia_used``    – bool, whether Essentia was used

    Raises:
        RuntimeError: If the audio cannot be loaded or is too short.
    """
    # --- Normalise input -------------------------------------------------------
    if isinstance(audio_input, (str, Path)):
        audio_path = str(audio_input)
        audio_bytes: Optional[bytes] = None
    else:
        audio_bytes = audio_input
        audio_path = None

    if ESSENTIA_AVAILABLE:
        return _extract_with_essentia(audio_path, audio_bytes)
    else:
        return _extract_with_librosa(audio_path, audio_bytes)


# ── Essentia path ─────────────────────────────────────────────────────────────


def _extract_with_essentia(
    audio_path: Optional[str],
    audio_bytes: Optional[bytes],
) -> Dict[str, Any]:
    """F0 extraction via Essentia PitchMelodia."""
    import tempfile, os  # noqa: E401

    # Write bytes to temp file if we only have bytes
    tmp_path: Optional[str] = None
    if audio_path is None and audio_bytes is not None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        # Convert bytes → wav via soundfile so Essentia can read it
        waveform, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
        mono = waveform.mean(axis=1) if waveform.shape[1] > 1 else waveform[:, 0]
        sf.write(tmp_path, mono, sr)
        tmp.close()
        audio_path = tmp_path

    try:
        loader = es.MonoLoader(filename=audio_path, sampleRate=TARGET_SR)
        audio = loader()

        pitch_extractor = es.PitchMelodia(sampleRate=TARGET_SR)
        pitch_hz, pitch_conf = pitch_extractor(audio)

        valid_mask = (pitch_hz > 0) & (pitch_conf > MIN_CONFIDENCE)
        valid_hz = pitch_hz[valid_mask]

        return _build_histogram(valid_hz, essentia_used=True)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


# ── librosa fallback path ─────────────────────────────────────────────────────


def _extract_with_librosa(
    audio_path: Optional[str],
    audio_bytes: Optional[bytes],
) -> Dict[str, Any]:
    """F0 extraction via librosa pyin (fallback when Essentia not installed)."""
    import librosa  # type: ignore[import]

    if audio_bytes is not None:
        waveform, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
        mono = waveform.mean(axis=1) if waveform.shape[1] > 1 else waveform[:, 0]
    else:
        mono, sr = librosa.load(audio_path, sr=None, mono=True)

    # Resample to 22050 Hz (librosa pyin sweet spot)
    if sr != 22050:
        mono = librosa.resample(mono, orig_sr=sr, target_sr=22050)
        sr = 22050

    f0, voiced_flag, voiced_prob = librosa.pyin(
        mono,
        sr=sr,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
    )

    valid_hz = f0[(voiced_flag) & (f0 > 0)]
    return _build_histogram(valid_hz, essentia_used=False)


# ── Histogram builder (shared) ────────────────────────────────────────────────


def _build_histogram(valid_hz: np.ndarray, essentia_used: bool) -> Dict[str, Any]:
    """Convert a valid F0 array (Hz) into a normalized cents histogram."""
    if len(valid_hz) == 0:
        logger.warning("No voiced frames found — returning empty histogram")
        empty_hist = np.zeros(BINS_PER_OCTAVE).tolist()
        empty_edges = np.linspace(0, 1200, BINS_PER_OCTAVE + 1).tolist()
        return {
            "hist": empty_hist,
            "bin_edges_cents": empty_edges,
            "tonic_hz": 0.0,
            "tonic_cents": 0.0,
            "tonic_note": "Unknown",
            "peak_cents": [],
            "essentia_used": essentia_used,
        }

    # Convert Hz → cents mod 1200 (fold into one octave)
    cents = 1200.0 * np.log2(valid_hz / REF_FREQ)
    cents_mod = cents % 1200.0

    hist, bin_edges = np.histogram(cents_mod, bins=BINS_PER_OCTAVE, range=(0.0, 1200.0))
    hist = hist / (hist.sum() + 1e-8)  # normalise to probability

    # ── Tonic detection via histogram peak ────────────────────────────────────
    peaks, props = find_peaks(hist, height=0.005, distance=10, prominence=0.003)

    if len(peaks) == 0:
        # Fallback: global maximum
        tonic_bin = int(np.argmax(hist))
    else:
        # Highest-amplitude peak
        tonic_bin = int(peaks[np.argmax(hist[peaks])])

    tonic_cents = float(bin_edges[tonic_bin])
    tonic_hz = REF_FREQ * (2.0 ** (tonic_cents / 1200.0))

    peak_cents = [float(bin_edges[p]) for p in peaks]

    logger.info(
        f"Pitch histogram built: {len(valid_hz)} frames, "
        f"tonic={_hz_to_note_with_quarter(tonic_hz)} @ {tonic_cents:.0f}¢ "
        f"({tonic_hz:.2f} Hz), {len(peaks)} peaks"
    )

    return {
        "hist": hist.tolist(),
        "bin_edges_cents": bin_edges.tolist(),
        "tonic_hz": float(tonic_hz),
        "tonic_cents": float(tonic_cents),
        "tonic_note": _hz_to_note_with_quarter(tonic_hz),
        "peak_cents": peak_cents,
        "essentia_used": essentia_used,
    }


# ── Note name helper ──────────────────────────────────────────────────────────

_NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def _hz_to_note_with_quarter(hz: float) -> str:
    """
    Convert a frequency (Hz) to a note name, appending "½" for quarter-tone
    inflections (deviation > ±25 cents from nearest semitone).

    Args:
        hz: Frequency in Hz.

    Returns:
        Note name such as "D", "E½", or "Bb½".
    """
    if hz <= 0:
        return "?"
    midi = 69.0 + 12.0 * np.log2(hz / 440.0)
    semitone = int(round(midi)) % 12
    deviation = midi - round(midi)  # signed distance from nearest semitone
    suffix = "½" if abs(deviation) > 0.25 else ""
    return _NOTE_NAMES[semitone] + suffix


def get_scale_cents_from_histogram(
    hist: List[float],
    bin_edges: List[float],
    tonic_cents: float,
    n_notes: int = 7,
) -> List[float]:
    """
    Extract the most prominent scale degrees from a pitch histogram.

    Starting from the detected tonic, finds the ``n_notes`` most prominent
    peaks and returns their distances from the tonic in cents.

    Args:
        hist: Normalized pitch histogram (240 bins, 0–1200 cents).
        bin_edges: Bin edge values in cents (241 values).
        tonic_cents: Tonic position in cents.
        n_notes: Number of scale degrees to return (default 7, i.e. one octave).

    Returns:
        Sorted list of cent offsets from the tonic (always starts with 0).
    """
    hist_arr = np.array(hist)
    peaks, _ = find_peaks(hist_arr, height=0.005, distance=5)

    if len(peaks) == 0:
        # Uniform spacing fallback
        return [round(i * 1200 / n_notes) for i in range(n_notes + 1)]

    # Sort peaks by amplitude and take top n_notes
    top_peaks = sorted(peaks, key=lambda p: -hist_arr[p])[:n_notes]
    scale_cents_raw = [float(bin_edges[p]) for p in top_peaks]

    # Express as offsets from tonic, normalise to [0, 1200)
    offsets = sorted({round((c - tonic_cents) % 1200) for c in scale_cents_raw})

    if offsets and offsets[0] != 0:
        offsets.insert(0, 0)

    return offsets
