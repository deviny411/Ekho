// ekho-frontend/src/types/api.ts

// --- Requests ---
export interface AvatarCreationRequest {
    user_id: string;
    face_captures: string[]; // Base64 strings
    age_progression_years: number;
}

export interface ChatRequest {
    user_id: string;
    message: string;
    make_video: boolean;
}

// --- Responses (based on backend schemas) ---
export interface VideoGenerationResponse {
    job_id: string;
    status: string;
    message: string;
    estimated_time_seconds: number;
}

export interface VideoStatusResponse {
    job_id: string;
    status: 'pending' | 'processing' | 'completed' | 'failed' | 'unknown';
    progress: number; // 0-100
    video_url: string | null;
    error: string | null;
    created_at: string;
    updated_at: string;
}

export interface ChatResponse {
    text: string;
    video_url: string | null; 
    video_job_id: string | null; 
    audio_url: string | null; // Signed URL for generated ElevenLabs audio
    mode: string | null;
    emotional_tone: string | null;
}

export interface HealthCheckResponse {
    status: string;
    service: string;
    timestamp: string;
    google_cloud_connected: boolean;
}

// --- NEW Voice Cloning Response ---
export interface CloneVoiceResponse {
    user_id: string;
    voice_id: string;
    status: string; // e.g., "cloned"
}