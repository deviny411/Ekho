from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum

class VideoStyle(str, Enum):
    """Video generation style presets."""
    CINEMATIC = "cinematic"
    DOCUMENTARY = "documentary"
    CONVERSATIONAL = "conversational"
    EMOTIONAL = "emotional"

class VideoGenerationRequest(BaseModel):
    """Request model for video generation."""
    prompt: str = Field(..., min_length=10, max_length=1000)
    duration: int = Field(default=10, ge=5, le=30)
    reference_images: Optional[List[str]] = None  # Base64 encoded
    style: VideoStyle = VideoStyle.CONVERSATIONAL
    user_id: str

    @validator('reference_images')
    def validate_reference_images(cls, v):
        if v and len(v) > 5:
            raise ValueError('Maximum 5 reference images allowed')
        return v

class VideoGenerationResponse(BaseModel):
    """Response model for video generation."""
    job_id: str
    status: str
    message: str
    estimated_time_seconds: int

class VideoStatusResponse(BaseModel):
    """Response model for video status check."""
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: int  # 0-100
    video_url: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

class AvatarCreationRequest(BaseModel):
    """Request model for avatar creation."""
    user_id: str
    face_captures: List[str] = Field(..., min_items=3, max_items=5)  # Base64 images
    voice_sample: Optional[str] = None  # Base64 audio (for future)
    age_progression_years: int = Field(default=5, ge=3, le=10)

    @validator('face_captures')
    def validate_face_captures(cls, v):
        if not v or len(v) < 3:
            raise ValueError('At least 3 face captures required')
        return v

class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    timestamp: str
    google_cloud_connected: bool

# -------------------------
# Chat models
# -------------------------
class ChatRequest(BaseModel):
    user_id: str
    message: str = Field(..., min_length=1, max_length=2000)
    make_video: bool = False  # NEW: optionally kick off a Veo clip

class ChatResponse(BaseModel):
    text: str
    video_url: Optional[str] = None
    video_job_id: Optional[str] = None  # NEW: return job id if make_video=True
    mode: Optional[str] = None
    emotional_tone: Optional[str] = None
