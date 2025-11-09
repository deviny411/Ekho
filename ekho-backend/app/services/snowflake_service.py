import snowflake.connector
from app.config import get_settings
from datetime import datetime, timezone
import asyncio
from typing import Dict, Any

class SnowflakeService:
    def __init__(self):
        """
        Initialize the Snowflake connection.
        """
        self.settings = get_settings()
        self.conn = None
        print("Snowflake Service initialized (but not connected).")
        # Run setup in a non-blocking way
        asyncio.create_task(self._setup_tables())


    async def _setup_tables(self):
        """
        Ensures all required tables exist on startup.
        """
        print("Checking Snowflake table schemas...")
        await self._ensure_connected()
        try:
            # --- 1. CONVERSATIONS TABLE ---
            await asyncio.to_thread(
                self.conn.cursor().execute,
                """
                CREATE TABLE IF NOT EXISTS EKHO_DB.ANALYTICS.conversations (
                    user_id STRING,
                    emotional_tag STRING,
                    conversation_mode STRING,
                    sentiment_score FLOAT,
                    timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
                );
                """
            )
            
            # --- 2. NEW VOICE ANALYTICS TABLE ---
            await asyncio.to_thread(
                self.conn.cursor().execute,
                """
                CREATE TABLE IF NOT EXISTS EKHO_DB.ANALYTICS.voice_analytics (
                    user_id STRING,
                    pitch_mean_hz FLOAT,
                    speech_rate_bpm FLOAT,
                    pause_frequency_hz FLOAT,
                    volume_variance FLOAT,
                    duration_sec FLOAT,
                    tag STRING,
                    timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
                );
                """
            )
            print("✅ Snowflake tables verified.")
        except Exception as e:
            print(f"❌ Failed to create/verify Snowflake tables: {e}")
            self.conn = None # Force reconnect

    async def _connect(self):
        """
        Asynchronous helper to create the blocking connection in a thread.
        """
        if self.conn:
            return  # Already connected

        try:
            self.conn = await asyncio.to_thread(
                snowflake.connector.connect,
                user=self.settings.snowflake_user,
                password=self.settings.snowflake_password,
                account=self.settings.snowflake_account,
                database='EKHO_DB',
                schema='ANALYTICS',
                autocommit=True
            )
            await asyncio.to_thread(self.conn.cursor().execute, "USE WAREHOUSE EKHO_WH")
            print("✅ Snowflake connection successful and warehouse set.")
        except Exception as e:
            print(f"❌ Failed to connect to Snowflake: {e}")
            self.conn = None

    async def _ensure_connected(self):
        """Ensures a valid connection exists before running a query."""
        if not self.conn:
            await self._connect()
        if not self.conn:
            raise Exception("Snowflake connection is not established.")

    async def log_conversation_analytic(
        self, 
        user_id: str, 
        emotional_tag: str,
        conversation_mode: str,
        sentiment_score: float
    ):
        """
        Insert aggregated conversation data into Snowflake (non-blocking).
        """
        await self._ensure_connected() # Ensure connection is active
        
        query = """
        INSERT INTO conversations 
        (user_id, emotional_tag, conversation_mode, sentiment_score, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        """
        try:
            # Run the blocking DB call in a thread
            await asyncio.to_thread(
                self.conn.cursor().execute,
                query,
                (
                    user_id,
                    emotional_tag,
                    conversation_mode,
                    sentiment_score,
                    datetime.now(timezone.utc)
                )
            )
            print(f"Logged analytic for user {user_id} to Snowflake.")
        except Exception as e:
            print(f"❌ Failed to insert analytic into Snowflake: {e}")
            self.conn = None # Force reconnect on next call
    
    # --- NEW FUNCTION FOR VOICE ANALYSIS ---
    async def log_voice_analytic(
        self, 
        user_id: str, 
        features: Dict[str, Any],
        tag: str = "baseline"
    ):
        """
        Insert voice analysis features into Snowflake (non-blocking).
        """
        await self._ensure_connected()
        
        query = """
        INSERT INTO voice_analytics
        (user_id, pitch_mean_hz, speech_rate_bpm, pause_frequency_hz, 
         volume_variance, duration_sec, tag, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            await asyncio.to_thread(
                self.conn.cursor().execute,
                query,
                (
                    user_id,
                    features.get("pitch_mean_hz", 0.0),
                    features.get("speech_rate_bpm", 0.0),
                    features.get("pause_frequency_hz", 0.0),
                    features.get("volume_variance", 0.0),
                    features.get("duration_sec", 0.0),
                    tag,
                    datetime.now(timezone.utc)
                )
            )
            print(f"Logged voice analytic for user {user_id} to Snowflake.")
        except Exception as e:
            print(f"❌ Failed to insert voice analytic into Snowflake: {e}")
            self.conn = None # Force reconnect on next call

    async def analyze_emotional_trends(self, user_id: str):
        """
        Get 30-day emotional trend for a user (non-blocking).
        """
        await self._ensure_connected()

        query = """
        SELECT
            DATE(timestamp) as date,
            AVG(sentiment_score) as avg_emotion,
            COUNT(*) as conversation_count
        FROM conversations
        WHERE user_id = %s
        AND timestamp >= DATEADD(day, -30, CURRENT_DATE())
        GROUP BY DATE(timestamp)
        ORDER BY date
        """
        
        try:
            # Run blocking cursor and fetchall in a thread
            def _run_query():
                cursor = self.conn.cursor()
                cursor.execute(query, (user_id,))
                return cursor.fetchall()

            return await asyncio.to_thread(_run_query)
        
        except Exception as e:
            print(f"❌ Failed to analyze emotional trends: {e}")
            self.conn = None
            return []

    async def close(self):
        if self.conn:
            await asyncio.to_thread(self.conn.close)
            print("Snowflake connection closed.")