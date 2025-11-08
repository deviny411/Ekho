import base64
import os
from typing import List, Optional
from google.cloud import storage
from google.oauth2 import service_account

class StorageService:
    """Service for handling Google Cloud Storage operations."""
    
    def __init__(self):
        # Load credentials from environment variable path
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', './service-account.json')
        
        if not os.path.exists(creds_path):
            raise FileNotFoundError(
                f"Service account JSON not found at: {creds_path}\n"
                "Please ensure service-account.json is in the ekho-backend folder."
            )
        
        # Create credentials object
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        
        # Initialize client with explicit credentials
        self.client = storage.Client(credentials=credentials)
        
        # Get bucket name from environment
        bucket_name = os.getenv('STORAGE_BUCKET')
        if not bucket_name:
            raise ValueError("STORAGE_BUCKET not set in .env file")
        
        self.bucket = self.client.bucket(bucket_name)
    
    async def upload_reference_images(
        self,
        user_id: str,
        images: List[str],
        job_id: str
    ) -> List[str]:
        """
        Upload reference images to Cloud Storage.
        
        Args:
            user_id: User identifier
            images: List of base64 encoded images
            job_id: Job identifier for organization
            
        Returns:
            List of public URLs
        """
        urls = []
        
        for idx, image_b64 in enumerate(images):
            try:
                # Decode base64
                # Remove data URL prefix if present (data:image/jpeg;base64,...)
                if ',' in image_b64:
                    image_b64 = image_b64.split(',')[1]
                
                image_data = base64.b64decode(image_b64)
                
                # Create unique blob name
                blob_name = f"users/{user_id}/references/{job_id}_{idx}.jpg"
                blob = self.bucket.blob(blob_name)
                
                # Upload
                blob.upload_from_string(
                    image_data,
                    content_type='image/jpeg'
                )
                
                # Make public (for demo - in production use signed URLs)
                blob.make_public()
                urls.append(blob.public_url)
                
            except Exception as e:
                print(f"Error uploading image {idx}: {str(e)}")
                raise
        
        return urls
    
    async def upload_video(
        self,
        user_id: str,
        video_data: bytes,
        job_id: str
    ) -> str:
        """
        Upload generated video to storage.
        
        Args:
            user_id: User identifier
            video_data: Video bytes
            job_id: Job identifier
            
        Returns:
            Public URL of uploaded video
        """
        blob_name = f"users/{user_id}/videos/{job_id}.mp4"
        blob = self.bucket.blob(blob_name)
        
        blob.upload_from_string(
            video_data,
            content_type='video/mp4'
        )
        
        blob.make_public()
        return blob.public_url
    
    async def cleanup_temp_files(self, user_id: str, job_id: str):
        """Delete temporary reference images."""
        prefix = f"users/{user_id}/references/{job_id}"
        blobs = self.bucket.list_blobs(prefix=prefix)
        
        for blob in blobs:
            blob.delete()
    
    def check_connection(self) -> bool:
        """Check if storage bucket is accessible."""
        try:
            self.bucket.exists()
            return True
        except Exception:
            return False

# Singleton instance - will be created when first imported
storage_service = StorageService()
