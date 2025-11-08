# app/services/mongodb_service.py

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from datetime import datetime, timezone  # <-- Import timezone
import logging

logger = logging.getLogger(__name__)

class MongoDBService:
    def __init__(self):
        """
        Initialize the MongoDB connection using Motor.
        """
        settings = get_settings()
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client.ekho  # 'ekho' is the database name
        
        # Schemas are defined in the project doc [cite: 458-480]
        self.users_collection = self.db.users
        self.conversations_collection = self.db.conversations
        
        logger.info("MongoDB connection initialized.")

    async def save_conversation(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        emotional_tag: str,
        mode: str
    ):
        """
        Save conversation to database, based on schema [cite: 470-480]
        """
        try:
            await self.conversations_collection.insert_one({
                "user_id": user_id,
                "user_message": user_message,
                "ai_response": ai_response,
                "emotional_tag": emotional_tag,
                "mode": mode,
                "timestamp": datetime.now(timezone.utc)  # <-- Modern datetime
            })
            logger.info(f"Saved conversation for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")

    async def get_conversation_history(
        self,
        user_id: str,
        limit: int = 50
    ):
        """
        Retrieve recent conversations for a user [cite: 446-453]
        """
        try:
            cursor = self.conversations_collection.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit)
            
            # Motor returns a cursor, we must convert it to a list
            history = await cursor.to_list(length=limit)
            # Reverse the list so it's in chronological order
            return list(reversed(history))
        except Exception as e:
            logger.error(f"Failed to retrieve conversation history: {e}")
            return []

    async def get_user_profile(self, user_id: str):
        """
        Get user profile with metadata [cite: 454-455]
        """
        try:
            return await self.users_collection.find_one({"user_id": user_id})
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None

    # You would add other functions here like:
    # async def create_user_profile(...)
    # async def get_user_goals(...)