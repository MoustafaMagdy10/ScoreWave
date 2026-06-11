"""
Progress router for real-time job progress tracking.

Provides SSE (Server-Sent Events) streaming and polling endpoints
for tracking audio processing job progress.
"""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.progress_service import (
    get_progress_service,
    ProcessingStage,
)


router = APIRouter()


class ProgressResponse(BaseModel):
    """Response model for progress status."""

    job_id: str
    stage: str
    progress: int
    message: str
    error: str | None = None


def _job_to_response(job) -> ProgressResponse:
    """Convert JobProgress to ProgressResponse."""
    return ProgressResponse(
        job_id=job.job_id,
        stage=job.stage.value,
        progress=job.progress,
        message=job.message,
        error=job.error,
    )


async def _progress_event_generator(job_id: str) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for job progress updates.

    Args:
        job_id: Job identifier to track

    Yields:
        SSE-formatted event strings
    """
    progress_service = get_progress_service()
    last_progress = -1
    last_stage = None
    retry_count = 0
    max_retries = 10  # Wait up to 10 seconds for job to appear

    while True:
        job = progress_service.get_job(job_id)

        if job is None:
            retry_count += 1
            if retry_count > max_retries:
                # Job not found after retries
                yield f"data: {json.dumps({'error': 'Job not found', 'job_id': job_id})}\n\n"
                break
            # Job might not be created yet, wait a bit
            await asyncio.sleep(1)
            continue

        # Reset retry count once job is found
        retry_count = 0

        # Send update if progress or stage changed
        if job.progress != last_progress or job.stage != last_stage:
            last_progress = job.progress
            last_stage = job.stage

            response = _job_to_response(job)
            yield f"data: {json.dumps(response.model_dump())}\n\n"

        # Stop streaming on completion or failure
        if job.stage in (ProcessingStage.COMPLETE, ProcessingStage.FAILED):
            break

        # Poll interval
        await asyncio.sleep(0.5)


@router.get("/progress/{job_id}")
async def stream_progress(job_id: str):
    """
    🔴 **SSE Stream: Real-time Progress Updates**

    Streams Server-Sent Events (SSE) with job progress updates.
    Connect to this endpoint to receive live progress updates.

    **Event format:**
    ```
    data: {"job_id": "abc123", "stage": "separating", "progress": 30, "message": "..."}
    ```

    **Stages:** uploading → separating → transcribing → analyzing → generating → complete

    The stream automatically closes when processing completes or fails.
    """
    return StreamingResponse(
        _progress_event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/progress/{job_id}/status", response_model=ProgressResponse)
async def get_progress_status(job_id: str):
    """
    📊 **Polling Fallback: Get Current Progress**

    Returns the current progress status for a job.
    Use this as a fallback if SSE is not available.

    **Stages:** uploading → separating → transcribing → analyzing → generating → complete
    """
    progress_service = get_progress_service()
    job = progress_service.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found",
        )

    return _job_to_response(job)


@router.delete("/progress/{job_id}")
async def delete_progress(job_id: str):
    """
    🗑️ **Delete Job Progress**

    Remove a job from progress tracking.
    Useful for cleanup after processing completes.
    """
    progress_service = get_progress_service()
    deleted = progress_service.delete_job(job_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found",
        )

    return {"message": f"Job '{job_id}' deleted"}


@router.get("/health/progress")
async def health_check():
    """Health check for progress service."""
    progress_service = get_progress_service()
    return {
        "status": "ok",
        "active_jobs": len(progress_service._jobs),
    }
