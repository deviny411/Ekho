from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from datetime import datetime, timezone

class MongoDBService:
    def __init__(self):
        """
        Initialize the MongoDB connection using Motor.
        """
        settings = get_settings()
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client.ekho  # 'ekho' is the database name
        
        self.users_collection = self.db.users
        self.conversations_collection = self.db.conversations
        
        print("✅ MongoDB connection initialized.")

    async def save_conversation(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        emotional_tag: str,
        mode: str
    ):
        """
        Save conversation to database.
        """
        try:
            await self.conversations_collection.insert_one({
                "user_id": user_id,
                "user_message": user_message,
                "ai_response": ai_response,
                "emotional_tag": emotional_tag,
                "mode": mode,
                "timestamp": datetime.now(timezone.utc)
            })
            print(f"Saved conversation for user {user_id}")
        except Exception as e:
            print(f"❌ Failed to save conversation: {e}")

    async def get_conversation_history(
        self,
        user_id: str,
        limit: int = 50
    ):
        """
        Retrieve recent conversations for a user.
        """
        try:
            cursor = self.conversations_collection.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit)
            
            history = await cursor.to_list(length=limit)
            return list(reversed(history))
        except Exception as e:
            print(f"❌ Failed to retrieve conversation history: {e}")
            return []

    async def get_user_profile(self, user_id: str):
        """
        Get user profile with metadata.
        """
        try:
            return await self.users_collection.find_one({"user_id": user_id})
        except Exception as e:
            print(f"❌ Failed to get user profile: {e}")
            return None

    # --- NEW FUNCTION ---
    async def update_user_profile(self, user_id: str, updates: dict):
        """
        Updates a user's profile, or creates one if it doesn't exist.
        """
        try:
            # $set updates fields, upsert=True creates the doc if it doesn't exist
            await self.users_collection.update_one(
                {"user_id": user_id},
                {"$set": updates},
                upsert=True  
            )
            print(f"Updated profile for user {user_id} with: {list(updates.keys())}")
        except Exception as e:
            print(f"❌ Failed to update user profile {user_id}: {e}")