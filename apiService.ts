// ekho-frontend/src/services/apiService.ts
import type {
    AvatarCreationRequest,
    VideoGenerationResponse,
    VideoStatusResponse,
    ChatRequest,
    ChatResponse,
    HealthCheckResponse,
    CloneVoiceResponse
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL;

const fetchApi = async <T>(endpoint: string, options: RequestInit): Promise<T> => {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, options);

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown API error' }));
        throw new Error(`API Error: ${response.status} - ${error.detail || 'Failed to fetch'}`);
    }

    return response.json() as Promise<T>;
};

export const createAvatar = (data: AvatarCreationRequest): Promise<VideoGenerationResponse> => {
    return fetchApi<VideoGenerationResponse>('/generate-avatar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
};

export const getVideoStatus = (jobId: string): Promise<VideoStatusResponse> => {
    return fetchApi<VideoStatusResponse>(`/video-status/${jobId}`, {
        method: 'GET',
    });
};

export const sendMessage = (data: ChatRequest): Promise<ChatResponse> => {
    return fetchApi<ChatResponse>('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
};

export const getHealthStatus = (): Promise<HealthCheckResponse> => {
    // Calls the FastAPI endpoint GET /api/v1/health
    return fetchApi<HealthCheckResponse>('/health', {
        method: 'GET',
    });
};

export const cloneVoice = (userId: string, audioFile: File): Promise<CloneVoiceResponse> => {
    const formData = new FormData();
    formData.append("audio_file", audioFile);
    
    // Note: No 'Content-Type': 'application/json' header for FormData
    return fetchApi<CloneVoiceResponse>(`/clone-voice/${userId}`, {
        method: 'POST',
        body: formData,
    });
};