# app/services/elevenlabs_service.py

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from io import BytesIO
import asyncio
from app.config import get_settings
from app.services.voice_analysis import get_best_matching_default_voice_from_audio

class ElevenLabsService:
    def __init__(self):
        settings = get_settings()
        if not settings.elevenlabs_api_key:
            print("❌ ERROR: ELEVENLABS_API_KEY not set!")
            raise ValueError("ELEVENLABS_API_KEY not set")
            
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        print("✅ ElevenLabs Service initialized.")

    async def clone_voice(self, audio_data: bytes, user_id: str) -> str:
        """
        Attempts to clone a user's voice. If cloning fails (e.g., subscription restriction),
        falls back to a default voice.
        Returns a voice_id string.
        """
        try:
            audio_file = BytesIO(audio_data)
            
            # Try Instant Voice Cloning (IVC)
            voice = await asyncio.to_thread(
                self.client.voices.ivc.create,
                name=f"Ekho User - {user_id}",
                description=f"Voice clone for Ekho user {user_id}",
                files=[audio_file]
            )
            
            print(f"✅ Cloned voice for user {user_id}. Voice ID: {voice.voice_id}")
            return voice.voice_id
        
        except Exception as e:
            # Detect subscription restriction specifically
            msg = str(e).lower()
            if "can_not_use_instant_voice_cloning" in msg or "subscription" in msg:
                print(f"⚠️ Cannot clone voice for user {user_id}: {e}")
                # --- Call the voice matching function from voice_analysis.py ---
                voice_id = await get_best_matching_default_voice_from_audio(
                    client=self.client,
                    audio_data=audio_data
                )
                print(f"➡️ Using closest default voice ID: {voice_id}")
                return voice_id
            else:
                # Raise other exceptions
                print(f"❌ Failed to clone voice for user {user_id}: {e}")
                raise

    def get_default_voice_id(self) -> str:
        """
        Returns the ID of a default pre‑existing ElevenLabs voice.
        Picks the first available voice as fallback.
        """
        # Use the correct method to list/s\-search voices
        resp = self.client.voices.search(page_size=1)  # minimal query
        voices = resp.voices
        if not voices:
            raise RuntimeError("No voices available in ElevenLabs account!")
        return voices[0].voice_id




    # --- CREATE A SYNCHRONOUS HELPER FUNCTION ---
    # We put all the blocking logic in its own function.
    def _generate_speech_sync(self, text: str, voice_id: str) -> bytes:
        """
        Synchronous helper for audio generation.
        """
        try:
            voice_settings = VoiceSettings(
                stability=0.35,
                similarity_boost=0.75,
                style=0.2,
                use_speaker_boost=True
            )

            # This call blocks
            audio_chunks = self.client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=voice_settings
            )

            # This call also blocks
            audio_bytes = b"".join(chunk for chunk in audio_chunks)
            
            print(f"Generated speech for voice_id {voice_id}")
            return audio_bytes
        except Exception as e:
            print(f"❌ Failed to generate speech for voice_id {voice_id}: {e}")
            raise

    async def generate_speech(self, text: str, voice_id: str) -> bytes:
        """
        Converts text to speech using a cloned voice.
        Returns full audio bytes, non-blocking.
        """
        # --- 4. RUN THE HELPER FUNCTION IN A THREAD ---
        return await asyncio.to_thread(
            self._generate_speech_sync,
            text,
            voice_id
        )