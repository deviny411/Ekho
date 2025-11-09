# app/services/adk_service.py
import asyncio
import re
from typing import Any, Dict, List, Optional

from app.services.mongodb_service import MongoDBService
from app.services.snowflake_service import SnowflakeService

# Very simple keyword screen; improve later if time permits.
CRISIS_KEYWORDS = {
    "suicide", "kill myself", "self-harm", "hurt myself",
    "end it all", "can't go on", "want to die"
}

# Light heuristics for mode & emotion
_MODE_RULES = {
    "therapist": [
        r"\b(anxious|anxiety|panic|overwhelmed|depressed|lonely|burn(?:out|ed)?)\b",
        r"\b(feel|feeling|emotion|cope|struggle|help me|talk)\b",
    ],
    "decision": [
        r"\b(decide|decision|choose|option|pros?/?cons?|trade[- ]?off|should I)\b",
    ],
    "brainstorm": [
        r"\b(idea|ideas|brainstorm|creativ|how might we|what if)\b",
    ],
}

_POSITIVE = re.compile(r"\b(happy|relieved|proud|excited|optimistic|grateful)\b", re.I)
_NEGATIVE = re.compile(r"\b(sad|anxious|stressed|worried|angry|upset|tired|burn(?:ed|out))\b", re.I)


class ADKAgentService:
    """
    Minimal agent orchestrator for MVP:
      - memory_agent: fetches recent chats (Mongo)
      - pattern_agent: 30-day aggregates (Snowflake) if available
      - safety_agent: simple crisis keyword scan
      - detect_mode / tag_emotion / quick_sentiment_score: tiny heuristics
      - orchestrate: run agents in parallel and merge
      - log_after_chat: persist to Mongo + Snowflake (best-effort)
    """

    def __init__(self):
        self.mongo = MongoDBService()
        self.snow = SnowflakeService()

    # -------------------------
    # Agents
    # -------------------------
    async def memory_agent(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        try:
            history = await self.mongo.get_conversation_history(user_id, limit=10)
            return history or []
        except Exception:
            return []

    async def pattern_agent(self, user_id: str):
        try:
            if not getattr(self.snow, "conn", None):
                return []
            return await self.snow.analyze_emotional_trends(user_id) or []
        except Exception:
            return []

    async def safety_agent(self, message: str) -> Dict[str, Any]:
        msg = (message or "").lower()
        crisis = any(k in msg for k in CRISIS_KEYWORDS)
        return {"crisis": crisis, "note": "Crisis language detected." if crisis else "clear"}

    # -------------------------
    # Heuristics
    # -------------------------
    def detect_mode(self, message: str) -> str:
        text = (message or "")
        for mode, patterns in _MODE_RULES.items():
            for pat in patterns:
                if re.search(pat, text, flags=re.I):
                    return mode
        return "casual"

    def tag_emotion(self, text: str) -> str:
        if not text:
            return "neutral"
        if _NEGATIVE.search(text):
            return "anxious"
        if _POSITIVE.search(text):
            return "positive"
        return "neutral"

    def quick_sentiment_score(self, text: str) -> float:
        if not text:
            return 0.0
        pos = len(_POSITIVE.findall(text))
        neg = len(_NEGATIVE.findall(text))
        if pos == neg == 0:
            return 0.0
        return (pos - neg) / max(1, (pos + neg))

    # -------------------------
    # Orchestration
    # -------------------------
    async def orchestrate(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """
        Runs all agents AND fetches user profile data in parallel for context.
        """
        # 1. Gather all tasks concurrently: agents + profile data
        mem, trends, safety, profile = await asyncio.gather(
            self.memory_agent(user_id, user_message),
            self.pattern_agent(user_id),
            self.safety_agent(user_message),
            self.mongo.get_user_profile(user_id), # <-- NEW: Fetch user profile
        )
        
        # 2. Extract essential fields needed by routes.py
        voice_id = profile.get("voice_id") if profile else None
        avatar_refs = profile.get("avatar_reference_urls", []) if profile else []

        # 3. Compile final context dictionary
        return {
            "memories": mem or [],
            "trends": trends or [],
            "safety": safety,
            "suggested_mode": self.detect_mode(user_message),
            "voice_id": voice_id,                   # <-- NOW AVAILABLE to routes.py
            "avatar_reference_urls": avatar_refs,   # <-- NOW AVAILABLE to routes.py
        }

    # -------------------------
    # Persistence hook (call from route AFTER LLM reply)
    # -------------------------
    async def log_after_chat(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        mode_final = mode or self.detect_mode(user_message)
        emotion = self.tag_emotion(f"{user_message} {ai_response}")
        sentiment = self.quick_sentiment_score(ai_response)

        # Mongo (conversation log)
        try:
            await self.mongo.save_conversation(
                user_id=user_id,
                user_message=user_message,
                ai_response=ai_response,
                emotional_tag=emotion,
                mode=mode_final,
            )
        except Exception:
            pass

        # Snowflake (analytics row)
        try:
            if getattr(self.snow, "conn", None):
                await self.snow.log_conversation_analytic(
                    user_id=user_id,
                    emotional_tag=emotion,
                    conversation_mode=mode_final,
                    sentiment_score=sentiment,
                )
        except Exception:
            pass

        return {"emotional_tag": emotion, "sentiment_score": sentiment, "mode": mode_final}


