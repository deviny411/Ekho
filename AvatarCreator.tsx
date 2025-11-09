// ekho-frontend/src/components/AvatarCreator.tsx

import React, { useState, useEffect } from 'react';
import type { ChangeEvent } from 'react';
import { createAvatar, getVideoStatus } from '../services/apiService';
import type { AvatarCreationRequest, VideoStatusResponse } from '../types/api';

const USER_ID = "test-user-001"; 
const MAX_CAPTURES = 5; 

const AvatarCreator: React.FC = () => {
    const [captures, setCaptures] = useState<string[]>([]);
    const [ageYears, setAgeYears] = useState(10);
    const [jobId, setJobId] = useState<string | null>(null);
    const [status, setStatus] = useState<VideoStatusResponse | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // --- Image File Handler (converts to Base64) ---
    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (!files) return;

        setError(null);
        setCaptures([]); 

        Array.from(files).slice(0, MAX_CAPTURES).forEach(file => {
            if (file) {
                const reader = new FileReader();
                reader.onloadend = () => {
                    setCaptures(prev => {
                        if (prev.length < MAX_CAPTURES) {
                            return [...prev, reader.result as string];
                        }
                        return prev;
                    });
                };
                reader.readAsDataURL(file);
            }
        });
    };

    // --- Job Submission ---
    const handleSubmit = async () => {
        if (captures.length < 3) { 
            setError("Please upload at least 3 face captures.");
            return;
        }

        setIsSubmitting(true);
        setError(null);
        setJobId(null);
        setStatus(null);

        try {
            const request: AvatarCreationRequest = {
                user_id: USER_ID,
                face_captures: captures,
                age_progression_years: ageYears,
            };
            
            const response = await createAvatar(request);

            setJobId(response.job_id);
            setStatus({ 
                job_id: response.job_id, 
                status: response.status as VideoStatusResponse['status'], 
                progress: 0,
                video_url: null,
                error: null,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            });
        } catch (err: any) {
            setError(err.message || "Failed to start avatar generation job.");
        } finally {
            setIsSubmitting(false);
        }
    };


    // --- Polling Logic ---
    useEffect(() => {
        if (!jobId || status?.status === 'completed' || status?.status === 'failed') {
            return;
        }

        const intervalId = setInterval(async () => {
            try {
                const currentStatus = await getVideoStatus(jobId);
                setStatus(currentStatus);

                if (currentStatus.status === 'completed' || currentStatus.status === 'failed') {
                    clearInterval(intervalId);
                }
            } catch (err) {
                console.error("Polling failed:", err);
                setStatus(s => s ? {...s, status: 'failed', error: String(err)} : null);
                clearInterval(intervalId);
            }
        }, 8000); 

        return () => clearInterval(intervalId);
    }, [jobId, status?.status]);


    // --- Render Logic ---
    const isJobActive = !!(jobId && status?.status !== 'completed' && status?.status !== 'failed');

    return (
        <div className="feature-card"> 
            <h3 style={{ marginTop: 0, color: 'var(--color-accent)' }}>📸 Create Future Avatar</h3>
            <p style={{ color: '#aaa', fontSize: '0.95em' }}>
                Upload 3-5 high-quality face photos to generate your aged video avatar.
            </p>
            
            {/* Input Controls */}
            <div style={{ marginBottom: '20px', padding: '15px 0', borderTop: '1px solid #333', borderBottom: '1px solid #333' }}>
                <label style={{ display: 'block', marginBottom: '10px', fontWeight: 500 }}>
                    Age Progression: <span style={{ color: 'var(--color-accent)' }}>{ageYears} Years</span>
                </label>
                <input 
                    type="range" 
                    min="3" 
                    max="10" 
                    value={ageYears} 
                    onChange={(e) => setAgeYears(Number(e.target.value))} 
                    disabled={isJobActive}
                    style={{ width: '100%', padding: '0', height: '8px', cursor: isJobActive ? 'not-allowed' : 'pointer' }}
                />
            </div>
            
            <input 
                type="file" 
                accept="image/jpeg, image/png" 
                multiple 
                onChange={handleFileChange} 
                disabled={isJobActive}
            />

            <p style={{ marginTop: '15px', fontWeight: 400 }}>
                Images Selected: <span style={{ color: 'var(--color-accent)' }}>{captures.length}</span> / {MAX_CAPTURES} (Min 3 required)
            </p>

            <button 
                onClick={handleSubmit} 
                disabled={isSubmitting || captures.length < 3 || isJobActive}
                style={{ background: isJobActive ? '#555' : 'var(--color-accent)', marginTop: '20px' }}
            >
                {isSubmitting ? 'Submitting...' : isJobActive ? `Generating (${status?.progress}%)` : 'Generate Avatar'}
            </button>
            
            {error && <p className="message-error" style={{ marginTop: '15px' }}>❌ {error}</p>}

            {/* --- Job Status Display --- */}
            {jobId && (
                <div style={{ borderTop: '1px solid var(--color-border)', marginTop: '25px', paddingTop: '20px' }}>
                    <h4 style={{ margin: '0 0 10px 0', color: '#ccc' }}>Job Status: {jobId}</h4>
                    <p>Status: <strong style={{ color: isJobActive ? 'var(--color-accent-hover)' : (status?.status === 'completed' ? 'var(--color-success)' : 'var(--color-error)') }}>{status?.status.toUpperCase()}</strong></p>
                    <p>Progress: {status?.progress}%</p>

                    {/* Display Video or Error */}
                    {status?.video_url && status.status === 'completed' ? (
                        <div>
                            <p className="message-success">✅ Generation Complete!</p>
                            <video 
                                src={status.video_url} 
                                controls 
                                style={{ width: '100%', marginTop: '15px' }} 
                            />
                        </div>
                    ) : status?.status === 'failed' ? (
                        <p className="message-error">❌ Job Failed: {status.error || "Unknown error"}</p>
                    ) : (
                        <p style={{ color: '#aaa' }}>Estimated time: 60 seconds.</p>
                    )}
                </div>
            )}
        </div>
    );
};

export default AvatarCreator;