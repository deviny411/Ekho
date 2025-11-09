// ekho-frontend/src/components/VoiceCloner.tsx

import React, { useState } from 'react';
import type { ChangeEvent } from 'react';
import { cloneVoice } from '../services/apiService';
import type { CloneVoiceResponse } from '../types/api';

const USER_ID = "test-user-001"; 

const VoiceCloner: React.FC = () => {
    // audioFile is File | null, loading/error are boolean/string, response is the API object
    const [audioFile, setAudioFile] = useState<File | null>(null);
    const [response, setResponse] = useState<CloneVoiceResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files ? event.target.files[0] : null;
        setAudioFile(file);
        setResponse(null);
        setError(null);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!audioFile) {
            setError("Please select an audio file (MP3 or WAV) of your voice.");
            return;
        }

        setLoading(true);
        setError(null);
        setResponse(null);

        try {
            const result = await cloneVoice(USER_ID, audioFile);
            setResponse(result);
        } catch (err: any) {
            console.error("Voice cloning failed:", err);
            // Captures detailed error message from the API service
            setError(`Failed to clone voice: ${err.message || 'Check network or backend status.'}`);
        } finally {
            setLoading(false);
        }
    };

    // Derived boolean state variables (used for styling and logic)
    const isCloned = !!(response && response.status === 'cloned');
    const isButtonDisabled = loading || !audioFile || isCloned; 

    return (
        <div className="feature-card"> {/* <-- USE FEATURE CARD CLASS */}
            <h3 style={{ marginTop: 0, color: 'var(--color-accent)' }}>🎙️ Clone Your Future Self's Voice</h3>
            <p style={{ color: '#aaa', fontSize: '0.95em' }}>
                Upload a 30-second sample of your clean speech to enable personalized audio responses.
            </p>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <input 
                    type="file" 
                    accept="audio/*" 
                    onChange={handleFileChange} 
                    disabled={isButtonDisabled}
                    // Input file styling is handled by global CSS now
                />
                
                <button 
                    type="submit" 
                    disabled={isButtonDisabled}
                    style={{ background: isCloned ? 'var(--color-success)' : 'var(--color-accent)' }}
                >
                    {isCloned ? '✅ Voice Cloned' : loading ? 'Processing Voice...' : 'Start Voice Cloning'}
                </button>
            </form>

            {/* Status Display */}
            {response && (
                <div style={{ marginTop: '20px', borderTop: '1px solid var(--color-border)', paddingTop: '15px' }}>
                    <p className="message-success">
                        ✅ Voice Profile Created!
                    </p>
                    <p style={{ fontSize: '0.9em', color: '#ccc' }}>
                        Voice ID: {response.voice_id} (Ready for use in chat.)
                    </p>
                </div>
            )}
            
            {error && <p className="message-error" style={{ marginTop: '10px' }}>❌ {error}</p>}
        </div>
    );
};

export default VoiceCloner;