from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.config import get_settings
import os

settings = get_settings()

app = FastAPI(
    title="Ekho - Your Future Self",
    description="Talk to tomorrow's you, today. Veo 3.1 video avatar generation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware - allows frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("=" * 60)
    print("🚀 Ekho Backend Starting...")
    print("=" * 60)
    print(f"📍 Google Cloud Project: {settings.google_cloud_project}")
    print(f"📍 Location: {settings.google_cloud_location}")
    print(f"📍 Storage Bucket: {settings.storage_bucket}")
    print(f"📍 Environment: {settings.environment}")
    print("=" * 60)
    print("✅ Server ready! Visit http://localhost:8000/docs")
    print("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("\n👋 Ekho Backend Shutting Down...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-reload on code changes
    )
