import uuid
from typing import List, Dict
from datetime import datetime
import asyncio

from app.config import get_settings
from app.models.schemas import VideoStyle
from app.services.storage_service import storage_service

settings = get_settings()

class VeoService:
    """
    Service for Veo 3.1 video generation.
    Handles avatar creation and custom video generation.
    """
    
    def __init__(self):
        # In-memory job storage (replace with Redis/database in production)
        self.jobs: Dict[str, Dict] = {}
    
    async def generate_avatar_video(
        self,
        user_id: str,
        prompt: str,
        reference_images: List[str],
        duration: int = 10,
        style: VideoStyle = VideoStyle.CONVERSATIONAL
    ) -> Dict:
        """
        Generate video with Veo 3.1 using reference images.
        
        Args:
            user_id: User identifier
            prompt: Video generation prompt
            reference_images: Base64 encoded reference images
            duration: Video duration in seconds
            style: Video style preset
            
        Returns:
            Job metadata dict
        """
        job_id = f"veo_{user_id}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Step 1: Upload reference images to Cloud Storage
            print(f"[{job_id}] Uploading {len(reference_images)} reference images...")
            reference_urls = await storage_service.upload_reference_images(
                user_id=user_id,
                images=reference_images,
                job_id=job_id
            )
            print(f"[{job_id}] Reference images uploaded: {len(reference_urls)} URLs")
            
            # Step 2: Enhance prompt based on style
            enhanced_prompt = self._enhance_prompt(prompt, style)
            print(f"[{job_id}] Enhanced prompt: {enhanced_prompt[:100]}...")
            
            # Step 3: Create job metadata
            job_metadata = {
                "job_id": job_id,
                "user_id": user_id,
                "status": "processing",
                "progress": 10,
                "prompt": prompt,
                "enhanced_prompt": enhanced_prompt,
                "duration": duration,
                "style": style.value,
                "reference_urls": reference_urls,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "video_url": None,
                "error": None
            }
            
            # Store job
            self.jobs[job_id] = job_metadata
            
            # Step 4: Start async video generation
            asyncio.create_task(self._process_video_generation(job_id))
            
            return job_metadata
            
        except Exception as e:
            error_job = {
                "job_id": job_id,
                "user_id": user_id,
                "status": "failed",
                "progress": 0,
                "error": str(e),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            self.jobs[job_id] = error_job
            return error_job
    
    async def _process_video_generation(self, job_id: str):
        """
        Background task to generate video.
        This simulates Veo API call - replace with actual API in production.
        """
        try:
            job = self.jobs[job_id]
            
            # Simulate processing stages
            stages = [
                (30, "Analyzing reference images..."),
                (50, "Generating video frames..."),
                (70, "Applying style and consistency..."),
                (90, "Rendering final video..."),
            ]
            
            for progress, message in stages:
                await asyncio.sleep(5)  # Simulate processing time
                job["progress"] = progress
                job["updated_at"] = datetime.utcnow().isoformat()
                print(f"[{job_id}] {message} ({progress}%)")
            
            # Simulate successful completion
            # In production: Call actual Veo API here
            video_url = f"https://storage.googleapis.com/{settings.storage_bucket}/users/{job['user_id']}/videos/{job_id}.mp4"
            
            job["status"] = "completed"
            job["progress"] = 100
            job["video_url"] = video_url
            job["updated_at"] = datetime.utcnow().isoformat()
            
            print(f"[{job_id}] ✅ Video generation completed!")
            
            # Cleanup reference images
            await storage_service.cleanup_temp_files(job["user_id"], job_id)
            
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
            job["updated_at"] = datetime.utcnow().isoformat()
            print(f"[{job_id}] ❌ Error: {str(e)}")
    
    def _enhance_prompt(self, prompt: str, style: VideoStyle) -> str:
        """Add style-specific enhancements to prompt."""
        
        style_templates = {
            VideoStyle.CINEMATIC: "Cinematic lighting, film grain, professional cinematography, 35mm lens. ",
            VideoStyle.DOCUMENTARY: "Natural lighting, authentic documentary style, handheld camera feel. ",
            VideoStyle.CONVERSATIONAL: "Warm lighting, friendly atmosphere, direct eye contact, natural expressions, slight smile. Indoor setting with soft natural light. ",
            VideoStyle.EMOTIONAL: "Dramatic lighting, expressive faces, emotionally resonant atmosphere. "
        }
        
        enhancement = style_templates.get(style, "")
        consistency = "CRITICAL: Character consistency throughout. Same person in all frames. "
        
        return f"{enhancement}{consistency}{prompt}"
    
    async def create_aged_avatar(
        self,
        user_id: str,
        face_captures: List[str],
        age_years: int = 5
    ) -> Dict:
        """
        Create aged avatar from face captures.
        
        Args:
            user_id: User identifier
            face_captures: Base64 encoded face images
            age_years: Years to age the avatar
            
        Returns:
            Job metadata dict
        """
        # Generate prompt for aged avatar
        prompt = f"""
        Portrait video of a person, aged {age_years} years older.
        Gentle, natural facial movements. Calm breathing.
        Slight smile, warm and approachable expression.
        Making comfortable eye contact with camera.
        Indoor setting with warm, soft lighting.
        Subject appears wise, confident, and at peace.
        30 seconds duration.
        """
        
        return await self.generate_avatar_video(
            user_id=user_id,
            prompt=prompt,
            reference_images=face_captures,
            duration=30,
            style=VideoStyle.CONVERSATIONAL
        )
    
    async def get_job_status(self, job_id: str) -> Dict:
        """Get status of video generation job."""
        
        job = self.jobs.get(job_id)
        
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        return job
    
    def list_user_jobs(self, user_id: str) -> List[Dict]:
        """Get all jobs for a user."""
        return [
            job for job in self.jobs.values()
            if job["user_id"] == user_id
        ]

# Singleton instance
veo_service = VeoService()
