import io
import time
import threading
import math
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd
import torch
import torchcrepe
from tqdm import tqdm

from models.crepe import Crepe
from shared.logger import logger


# ── Module-level singleton ─────────────────────────────────────────────────
_crepe = Crepe(model_capacity="medium")

CREPE_SR = 16_000

_CAPACITY_MAP = {
    "tiny":   "tiny",
    "small":  "full",
    "medium": "full",
    "large":  "full",
    "full":   "full",
}


def _bar(desc: str, total: int = 1, unit: str = "step") -> tqdm:
    return tqdm(
        total=total,
        desc=f"  {desc}",
        unit=unit,
        ncols=70,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit} [{elapsed}]",
        colour="cyan",
    )


def _spinner(desc: str, stop_event: threading.Event) -> threading.Thread:
    def _run():
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        while not stop_event.is_set():
            print(f"\r  {chars[i % len(chars)]}  {desc}", end="", flush=True)
            i += 1
            stop_event.wait(timeout=0.1)
        print(f"\r  ✓  {desc}", flush=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _resample(waveform: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample using scipy.signal.resample_poly — pure C, no numba.
    Reduces the up/down ratio by their GCD first to keep it efficient.
    """
    if orig_sr == target_sr:
        return waveform
    g  = gcd(orig_sr, target_sr)
    up = target_sr // g
    down = orig_sr // g
    return resample_poly(waveform, up, down).astype(np.float32)


def _load_audio_mono_16k(audio_bytes: bytes) -> tuple[np.ndarray, float]:
    """
    Decode raw audio bytes → mono float32 numpy array at 16 kHz.
    soundfile (libsndfile) + scipy — zero numba, Python 3.12 safe.
    """
    waveform, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)

    # Mix down to mono
    waveform = waveform.mean(axis=1) if waveform.shape[1] > 1 else waveform[:, 0]

    # Resample with scipy — NOT resampy
    waveform = _resample(waveform, sr, CREPE_SR)

    return waveform, len(waveform) / CREPE_SR


def extract_pitch(
    audio_bytes: bytes,
    confidence_threshold: float = 0.5,
    step_size_ms: int = 10,
) -> dict:
    if not _crepe.health_check():
        raise RuntimeError("CREPE model is not ready.")

    t_start = time.time()
    print()
    logger.info("Starting pitch extraction (torchcrepe)")

    # ── 1. Decode → mono 16 kHz (scipy, no numba) ────────────────────────────
    with _bar("Decoding audio      ") as bar:
        waveform, duration_s = _load_audio_mono_16k(audio_bytes)
        bar.update(1)

    logger.info(f"  Audio: {duration_s:.1f}s | mono | {CREPE_SR} Hz")

    # ── 2. Run torchcrepe ─────────────────────────────────────────────────────
    hop_length   = int(CREPE_SR * step_size_ms / 1000)
    device       = _crepe._device
    model        = _CAPACITY_MAP.get(_crepe.model_capacity, "full")
    audio_tensor = torch.from_numpy(waveform).unsqueeze(0).float()  # (1, N)

    logger.info("Running torchcrepe -- frame progress below:")
    stop = threading.Event()
    _spinner("torchcrepe predicting frames...", stop)

    pitch, periodicity = torchcrepe.predict(
        audio_tensor,
        sample_rate=CREPE_SR,
        hop_length=hop_length,
        fmin=32.7,
        fmax=1975.5,
        model=model,
        decoder=torchcrepe.decode.viterbi,
        return_periodicity=True,
        batch_size=512,
        device=device,
        pad=True,
    )

    stop.set()

    # ── 3. Build arrays ───────────────────────────────────────────────────────
    freq_arr = pitch.squeeze().cpu().numpy()
    conf_arr = periodicity.squeeze().cpu().numpy()
    n_frames = len(freq_arr)
    time_arr = np.arange(n_frames) * hop_length / CREPE_SR

    # ── 4. Filter by confidence ───────────────────────────────────────────────
    with _bar("Filtering confidence") as bar:
        mask      = conf_arr >= confidence_threshold
        time_kept = time_arr[mask]
        freq_kept = freq_arr[mask]
        conf_kept = conf_arr[mask]
        bar.update(1)

    frames_kept = int(mask.sum())
    kept_pct    = frames_kept / n_frames * 100 if n_frames else 0
    logger.info(f"  Kept {frames_kept}/{n_frames} frames ({kept_pct:.1f}%) at threshold {confidence_threshold}")

    # ── 5. Hz → note names ───────────────────────────────────────────────────
    with _bar("Converting to notes ") as bar:
        notes = [_hz_to_note(f) for f in freq_kept]
        bar.update(1)

    elapsed = time.time() - t_start
    print()
    logger.info(f"Pitch extraction complete -- {elapsed:.1f}s")

    return {
        "time":         time_kept.tolist(),
        "frequency":    freq_kept.tolist(),
        "confidence":   conf_kept.tolist(),
        "note":         notes,
        "duration_s":   round(duration_s, 2),
        "frames_total": n_frames,
        "frames_kept":  frames_kept,
    }


def _hz_to_note(freq_hz: float) -> str:
    if freq_hz <= 0:
        return "N/A"
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    semitones  = 12 * np.log2(freq_hz / 440.0) + 69
    midi_int   = int(round(semitones))
    octave     = (midi_int // 12) - 1
    return f"{note_names[midi_int % 12]}{octave}"