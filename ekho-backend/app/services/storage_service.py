import os
import base64
import logging
from typing import List
from datetime import timedelta

from google.cloud import storage
from google.oauth2 import service_account

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class StorageService:
    """Service for handling Google Cloud Storage operations."""

    def __init__(self):
        # Bucket (required)
        bucket_name = os.getenv("STORAGE_BUCKET")
        if not bucket_name:
            raise ValueError("STORAGE_BUCKET not set in environment")

        # Credentials: use explicit service account if provided, else ADC
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path and os.path.exists(creds_path):
            credentials = service_account.Credentials.from_service_account_file(
                creds_path
            )
            self.client = storage.Client(credentials=credentials)
            logger.info(
                "StorageService: using explicit service account at %s", creds_path
            )
        else:
            self.client = storage.Client()
            logger.info("StorageService: using default application credentials")

        self.bucket_name = bucket_name
        self.bucket = self.client.bucket(bucket_name)
        logger.info("StorageService: initialized for bucket %s", bucket_name)

    def check_connection(self) -> bool:
        """Check if storage bucket is accessible."""
        try:
            self.client.get_bucket(self.bucket_name)
            return True
        except Exception as e:
            logger.error("StorageService connection check failed: %s", e)
            return False

    async def upload_reference_images(
        self,
        user_id: str,
        face_captures: List[str],
        job_id: str,
    ) -> List[str]:
        """
        Accepts base64 data URLs from frontend,
        uploads to GCS, returns gs:// URIs for Veo.
        """
        uris: List[str] = []

        for idx, image_b64 in enumerate(face_captures):
            if not image_b64:
                continue

            # Handle data URLs: data:image/png;base64,xxxx
            if image_b64.startswith("data:image"):
                header, b64data = image_b64.split(",", 1)
                if "png" in header:
                    ext = "png"
                    content_type = "image/png"
                else:
                    ext = "jpg"
                    content_type = "image/jpeg"
            else:
                b64data = image_b64
                ext = "jpg"
                content_type = "image/jpeg"

            try:
                image_data = base64.b64decode(b64data)
            except Exception as e:
                logger.error("Error decoding base64 for image %d: %s", idx, e)
                continue

            object_name = f"reference/{user_id}/{job_id}/face_{idx}.{ext}"
            blob = self.bucket.blob(object_name)

            try:
                blob.upload_from_string(image_data, content_type=content_type)
                gcs_uri = f"gs://{self.bucket_name}/{object_name}"
                uris.append(gcs_uri)
                logger.info("Uploaded reference image %d to %s", idx, gcs_uri)
            except Exception as e:
                logger.error("Error uploading image %d to GCS: %s", idx, e)

        return uris

    async def upload_video(
        self,
        user_id: str,
        video_data: bytes,
        job_id: str,
    ) -> str:
        """
        Optional: upload generated video bytes manually.
        Veo normally writes directly to GCS via storageUri.
        """
        blob_name = f"users/{user_id}/videos/{job_id}.mp4"
        blob = self.bucket.blob(blob_name)
        blob.upload_from_string(video_data, content_type="video/mp4")
        url = self.get_signed_url(f"gs://{self.bucket_name}/{blob_name}")
        logger.info("Uploaded video to %s", url)
        return url

    async def cleanup_temp_files(self, user_id: str, job_id: str):
        """Delete temporary reference images for a job."""
        prefix = f"reference/{user_id}/{job_id}/"
        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
        for blob in blobs:
            logger.info("Deleting temp blob %s", blob.name)
            blob.delete()

    def get_signed_url(self, gcs_uri: str, expires_seconds: int = 3600) -> str:
        """
        Turn gs://bucket/path.mp4 into a time-limited HTTPS URL the browser can play.
        """
        if not gcs_uri.startswith("gs://"):
            return gcs_uri

        without = gcs_uri[len("gs://"):]
        parts = without.split("/", 1)
        if len(parts) != 2:
            return gcs_uri

        bucket_name, blob_name = parts
        blob = self.client.bucket(bucket_name).blob(blob_name)

        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_seconds),
            method="GET",
        )
        return url


storage_service = StorageService()
