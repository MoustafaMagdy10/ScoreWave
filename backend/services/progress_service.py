"""
Progress tracking service for audio processing jobs.

Provides in-memory tracking of job progress through various stages
of the audio-to-sheet-music pipeline.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ProcessingStage(str, Enum):
    """Processing stages with associated progress percentages."""

    UPLOADING = "uploading"
    SEPARATING = "separating"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


# Stage progress percentages
STAGE_PROGRESS: dict[ProcessingStage, int] = {
    ProcessingStage.UPLOADING: 10,
    ProcessingStage.SEPARATING: 30,
    ProcessingStage.TRANSCRIBING: 50,
    ProcessingStage.ANALYZING: 70,
    ProcessingStage.GENERATING: 90,
    ProcessingStage.COMPLETE: 100,
    ProcessingStage.FAILED: 0,
}


@dataclass
class JobProgress:
    """Tracks progress of a single processing job."""

    job_id: str
    stage: ProcessingStage = ProcessingStage.UPLOADING
    progress: int = 5  # Start at 5% for realistic feel
    message: str = "Initializing..."
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ProgressService:
    """In-memory progress tracking for audio processing jobs."""

    def __init__(self):
        self._jobs: dict[str, JobProgress] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 3600  # 1 hour
        self._max_job_age = 7200  # 2 hours

    def create_job(self, job_id: str) -> JobProgress:
        """
        Create a new job progress tracker.

        Args:
            job_id: Unique identifier for the job

        Returns:
            JobProgress instance for the new job
        """
        with self._lock:
            job = JobProgress(job_id=job_id)
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> Optional[JobProgress]:
        """
        Get progress for a specific job.

        Args:
            job_id: Job identifier

        Returns:
            JobProgress if found, None otherwise
        """
        with self._lock:
            return self._jobs.get(job_id)

    def update_stage(
        self,
        job_id: str,
        stage: ProcessingStage,
        message: Optional[str] = None,
    ) -> Optional[JobProgress]:
        """
        Update job to a new processing stage.

        Args:
            job_id: Job identifier
            stage: New processing stage
            message: Optional status message

        Returns:
            Updated JobProgress if found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.stage = stage
                job.progress = STAGE_PROGRESS.get(stage, job.progress)
                job.message = message or self._get_stage_message(stage)
                job.updated_at = time.time()
            return job

    def update_progress(
        self,
        job_id: str,
        progress: int,
        message: Optional[str] = None,
    ) -> Optional[JobProgress]:
        """
        Update job progress percentage within current stage.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            message: Optional status message

        Returns:
            Updated JobProgress if found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.progress = max(0, min(100, progress))
                if message:
                    job.message = message
                job.updated_at = time.time()
            return job

    def fail_job(self, job_id: str, error: str) -> Optional[JobProgress]:
        """
        Mark a job as failed.

        Args:
            job_id: Job identifier
            error: Error message

        Returns:
            Updated JobProgress if found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.stage = ProcessingStage.FAILED
                job.error = error
                job.message = f"Failed: {error}"
                job.updated_at = time.time()
            return job

    def complete_job(self, job_id: str) -> Optional[JobProgress]:
        """
        Mark a job as complete.

        Args:
            job_id: Job identifier

        Returns:
            Updated JobProgress if found
        """
        return self.update_stage(
            job_id,
            ProcessingStage.COMPLETE,
            "Processing complete!",
        )

    def delete_job(self, job_id: str) -> bool:
        """
        Remove a job from tracking.

        Args:
            job_id: Job identifier

        Returns:
            True if job was deleted, False if not found
        """
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False

    def cleanup_old_jobs(self) -> int:
        """
        Remove jobs older than max_job_age.

        Returns:
            Number of jobs cleaned up
        """
        current_time = time.time()
        with self._lock:
            old_jobs = [
                job_id
                for job_id, job in self._jobs.items()
                if current_time - job.created_at > self._max_job_age
            ]
            for job_id in old_jobs:
                del self._jobs[job_id]
            return len(old_jobs)

    def _get_stage_message(self, stage: ProcessingStage) -> str:
        """Get default message for a processing stage."""
        messages = {
            ProcessingStage.UPLOADING: "Uploading audio file...",
            ProcessingStage.SEPARATING: "Separating audio stems with Demucs...",
            ProcessingStage.TRANSCRIBING: "Transcribing notes with Basic Pitch...",
            ProcessingStage.ANALYZING: "Analyzing melody patterns...",
            ProcessingStage.GENERATING: "Generating sheet music...",
            ProcessingStage.COMPLETE: "Processing complete!",
            ProcessingStage.FAILED: "Processing failed",
        }
        return messages.get(stage, "Processing...")


# Singleton instance + module-level lock for thread-safe initialization
_progress_service: Optional[ProgressService] = None
_singleton_lock = threading.Lock()


def get_progress_service() -> ProgressService:
    """Get the singleton progress service instance (thread-safe)."""
    global _progress_service
    if _progress_service is None:  # fast path — no lock needed after init
        with _singleton_lock:
            if _progress_service is None:  # guarded path — exactly one init
                _progress_service = ProgressService()
    return _progress_service
