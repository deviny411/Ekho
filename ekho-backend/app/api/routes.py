from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List

from app.models.schemas import (
    VideoGenerationRequest,
    VideoGenerationResponse,
    VideoStatusResponse,
    AvatarCreationRequest,
    HealthCheckResponse
)
from app.services.veo_service import veo_service
from app.services.storage_service import storage_service
from datetime import datetime

router = APIRouter(prefix="/api/v1", tags=["ekho"])

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint to verify service is running."""
    
    storage_connected = storage_service.check_connection()
    
    return HealthCheckResponse(
        status="healthy" if storage_connected else "degraded",
        service="ekho-api",
        timestamp=datetime.utcnow().isoformat(),
        google_cloud_connected=storage_connected
    )

@router.post("/generate-avatar", response_model=VideoGenerationResponse)
async def generate_avatar(
    request: AvatarCreationRequest,
    background_tasks: BackgroundTasks
):
    """
    Create aged avatar video from face captures.
    Main endpoint for onboarding flow.
    """
    
    try:
        print(f"📸 Creating avatar for user: {request.user_id}")
        print(f"   - Face captures: {len(request.face_captures)}")
        print(f"   - Age progression: {request.age_progression_years} years")
        
        result = await veo_service.create_aged_avatar(
            user_id=request.user_id,
            face_captures=request.face_captures,
            age_years=request.age_progression_years
        )
        
        return VideoGenerationResponse(
            job_id=result["job_id"],
            status=result["status"],
            message=f"Avatar generation started. Creating your future self aged {request.age_progression_years} years...",
            estimated_time_seconds=60
        )
        
    except Exception as e:
        print(f"❌ Error creating avatar: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-video", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """
    Generate custom video with Veo.
    Used for monthly recaps and custom content.
    """
    
    try:
        print(f"🎬 Generating video for user: {request.user_id}")
        print(f"   - Prompt: {request.prompt[:50]}...")
        print(f"   - Duration: {request.duration}s")
        print(f"   - Style: {request.style}")
        
        result = await veo_service.generate_avatar_video(
            user_id=request.user_id,
            prompt=request.prompt,
            reference_images=request.reference_images or [],
            duration=request.duration,
            style=request.style
        )
        
        return VideoGenerationResponse(
            job_id=result["job_id"],
            status=result["status"],
            message="Video generation started",
            estimated_time_seconds=result["duration"] * 3
        )
        
    except Exception as e:
        print(f"❌ Error generating video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/video-status/{job_id}", response_model=VideoStatusResponse)
async def get_video_status(job_id: str):
    """
    Check status of video generation job.
    Frontend polls this endpoint for updates.
    """
    
    try:
        status = await veo_service.get_job_status(job_id)
        
        return VideoStatusResponse(
            job_id=status["job_id"],
            status=status["status"],
            progress=status.get("progress", 0),
            video_url=status.get("video_url"),
            error=status.get("error"),
            created_at=status.get("created_at", ""),
            updated_at=status.get("updated_at", "")
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/jobs")
async def get_user_jobs(user_id: str):
    """Get all video generation jobs for a user."""
    
    try:
        jobs = veo_service.list_user_jobs(user_id)
        return {"user_id": user_id, "jobs": jobs, "count": len(jobs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
