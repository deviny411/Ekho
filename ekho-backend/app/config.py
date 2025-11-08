import os
from dotenv import load_dotenv

# Load .env file before anything else
load_dotenv()

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """Application settings and configuration."""
    
    # Google Cloud
    google_cloud_project: str
    google_cloud_location: str = "us-central1"
    google_application_credentials: str
    
    # Storage
    storage_bucket: str
    
    # API Configuration
    max_video_duration: int = 30
    max_reference_images: int = 5
    rate_limit_per_minute: int = 10
    
    # Environment
    environment: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
