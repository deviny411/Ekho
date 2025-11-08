from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List

from app.models.schemas import (
    VideoGenerationRequest,
    VideoGenerationResponse,
    VideoStatusResponse,
    AvatarCreationRequest,
    HealthCheckResponse,
    ChatRequest,
    ChatResponse
)
from app.services.veo_service import VeoService
from app.services.storage_service import StorageService
from app.services.mongodb_service import MongoDBService
from app.services.snowflake_service import SnowflakeService
from app.services.gemini_service import GeminiService #TODO: Needs gemini service implementation
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1", tags=["ekho"])

storage_service = StorageService()
veo_service = VeoService()
mongodb_service = MongoDBService()
snowflake_service = SnowflakeService()
gemini_service = GeminiService()

def _calculate_sentiment(emotional_tag: str) -> float:
    """Converts a string emotion tag into a numeric score for analytics."""
    tag = emotional_tag.lower()
    if tag in ["anxious", "sad", "worried", "error"]:
        return -0.5
    if tag in ["happy", "hopeful", "calm", "energetic"]:
        return 0.5
    return 0.0

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint to verify service is running."""
    
    storage_connected = storage_service.check_connection()
    
    return HealthCheckResponse(
        status="healthy" if storage_connected else "degraded",
        service="ekho-api",
        timestamp=datetime.now(timezone.utc).isoformat(),
        google_cloud_connected=storage_connected
    )

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Handle a user's chat message.
    This uses a MOCK AI response to test the MongoDB and Snowflake data pipeline.
    """
    try:
        # 1. Get user data & history from MongoDB (to prove it's working)
        user_profile = await mongodb_service.get_user_profile(request.user_id)
        if not user_profile:
            user_profile = {"user_id": request.user_id, "name": "User"}
        
        history = await mongodb_service.get_conversation_history(request.user_id)
        print(f"Retrieved {len(history)} history items for user {request.user_id}")

        # 2. --- MOCK GEMINI RESPONSE ---
        # This block simulates the output from GeminiService
        gemini_response = await gemini_service.generate_response(
            user_message=request.message,
            conversation_history=history,
            user_profile=user_profile,
            mode=request.mode
        )
        # -------------------------------
        
        # 3. (Future) Generate short video clip of avatar
        video_url_placeholder = "https://storage.googleapis.com/ekho-placeholder-video.mp4"

        # 4. Save conversation to MongoDB
        await mongodb_service.save_conversation(
            user_id=request.user_id,
            user_message=request.message,
            ai_response=gemini_response["text"],
            emotional_tag=gemini_response["emotional_tone"],
            mode=gemini_response["mode"]
        )

        # 5. Log analytics to Snowflake
        try:
            sentiment_score = _calculate_sentiment(gemini_response["emotional_tone"])
            await snowflake_service.log_conversation_analytic(
                user_id=request.user_id,
                emotional_tag=gemini_response["emotional_tone"],
                conversation_mode=gemini_response["mode"],
                sentiment_score=sentiment_score
            )
        except Exception as e:
            # Don't fail the chat request if analytics fails
            print(f"Snowflake logging failed: {e}")

        # 6. Return response text + video URL
        return ChatResponse(
            text=gemini_response["text"],
            video_url=video_url_placeholder, # Use placeholder for now
            mode=gemini_response["mode"],
            emotional_tone=gemini_response["emotional_tone"]
        )
        
    except Exception as e:
        print(f"❌ Error in /chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
