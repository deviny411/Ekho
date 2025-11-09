import os
import uuid
import logging
from datetime import datetime, timezone # <-- IMPORT TIMEZONE
from typing import List, Dict

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from app.services.storage_service import StorageService

# Use print instead of logger
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

storage_service = StorageService()

def guess_mime(uri: str) -> str:
    u = uri.lower()
    if u.endswith(".png"):
        return "image/png"
    return "image/jpeg"


class VeoServiceREST:
    """
    Veo 3.1 integration using:
      - Service account credentials (GOOGLE_APPLICATION_CREDENTIALS)
      - Vertex AI publisher model endpoint
      - predictLongRunning + fetchPredictOperation
      - Reference images stored in GCS
    """

    def __init__(self, project_id: str, location: str,
                 model_id: str, output_storage_uri: str):
        self.project_id = project_id
        self.location = location
        self.model_id = model_id
        self.output_storage_uri = output_storage_uri.rstrip("/") + "/"
        self.jobs: Dict[str, Dict] = {}

        sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not sa_path or not os.path.exists(sa_path):
            raise RuntimeError(
                f"GOOGLE_APPLICATION_CREDENTIALS not set or file not found: {sa_path}"
            )

        self.credentials = service_account.Credentials.from_service_account_file(
            sa_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        print(f"✅ VeoServiceREST: using service account from {sa_path}")

    # ---------- Auth ----------

    def get_access_token(self) -> str:
        """Synchronous token fetch/refresh."""
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return self.credentials.token

    # ---------- Public APIs used by your routes ----------

    async def create_aged_avatar(
        self,
        user_id: str,
        face_captures: List[str],
        age_years: int = 10,
    ) -> Dict:
        """
        Called by /generate-avatar.
        Takes base64 face captures, generates an 8s aged avatar.
        """
        duration_seconds = 8  # Veo requires 8s for reference_to_video

        prompt = (
            f"Portrait video of this person, aged {age_years} years older. "
            f"Natural, calm expression, subtle smile, direct eye contact, "
            f"soft professional lighting, neutral background."
        )

        return await self._create_job(
            user_id=user_id,
            prompt=prompt,
            face_captures=face_captures,
            duration_seconds=duration_seconds,
        )

    async def generate_avatar_video(
        self,
        user_id: str,
        prompt: str,
        reference_images: List[str],
        duration: int,
        style=None,
    ) -> Dict:
        """
        Called by /generate-video.
        Uses provided prompt + reference_images.
        We clamp to 8s for reference image -> video.
        """
        duration_seconds = 8

        return await self._create_job(
            user_id=user_id,
            prompt=prompt,
            face_captures=reference_images, # Re-using face_captures logic
            duration_seconds=duration_seconds,
        )

    # ---------- Core job creation ----------

    async def _create_job(
        self,
        user_id: str,
        prompt: str,
        face_captures: List[str],
        duration_seconds: int,
    ) -> Dict:
        job_id = f"veo_{user_id}_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        # --- FIX START: Conditional Handling for GCS URIs vs Base64 ---
        gcs_uris: List[str] = []
        
        # Determine if the input list contains GCS URIs (from MongoDB) or Base64 (from frontend upload).
        is_gcs_uris = bool(face_captures) and face_captures[0].startswith("gs://")
        
        try:
            if not face_captures:
                # Fail if no images are provided
                raise RuntimeError("No avatar reference images found for video generation.")

            if is_gcs_uris:
                # Case 1: Input is GCS URIs (from ADK/MongoDB for /chat)
                gcs_uris = face_captures[:3]
                print(f"[{job_id}] Skipping upload. Using {len(gcs_uris)} existing GCS URIs from profile.")
            else:
                # Case 2: Input is Base64 (from /generate-avatar)
                print(
                    f"[{job_id}] Uploading {len(face_captures[:3])} reference images for {user_id}"
                )
                gcs_uris = await storage_service.upload_reference_images(
                    user_id=user_id,
                    face_captures=face_captures[:3],
                    job_id=job_id,
                )
            
            if not gcs_uris:
                raise RuntimeError("No valid reference images were found or uploaded.")
        # --- FIX END ---

            print(f"[{job_id}] GCS URIs: {gcs_uris}")

            output_prefix = f"{self.output_storage_uri}{job_id}/"

            body = {
                "instances": [
                    {
                        "prompt": prompt,
                        "referenceImages": [
                            {
                                "image": {
                                    "gcsUri": uri,
                                    "mimeType": guess_mime(uri),
                                },
                                "referenceType": "asset",
                            }
                            for uri in gcs_uris
                        ],
                    }
                ],
                "parameters": {
                    "storageUri": output_prefix,
                    "durationSeconds": duration_seconds,
                    "aspectRatio": "16:9",
                    "personGeneration": "allow_adult",
                    "sampleCount": 1,
                },
            }

            operation_name = await self._call_predict_long_running(body)

            job = {
                "job_id": job_id,
                "user_id": user_id,
                "status": "submitted",
                "operation": operation_name,
                "progress": 0,
                "video_url": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
            self.jobs[job_id] = job

            print(f"[{job_id}] Submitted Veo job: {operation_name}")
            return job

        except Exception as e:
            print(
                f"❌ [{job_id}] Job creation failed: {type(e).__name__}: {e}"
            )
            err = {
                "job_id": job_id,
                "user_id": user_id,
                "status": "failed",
                "operation": None,
                "progress": 0,
                "video_url": None,
                "error": str(e),
                "created_at": now,
                "updated_at": datetime.now(timezone.utc).isoformat(), # <-- USE TIMEZONE
            }
            self.jobs[job_id] = err
            return err

    # ---------- Status APIs ----------

    async def get_job_status(self, job_id: str) -> Dict:
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        op_name = job.get("operation")
        if not op_name:
            return job

        try:
            op = await self._fetch_predict_operation(op_name)
        except Exception as e:
            print(
                f"❌ [{job_id}] fetchPredictOperation failed: {type(e).__name__}: {e}"
            )
            job["status"] = "error"
            job["error"] = str(e)
            job["updated_at"] = datetime.now(timezone.utc).isoformat() # <-- USE TIMEZONE
            return job

        job["updated_at"] = datetime.now(timezone.utc).isoformat() # <-- USE TIMEZONE

        print(f"[{job_id}] fetchPredictOperation response: {op}")

        # Still running
        if not op.get("done"):
            job["status"] = "processing"
            job.setdefault("progress", 10)
            return job

        # Done with error
        if "error" in op and op["error"]:
            job["status"] = "failed"
            job["error"] = op["error"]
            job["progress"] = 0
            return job

        # Done successfully
        job["status"] = "completed"
        job["progress"] = 100

        resp = op.get("response") or {}

        # ... (same logic as your file to find video_uri) ...
        videos = (
            resp.get("videos")
            or resp.get("generatedVideos")
            or resp.get("generatedSamples", [])
        )
        video_uri = None
        if videos:
            v0 = videos[0]
            video_uri = (
                v0.get("gcsUri")
                or v0.get("uri")
                or v0.get("videoUri")
            )
        if not video_uri:
            video_uri = self._find_any_video_url(resp) or self._find_any_video_url(op)

        
        # --- CRITICAL FIX: Use 'await' for the async get_signed_url ---
        if video_uri and video_uri.startswith("gs://"):
            video_uri = await storage_service.get_signed_url(video_uri)
        # --- END FIX ---

        job["video_url"] = video_uri
        print(
            f"[{job_id}] Operation done. status={job['status']}, video_url={job.get('video_url')}"
        )

        job.setdefault("error", None)
        return job

    def list_user_jobs(self, user_id: str) -> List[Dict]:
        return [j for j in self.jobs.values() if j.get("user_id") == user_id]

    # ---------- Helpers ----------
    def _find_any_video_url(self, data) -> str | None:
        # ... (same recursive logic as your file) ...
        if isinstance(data, dict):
            for _, v in data.items():
                if isinstance(v, str):
                    if (v.startswith("gs://") or v.startswith("http")) and any(
                        ext in v for ext in (".mp4", ".mov", ".webm", ".mkv")
                    ):
                        return v
                found = self._find_any_video_url(v)
                if found:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = self._find_any_video_url(item)
                if found:
                    return found
        return None

    # ---------- Internal HTTP ----------
    # This section is already async using httpx, so it's good.

    async def _call_predict_long_running(self, json_body: Dict) -> str:
        token = self.get_access_token()
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}"
            f"/publishers/google/models/{self.model_id}:predictLongRunning"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=json_body)

        if resp.status_code != 200:
            print(
                f"❌ Veo predictLongRunning error {resp.status_code}: {resp.text}"
            )
            resp.raise_for_status()

        data = resp.json()
        op_name = data.get("name")
        if not op_name:
            raise RuntimeError(f"No operation name returned from Veo: {data}")
        return op_name

    async def _fetch_predict_operation(self, operation_name: str) -> Dict:
        token = self.get_access_token()
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}"
            f"/publishers/google/models/{self.model_id}:fetchPredictOperation"
        )
        body = {"operationName": operation_name}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=body)

        if resp.status_code != 200:
            print(
                f"❌ Veo fetchPredictOperation error {resp.status_code}: {resp.text}"
            )
            resp.raise_for_status()

        return resp.json()

