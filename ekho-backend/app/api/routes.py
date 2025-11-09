from fastapi import (
    APIRouter, HTTPException, BackgroundTasks, 
    UploadFile, File, Path
)
from typing import Optional, List
from datetime import datetime, timezone
from app.config import get_settings
import asyncio # <-- IMPORT ASYNCIO

# --- 1. IMPORT ALL SCHEMAS ---
from app.models.schemas import (
    VideoGenerationRequest,
    VideoGenerationResponse,
    VideoStatusResponse,
    AvatarCreationRequest,
    HealthCheckResponse,
    ChatRequest,
    ChatResponse,
    CloneVoiceResponse,
)
# --- 2. IMPORT ALL SERVICES ---
from app.services.veo_service import VeoServiceREST
from app.services.storage_service import StorageService
from app.services.mongodb_service import MongoDBService
from app.services.snowflake_service import SnowflakeService
from app.services.gemini_service import GeminiService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.voice_analysis import VoiceAnalyzer # <-- IMPORT NEW SERVICE
# 🔹 ADK orchestration
from app.services.adk_service import ADKAgentService

router = APIRouter(prefix="/api/v1", tags=["ekho"])

# --- 3. LOAD SETTINGS & INSTANTIATE ALL SERVICES ---
settings = get_settings()

storage_service = StorageService()
mongodb_service = MongoDBService()
snowflake_service = SnowflakeService()
gemini_service = GeminiService()
elevenlabs_service = ElevenLabsService()
voice_analyzer = VoiceAnalyzer() # <-- INSTANTIATE NEW SERVICE
adk_service = ADKAgentService()


default_output_uri = f"gs://{settings.storage_bucket}/video-outputs/"

veo_service = VeoServiceREST(project_id=settings.google_cloud_project,
                             location=settings.google_cloud_location,
                             model_id="veo-3.1-generate-preview",
                             output_storage_uri=default_output_uri
                             )


# --- 4. HELPER FUNCTION ---
def _calculate_sentiment(emotional_tag: str) -> float:
    """Converts a string emotion tag into a numeric score for analytics."""
    tag = (emotional_tag or "").lower()
    if tag in ["anxious", "sad", "worried", "error"]:
        return -0.5
    if tag in ["happy", "hopeful", "calm", "energetic", "positive"]:
        return 0.5
    return 0.0




# --- 5. ALL API ENDPOINTS ---

