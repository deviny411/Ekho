import os
import base64
import logging
from typing import List
from datetime import timedelta
import asyncio

from google.cloud import storage
from google.oauth2 import service_account

# Use print instead of logger to match your other files
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling Google Cloud Storage operations."""

    def __init__(self):
        bucket_name = os.getenv("STORAGE_BUCKET")
        if not bucket_name:
            raise ValueError("STORAGE_BUCKET not set in environment")

        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path and os.path.exists(creds_path):
            credentials = service_account.Credentials.from_service_account_file(
                creds_path
            )
            self.client = storage.Client(credentials=credentials)
            print(
                f"✅ StorageService: using explicit service account at {creds_path}"
            )
        else:
            self.client = storage.Client()
            print("✅ StorageService: using default application credentials")

        self.bucket_name = bucket_name
        self.bucket = self.client.bucket(bucket_name)
        print(f"✅ StorageService: initialized for bucket {bucket_name}")

    def _check_connection_sync(self) -> bool:
        """Blocking helper for check_connection."""
        try:
            self.client.get_bucket(self.bucket_name)
            return True
        except Exception as e:
            print(f"❌ StorageService connection check failed: {e}")
            return False

    async def check_connection(self) -> bool:
        """Check if storage bucket is accessible."""
        return await asyncio.to_thread(self._check_connection_sync)

    def _upload_blob_sync(self, image_data: bytes, object_name: str, content_type: str) -> str:
        """Blocking helper for uploading."""
        blob = self.bucket.blob(object_name)
        blob.upload_from_string(image_data, content_type=content_type)
        gcs_uri = f"gs://{self.bucket_name}/{object_name}"
        print(f"Uploaded to {gcs_uri}")
        return gcs_uri

    async def upload_reference_images(
        self,
        user_id: str,
        face_captures: List[str],
        job_id: str,
    ) -> List[str]:
        """
        Accepts base64 data URLs, uploads to GCS, returns gs:// URIs.
        Now fully non-blocking.
        """
        uris: List[str] = []
        upload_tasks = []

        for idx, image_b64 in enumerate(face_captures):
            if not image_b64:
                continue

            # ... (same base64 decoding logic as your file) ...
            if image_b64.startswith("data:image"):
                header, b64data = image_b64.split(",", 1)
                content_type = "image/png" if "png" in header else "image/jpeg"
                ext = "png" if "png" in header else "jpg"
            else:
                b64data = image_b64
                content_type = "image/jpeg"
                ext = "jpg"

            try:
                image_data = base64.b64decode(b64data)
            except Exception as e:
                print(f"❌ Error decoding base64 for image {idx}: {e}")
                continue

            object_name = f"reference/{user_id}/{job_id}/face_{idx}.{ext}"
            
            # Add the async task to a list to run in parallel
            upload_tasks.append(
                asyncio.to_thread(
                    self._upload_blob_sync,
                    image_data,
                    object_name,
                    content_type
                )
            )

        # Run all uploads concurrently
        try:
            uris = await asyncio.gather(*upload_tasks)
        except Exception as e:
            print(f"❌ Error uploading images to GCS: {e}")

        return uris

    async def upload_file_bytes(self, file_bytes: bytes, gcs_path: str, content_type: str):
        """Helper to upload raw bytes (like audio)"""
        try:
            await asyncio.to_thread(
                self._upload_blob_sync,
                file_bytes,
                gcs_path,
                content_type
            )
        except Exception as e:
            print(f"❌ Error uploading file bytes to {gcs_path}: {e}")
            raise
    
    def _get_signed_url_sync(self, gcs_uri: str, expires_seconds: int) -> str:
        """Blocking helper for get_signed_url."""
        if not gcs_uri.startswith("gs://"):
            return gcs_uri

        without = gcs_uri[len("gs://"):]
        parts = without.split("/", 1)
        if len(parts) != 2:
            return gcs_uri

        bucket_name, blob_name = parts
        blob = self.client.bucket(bucket_name).blob(blob_name)

        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_seconds),
            method="GET",
        )

    async def get_signed_url(self, gcs_uri: str, expires_seconds: int = 3600) -> str:
        """
        Turn gs://bucket/path.mp4 into a time-limited HTTPS URL.
        Now fully non-blocking.
        """
        return await asyncio.to_thread(
            self._get_signed_url_sync,
            gcs_uri,
            expires_seconds
        )
