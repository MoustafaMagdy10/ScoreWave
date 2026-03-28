import io
import time
import torch
import torchaudio
from pathlib import Path
from tqdm import tqdm

from demucs.apply import apply_model
from demucs.audio import convert_audio

from models.demucs import Demucs
from shared.logger import logger


# ── Module-level singleton — model loads once on first import ──────────────
_demucs = Demucs(model_name="htdemucs")


def _bar(desc: str, total: int = 1, unit: str = "step") -> tqdm:
    """Consistent tqdm style across all stages."""
    return tqdm(
        total=total,
        desc=f"  {desc}",
        unit=unit,
        ncols=70,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit} [{elapsed}]",
        colour="yellow",
    )


def separate_audio(audio_bytes: bytes, output_dir: str) -> dict[str, str]:
    """
    Separate raw audio bytes into stems using Demucs.

    Args:
        audio_bytes: Raw bytes of the audio file (MP3 / WAV / FLAC / M4A),
                     as received directly from a FastAPI UploadFile.read().
        output_dir:  Directory where stem WAVs will be written.

    Returns:
        Dict mapping stem name -> absolute path to the written WAV file.
        e.g. {"vocals": "/tmp/.../vocals.wav", "no_vocals": "/tmp/.../no_vocals.wav"}

    Raises:
        RuntimeError  if the model is not loaded or separation fails.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not _demucs.health_check():
        raise RuntimeError("Demucs model is not loaded. Cannot run separation.")

    model   = _demucs.model
    device  = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model   = model.to(device)

    size_kb = len(audio_bytes) // 1024
    t_start = time.time()

    print()  # blank line so bars don't collide with uvicorn log prefix
    logger.info(f"Starting separation -- {size_kb} KB on {device}")

    # -- 1. Decode ------------------------------------------------------------
    with _bar("Decoding audio      ") as bar:
        waveform, sample_rate = torchaudio.load(io.BytesIO(audio_bytes))
        duration_sec = waveform.shape[-1] / sample_rate
        bar.update(1)

    logger.info(f"  Audio: {duration_sec:.1f}s | {sample_rate} Hz | {waveform.shape[0]}ch")

    # -- 2. Resample to model's expected sample rate --------------------------
    with _bar("Resampling          ") as bar:
        waveform = convert_audio(
            waveform,
            sample_rate,
            model.samplerate,      # htdemucs expects 44100 Hz
            model.audio_channels,  # stereo (2)
        )
        waveform = waveform.unsqueeze(0).to(device)  # -> [batch, ch, samples]
        bar.update(1)

    # -- 3. Separation (slow) — progress=True gives Demucs' own chunk bar ----
    logger.info("Running Demucs -- chunk progress below:")
    with torch.no_grad():
        sources = apply_model(
            model,
            waveform,
            device=device,
            shifts=1,       # 1 random shift -> better quality; 0 = fastest
            split=True,     # process in overlapping chunks -> saves memory
            overlap=0.25,
            progress=True,  # enables Demucs' built-in tqdm chunk bar
        )

    sources = sources[0]  # drop batch dim -> [num_stems, channels, samples]

    # -- 4. Write stems to disk -----------------------------------------------
    stem_names = model.sources   # ["drums", "bass", "other", "vocals"]
    stem_paths: dict[str, str] = {}

    with _bar("Writing stems       ", total=len(stem_names), unit="stem") as bar:
        for i, name in enumerate(stem_names):
            out_path = output_dir / f"{name}.wav"
            torchaudio.save(str(out_path), sources[i].cpu(), model.samplerate)
            stem_paths[name] = str(out_path)
            bar.set_postfix(stem=name)
            bar.update(1)

    # -- 5. Build no_vocals mix (bass + drums + other) ------------------------
    with _bar("Building no_vocals  ") as bar:
        vocal_idx = stem_names.index("vocals")
        no_vocals = sum(sources[i] for i in range(len(stem_names)) if i != vocal_idx)
        nv_path   = output_dir / "no_vocals.wav"
        torchaudio.save(str(nv_path), no_vocals.cpu(), model.samplerate)
        stem_paths["no_vocals"] = str(nv_path)
        bar.update(1)

    elapsed = time.time() - t_start
    print()
    logger.info(f"Separation complete -- {len(stem_paths)} stems in {elapsed:.1f}s")
    return stem_paths