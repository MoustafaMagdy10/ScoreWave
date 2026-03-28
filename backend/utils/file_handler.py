import os
import uuid
import shutil
from pathlib import Path

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
MAX_UPLOAD_BYTES   = int(os.getenv("MAX_UPLOAD_MB", 50)) * 1024 * 1024


def generate_job_id() -> str:
    return str(uuid.uuid4())


def get_job_dir(job_id: str) -> Path:
    path = Path(f"tmp/jobs/{job_id}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_stems_dir(job_id: str) -> Path:
    path = get_job_dir(job_id) / "stems"
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_audio_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")


def cleanup_job(job_id: str) -> None:
    job_dir = Path(f"tmp/jobs/{job_id}")
    if job_dir.exists():
        shutil.rmtree(job_dir)