@router.post("/clone-voice/{user_id}", response_model=CloneVoiceResponse)
async def clone_voice(
    user_id: str = Path(..., description="The user ID to associate the voice with"), 
    audio_file: UploadFile = File(...)
):
    """
    Accepts a 30-sec audio file, clones the voice,
    analyzes its features, and saves all data.
    """
    try:
        # Read file once, then run tasks in parallel
        audio_bytes = await audio_file.read()
        
        clone_task = elevenlabs_service.clone_voice(audio_bytes, user_id)
        analysis_task = voice_analyzer.analyze_voice_features(audio_bytes)
        
        # Run both operations concurrently
        results = await asyncio.gather(clone_task, analysis_task)
        
        voice_id = results[0]
        voice_features = results[1]
        
        # --- SAVE ALL RESULTS ---
        
        # 1. Save the new voice_id to the user's profile in MongoDB
        await mongodb_service.update_user_profile(
            user_id,
            {"voice_id": voice_id}
        )
        
        # 2. Save the voice features to Snowflake
        if voice_features and "error" not in voice_features:
            await snowflake_service.log_voice_analytic(
                user_id, 
                voice_features, 
                tag="baseline_onboarding"
            )
        
        return CloneVoiceResponse(
            user_id=user_id,
            voice_id=voice_id,
            status="cloned"
        )
        
    except Exception as e:
        print(f"❌ Failed to clone voice for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint to verify service is running."""
    # check_connection is now async, so it must be awaited
    storage_connected = await storage_service.check_connection() # <-- FIXED
    return HealthCheckResponse(
        status="healthy" if storage_connected else "degraded",
        service="ekho-api",
        timestamp=datetime.now(timezone.utc).isoformat(),
        google_cloud_connected=storage_connected,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Legacy, fuller chat flow retained (fixed to use existing Gemini method)
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/chat_full", response_model=ChatResponse)
async def chat_full(request: ChatRequest):
    """
    Handle a user's chat message and return an AI response.
    Orchestrates MongoDB, Gemini, Snowflake, and optionally Veo.
    """
    try:
        # 1) Get user data & history from MongoDB
        user_profile = await mongodb_service.get_user_profile(request.user_id)
        if not user_profile:
            user_profile = {"user_id": request.user_id, "name": "User"}
        history = await mongodb_service.get_conversation_history(request.user_id)
        print(f"Retrieved {len(history)} history items for user {request.user_id}")
        
        # 2) Generate text via the working Gemini wrapper
        # gemini_service.generate is async, so it must be awaited
        reply_text = await gemini_service.generate( # <-- FIXED
            user_message=request.message, user_name=request.user_id
        )

        # Derive mode/tone locally
        mode = adk_service.detect_mode(request.message)
        tone = adk_service.tag_emotion(reply_text)

        # 3) Optional Veo kick-off (best-effort)
        video_url_to_return: Optional[str] = None
        video_job_id_to_return: Optional[str] = None

        if getattr(request, "make_video", False):
            try:
                # --- BUG FIX: Get avatar refs from user_profile ---
                avatar_refs = user_profile.get("avatar_reference_urls", []) 

                video_job_result = await veo_service.generate_avatar_video(
                    user_id=request.user_id,
                    prompt=reply_text,
                    reference_images=avatar_refs, # <-- FIXED
                    duration=max(5, min(30, len(reply_text) // 15)),
                    style="conversational",
                )
                video_job_id_to_return = video_job_result.get("job_id")
            except Exception as e:
                print(f"❌ Error during video job kickoff: {str(e)}")
                video_job_id_to_return = f"error: {str(e)}"
        else:
            video_url_to_return = "https://storage.googleapis.com/ekho-placeholder-video.mp4"

        # 4) Save conversation to MongoDB
        await mongodb_service.save_conversation(
            user_id=request.user_id,
            user_message=request.message,
            ai_response=reply_text,
            emotional_tag=tone,
            mode=mode,
        )

        # 5) Log analytics to Snowflake (best-effort)
        try:
            sentiment_score = _calculate_sentiment(tone)
            await snowflake_service.log_conversation_analytic(
                user_id=request.user_id,
                emotional_tag=tone,
                conversation_mode=mode,
                sentiment_score=sentiment_score,
            )
        except Exception as e:
            print(f"Snowflake logging failed: {e}")

        # 6) Return response
        return ChatResponse(
            text=reply_text,
            video_url=video_url_to_return,
            video_job_id=video_job_id_to_return,
            mode=mode,
            emotional_tone=tone,
        )

    except Exception as e:
        print(f"❌ Error in /chat_full endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# MVP Chat + ADK orchestration (primary endpoint used by Swagger/frontend)
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    User sends message, get AI response text.
    If make_video=True, also start Veo generation and ElevenLabs audio.
    ADK orchestrates memory/pattern/safety and logs post-chat.
    """
    try:
        user_id = req.user_id
        message = req.message

        # 1) Run ADK agents in parallel (memory, trends, safety)
        ctx = await adk_service.orchestrate(user_id, message)
        suggested_mode = ctx.get("suggested_mode") or adk_service.detect_mode(message)
        
        voice_id = ctx.get("voice_id") # Fetched from user profile via ADK

        # 2) Generate a warm reply (Gemini wrapper or stub)
        reply_text = await gemini_service.generate(message, user_name=user_id) # <-- FIXED

        # 3) Optionally kick off Veo video & ElevenLabs audio
        video_job_id: Optional[str] = None
        audio_url: Optional[str] = None

        if getattr(req, "make_video", False):
            # --- Veo Generation (existing code) ---
            try:
                avatar_refs = ctx.get("avatar_reference_urls", []) # Get refs from ADK context
                
                result = await veo_service.generate_avatar_video(
                    user_id=user_id,
                    prompt=reply_text,
                    reference_images=avatar_refs, # <-- Use real refs
                    duration=10,
                    style="conversational",
                )
                video_job_id = result.get("job_id")
            except Exception as e:
                print("⚠️ Veo kick-off failed in /chat:", e)

            # --- NEW: ElevenLabs Audio Generation ---
            if voice_id:
                try:
                    audio_bytes = await elevenlabs_service.generate_speech(
                        text=reply_text,
                        voice_id=voice_id
                    
                    )
                    audio_gcs_path = f"users/{user_id}/audio/{datetime.now(timezone.utc).isoformat()}.mp3"
                    await storage_service.upload_file_bytes(
                        audio_bytes,
                        audio_gcs_path,
                        content_type="audio/mpeg"
                    )
                    
                    audio_url = await storage_service.get_signed_url(audio_gcs_path)

                except Exception as e:
                    print(f"⚠️ ElevenLabs audio generation failed in /chat: {e}")
            else:
                print(f"⚠️ No voice_id found for user {user_id}. Skipping audio generation.")
            # --- END NEW ---

        # 4) Persist chat & analytics via ADK helper
        log_meta = await adk_service.log_after_chat(
            user_id=user_id,
            user_message=message,
            ai_response=reply_text,
            mode=suggested_mode,
        )

        # 5) Return response
        return ChatResponse(
            text=reply_text,
            video_url=None,
            video_job_id=video_job_id,
            audio_url=audio_url,
            mode=log_meta.get("mode", suggested_mode),
            emotional_tone=log_meta.get("emotional_tag", "neutral"),
        )

    except Exception as e:
        print(f"❌ Error in /chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-avatar", response_model=VideoGenerationResponse)
async def generate_avatar(
    request: AvatarCreationRequest, background_tasks: BackgroundTasks
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
            age_years=request.age_progression_years,
        )
        
        # --- NEW ---
        # After avatar is created, save the reference image URIs to the profile
        if result.get("gcs_uris"):
            await mongodb_service.update_user_profile(
                request.user_id,
                {"avatar_reference_urls": result.get("gcs_uris")}
            )
        # --- END NEW ---

        return VideoGenerationResponse(
            job_id=result["job_id"],
            status=result["status"],
            message=f"Avatar generation started. Creating your future self aged {request.age_progression_years} years...",
            estimated_time_seconds=60,
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
            style=request.style.value,  # ensure enum -> str
        )

        return VideoGenerationResponse(
            job_id=result["job_id"],
            status=result["status"],
            message="Video generation started",
            estimated_time_seconds=request.duration * 3,
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
            job_id=status.get("job_id", job_id),
            status=status.get("status", "unknown"),
            progress=status.get("progress", 0),
            video_url=status.get("video_url"),
            error=status.get("error"),
            created_at=status.get("created_at", ""),
            updated_at=status.get("updated_at", ""),
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