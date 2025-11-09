# app/services/gemini_service.py
import os
from app.config import get_settings

try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None

class GeminiService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.enabled = False
        self.model = None

        if self.api_key and genai:
            try:
                genai.configure(api_key=self.api_key)
                # fast & cheap for hackathons; swap if you want
                self.model = genai.GenerativeModel("gemini-2.0-flash")
                self.enabled = True
                print("✅ Gemini initialized")
            except Exception as e:
                print("⚠️ Gemini init failed:", e)

    def generate(self, user_message: str, user_name: str = "you") -> str:
        """
        Return a text reply. This method NEVER raises; it returns a stub if SDK/key fail.
        """
        prompt = (
            f"You are {user_name}, speaking to your past self from 5 years in the future. "
            "Warm, concise, supportive. Ask one gentle follow-up question.\n\n"
            f"User: {user_message}"
        )

        if not self.enabled or not self.model:
            return f"(stub) Future {user_name}: '{user_message}' — tell me more."

        try:
            # simple single-string call to avoid SDK role/version mismatch headaches
            resp = self.model.generate_content(prompt)
            text = getattr(resp, "text", None)
            return (text or "(no response)").strip()
        except Exception as e:
            print("⚠️ Gemini call failed:", e)
            return "I’m here. What part worries you most?"

gemini_service = GeminiService()
