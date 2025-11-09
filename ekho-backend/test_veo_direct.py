import os
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

PROJECT_ID = "ekho-477607"
LOCATION = "us-central1"
MODEL_ID = "veo-3.1-generate-preview"

# Make sure this exists and is an actual JPEG/PNG in your bucket
TEST_REF = "gs://ekho-avatars-ekho-477607/test/test.jpg"
OUT_URI = "gs://ekho-avatars-ekho-477607/output/test-direct/"

SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or r"C:\Users\Vexo4\Documents\ekho-app\ekho-backend\service-account.json"


def get_token():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account file not found at: {SERVICE_ACCOUNT_FILE}")

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    return creds.token


def main():
    print(f"Using service account file: {SERVICE_ACCOUNT_FILE}")
    token = get_token()
    print("Got access token (first 40 chars):", token[:40])

    url = (
        f"https://{LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}"
        f"/publishers/google/models/{MODEL_ID}:predictLongRunning"
    )

    body = {
        "instances": [
            {
                "prompt": "4-second simple cinematic portrait shot.",
                "referenceImages": [
                    {
                        "image": {
                            "gcsUri": TEST_REF,
                            "mimeType": "image/jpeg"  # 👈 IMPORTANT
                        },
                        "referenceType": "asset"
                    }
                ]
            }
        ],
        "parameters": {
            "storageUri": OUT_URI,
            "durationSeconds": 4,
            "aspectRatio": "16:9",
            "personGeneration": "allow_adult",
            "sampleCount": 1
        }
    }

    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=body,
    )

    print("Status:", resp.status_code)
    print("Body (truncated):", resp.text[:2000])

    if resp.ok:
        data = resp.json()
        print("Operation name:", data.get("name"))


if __name__ == "__main__":
    main()
