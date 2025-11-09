import asyncio
import librosa
import numpy as np
import io
import soundfile as sf
from typing import Dict, Any

class VoiceAnalyzer:
    """
    Service to extract biometric voice features using Librosa.
    Based on Feature 7 from the project documentation.
    """
    
    def __init__(self):
        print("✅ VoiceAnalyzer Service initialized.")

    def _analyze_sync(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Synchronous (blocking) helper to run librosa analysis.
        """
        try:
            # Use soundfile to decode the audio (MP3, WAV, etc.) into a numpy array
            audio_io = io.BytesIO(audio_data)
            y, sr = sf.read(audio_io)
            
            # If stereo, convert to mono
            if y.ndim > 1:
                y = y.mean(axis=1)
                
            # Convert to a format librosa.load understands (float)
            y_float = y.astype(np.float32)
            
            # --- Feature Extraction ---
            
            # 1. Pitch (Fundamental Frequency)
            pitch_f0, _, _ = librosa.pyin(y_float, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
            pitch_mean = np.nanmean(pitch_f0) if not np.all(np.isnan(pitch_f0)) else 0.0

            # 2. Speech Rate (Tempo)
            onset_env = librosa.onset.onset_detect(y=y_float, sr=sr)
            tempo_frames = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
            speech_rate = np.mean(tempo_frames) if tempo_frames.size > 0 else 0.0
            
            # 3. Pause Frequency
            silent_parts = librosa.effects.split(y_float, top_db=40) # 40dB below max
            pause_count = len(silent_parts) - 1
            duration_sec = len(y_float) / sr
            pause_frequency = (pause_count / duration_sec) if duration_sec > 0 else 0.0

            # 4. Volume Variance
            rms_energy = librosa.feature.rms(y=y_float)
            volume_variance = np.var(rms_energy) if rms_energy.size > 0 else 0.0

            features = {
                "pitch_mean_hz": float(pitch_mean),
                "speech_rate_bpm": float(speech_rate),
                "pause_frequency_hz": float(pause_frequency),
                "volume_variance": float(volume_variance),
                "duration_sec": float(duration_sec),
            }
            
            print(f"✅ Voice analysis complete: {features}")
            return features

        except Exception as e:
            print(f"❌ Librosa analysis failed: {e}")
            return {
                "pitch_mean_hz": 0.0,
                "speech_rate_bpm": 0.0,
                "pause_frequency_hz": 0.0,
                "volume_variance": 0.0,
                "duration_sec": 0.0,
                "error": str(e)
            }

    async def analyze_voice_features(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Asynchronously runs the blocking librosa analysis in a separate thread.
        """
        return await asyncio.to_thread(self._analyze_sync, audio_data)
    
async def get_best_matching_default_voice_from_audio(client, audio_data: bytes) -> str:
    """
    Use VoiceAnalyzer to extract features from the audio and pick
    the closest default voice based on pitch.
    """
    analyzer = VoiceAnalyzer()
    features = await analyzer.analyze_voice_features(audio_data)
    pitch = features.get("pitch_mean_hz", 0)

    # Simple heuristic for gender
    if pitch < 165:
        desired_gender = "male"
    elif pitch > 255:
        desired_gender = "female"
    else:
        desired_gender = "neutral"

    # Fetch available voices
    voices_resp = client.voices.search(page_size=50)
    voices = voices_resp.voices

    # Filter voices by gender if possible
    filtered = [v for v in voices if getattr(v, "gender", "").lower() == desired_gender]
    if not filtered:
        filtered = voices  # fallback to any voice

    return filtered[0].voice_id if filtered else None
