import snowflake.connector
from app.config import get_settings
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SnowflakeService:
    def __init__(self):
        """
        Initialize the Snowflake connection.
        """
        settings = get_settings()
        try:
            self.conn = snowflake.connector.connect(
                user=settings.snowflake_user,
                password=settings.snowflake_password,
                account=settings.snowflake_account,
                warehouse='EKHO_WH',
                database='EKHO_DB',
                schema='ANALYTICS',
                autocommit=True
            )
            self.conn.cursor().execute("USE WAREHOUSE EKHO_WH")
            logger.info("Snowflake connection successful.")
        except Exception as e:
            logger.error(f"Failed to connect to Snowflake: {e}")
            self.conn = None

    def _get_cursor(self):
        if not self.conn:
            logger.error("No Snowflake connection available.")
            return None
        return self.conn.cursor()

    async def log_conversation_analytic(
        self, 
        user_id: str, 
        emotional_tag: str,
        conversation_mode: str,
        sentiment_score: float # You'll need to generate this, e.g., from Gemini
    ):
        """
        Insert aggregated conversation data into Snowflake for analytics.
        This is part of your ETL process.
        """
        cursor = self._get_cursor()
        if not cursor:
            return

        query = """
        INSERT INTO conversations 
        (user_id, emotional_tag, conversation_mode, sentiment_score, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        """
        try:
            cursor.execute(query, (
                user_id,
                emotional_tag,
                conversation_mode,
                sentiment_score,
                datetime.now(timezone.utc)
            ))
            logger.info(f"Logged analytic for user {user_id} to Snowflake.")
        except Exception as e:
            logger.error(f"Failed to insert analytic into Snowflake: {e}")
        finally:
            cursor.close()

    async def analyze_emotional_trends(self, user_id: str):
        """
        Get 30-day emotional trend for a user.
        This will be used by the Pattern Agent.
        """
        cursor = self._get_cursor()
        if not cursor:
            return []

        # This query is from the project documentation
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
            cursor.execute(query, (user_id,))
            return cursor.fetchall() #
        except Exception as e:
            logger.error(f"Failed to analyze emotional trends: {e}")
            return []
        finally:
            cursor.close()

    async def predict_emotional_state(self, user_id: str):
        """
        ML model prediction of next emotional state.
        This is a Phase 3 (Polish) feature.
        """
        pass #

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Snowflake connection closed.")