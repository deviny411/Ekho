// ekho-frontend/src/components/ChatInterface.tsx

import React, { useState, useEffect, useCallback } from 'react';
import { sendMessage, getVideoStatus } from '../services/apiService';
import type { ChatRequest, ChatResponse } from '../types/api'; 
// Note: VideoStatusResponse is intentionally not imported directly as it's not needed by name here

const USER_ID = "test-user-001"; 

// --- MODIFIED INTERFACE (Audio fields kept for type safety but always null) ---
interface ChatHistoryItem extends ChatResponse {
    userMessage: string;
    isPolling: boolean;
    error: string | null;
    // REMOVED: audioBlobUrl: string | null; 
}
// --- END MODIFIED INTERFACE ---


const ChatInterface: React.FC = () => {
    const [input, setInput] = useState('');
    const [history, setHistory] = useState<ChatHistoryItem[]>([]);
    const [isSending, setIsSending] = useState(false);

    // REMOVED: fetchAndPlayAudio function is no longer needed.


    // --- 1. Polling Logic Hook (Only for Video Status) ---
    useEffect(() => {
        const pollingInterval = setInterval(() => {
            history.forEach((item, index) => {
                // Only poll for video if a valid job ID exists
                if (item.video_job_id && item.isPolling && item.video_job_id !== "submitted_in_background") {
                    
                    getVideoStatus(item.video_job_id!).then(status => {
                        if (status.status === 'completed' || status.status === 'failed') {
                            setHistory(prev => {
                                const newHistory = [...prev];
                                if (newHistory[index]) {
                                    newHistory[index] = {
                                        ...newHistory[index],
                                        video_url: status.video_url,
                                        isPolling: false,
                                        error: status.error,
                                    };
                                }
                                return newHistory;
                            });
                        } else {
                            setHistory(prev => {
                                const newHistory = [...prev];
                                if (newHistory[index]) {
                                    newHistory[index] = {
                                        ...newHistory[index],
                                        video_url: `Processing: ${status.progress}%`, 
                                    };
                                }
                                return newHistory;
                            });
                        }
                    }).catch(error => {
                        console.error("Polling error:", error);
                        setHistory(prev => {
                            const newHistory = [...prev];
                            if (newHistory[index]) {
                                newHistory[index] = { ...newHistory[index], error: "Polling failed", isPolling: false }; 
                            }
                            return newHistory;
                        });
                    });
                } 
                // Handle the placeholder status for the user
                else if (item.video_job_id === "submitted_in_background" && item.isPolling) {
                    setHistory(prev => {
                        const newHistory = [...prev];
                        if (newHistory[index]) {
                            newHistory[index] = {
                                ...newHistory[index],
                                video_url: "Video job submitted. Status pending...", 
                                isPolling: false, // Stop the polling interval for this item
                            };
                        }
                        return newHistory;
                    });
                }
            });
        }, 5000); 

        return () => clearInterval(pollingInterval);
    }, [history]); 


    // --- 2. Submission Handler (CLEANED) ---
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isSending) return;

        const userMessage = input;
        setInput('');
        setIsSending(true);

        const tempItem: ChatHistoryItem = {
            userMessage: userMessage,
            text: "Waiting for response...", 
            isPolling: false,
            error: null,
            audio_url: null, // Always null now
            video_url: null, 
            video_job_id: null,
            mode: null,
            emotional_tone: null
        };
        
        const currentItemIndex = 0; 
        setHistory(h => [tempItem, ...h]);
        
        try {
            const request: ChatRequest = {
                user_id: USER_ID,
                message: userMessage,
                make_video: true, 
            };
            
            const response = await sendMessage(request);

            setHistory(prev => {
                const newHistory = [...prev];
                if (newHistory[currentItemIndex]) { 
                    newHistory.splice(currentItemIndex, 1, {
                        ...response,
                        userMessage: userMessage,
                        isPolling: !!response.video_job_id,
                        error: null, 
                    } as ChatHistoryItem);
                }
                return newHistory;
            });
            
            // REMOVED: Audio fetch and play logic

        } catch (error: any) {
            console.error('Chat submission failed:', error);
            setHistory(prev => {
                const newHistory = [...prev];
                if (newHistory[currentItemIndex]) {
                    newHistory.splice(currentItemIndex, 1, { 
                        ...tempItem, 
                        text: "Connection failed. Please check backend.",
                        error: error.message || String(error)
                    } as ChatHistoryItem);
                }
                return newHistory;
            });
        } finally {
            setIsSending(false);
        }
    };


    // --- 3. Render Method (CLEANED) ---
    // --- 3. Render Method (CLEANED) ---
    return (
        <div className="chat-interface" style={{ maxWidth: '800px', margin: '0 auto' }}>
            <h2>Future Self Chat ({USER_ID})</h2>
            <div className="chat-history-container">
                {/* Ensure map renders in reverse if you want newest messages on top */}
                {history.map((item, index) => (
                    // Group the user message and AI response for clear styling
                    <div key={index}>
                        
                        {/* User Message */}
                        <div className="chat-item-user">
                            <p style={{ fontWeight: 600 }}>You:</p>
                            <p style={{ margin: 0, padding: '10px 15px', borderRadius: '8px', backgroundColor: '#d1e0fc', display: 'inline-block', maxWidth: '80%' }}>
                                {item.userMessage}
                            </p>
                        </div>

                        {/* AI Response */}
                        <div className="chat-item-ai">
                            <p style={{ fontWeight: 600 }}>Future Self:</p>
                            <p style={{ margin: '5px 0' }}>{item.text}</p>
                            
                            {/* Metadata */}
                            <p className="chat-metadata">
                                Tone: {item.emotional_tone || 'N/A'} | Mode: {item.mode || 'N/A'}
                            </p>
                            
                            {/* Video Status */}
                            {item.isPolling && <p style={{ color: '#3b82f6', marginTop: '10px' }}>⏳ Video Job {item.video_job_id}: {item.video_url || 'Starting...'}</p>}
                            {item.video_url && item.video_url.startsWith('http') && (
                                 <video 
                                    src={item.video_url} 
                                    controls 
                                    style={{ width: '100%', marginTop: '15px' }} 
                                />
                            )}
                            {item.error && <p style={{ color: 'red', marginTop: '10px' }}>❌ Fatal Error: {item.error}</p>}
                        </div>

                    </div>
                ))}
            </div>
            
            <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px', marginTop: '15px' }}>
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={isSending ? "Waiting for AI response..." : "Ask your future self..."}
                    disabled={isSending}
                    style={{ flexGrow: 1 }}
                />
                <button type="submit" disabled={isSending}>
                    {isSending ? 'Sending...' : 'Send'}
                </button>
            </form>
        </div>
    );
};

export default ChatInterface;