# app/config.py
from dotenv import load_dotenv
load_dotenv()

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # read from .env and environment (case-insensitive)
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Google Cloud
    google_cloud_project: str = Field(..., alias="GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = Field("us-central1", alias="GOOGLE_CLOUD_LOCATION")
    google_application_credentials: str = Field(..., alias="GOOGLE_APPLICATION_CREDENTIALS")

    # Storage
    storage_bucket: str = Field(..., alias="STORAGE_BUCKET")

    # API Configuration
    max_video_duration: int = Field(30, alias="MAX_VIDEO_DURATION")
    max_reference_images: int = Field(5, alias="MAX_REFERENCE_IMAGES")
    rate_limit_per_minute: int = Field(10, alias="RATE_LIMIT_PER_MINUTE")

    # Gemini (required)
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")

    # Environment
    environment: str = Field("development", alias="ENVIRONMENT")

    # MongoDB (required)
    mongodb_uri: str = Field(..., alias="MONGODB_URI")

    # Snowflake (required)
    snowflake_user: str = Field(..., alias="SNOWFLAKE_USER")
    snowflake_password: str = Field(..., alias="SNOWFLAKE_PASSWORD")
    snowflake_account: str = Field(..., alias="SNOWFLAKE_ACCOUNT")

@lru_cache()
def get_settings() -> Settings:
    return Settings()
