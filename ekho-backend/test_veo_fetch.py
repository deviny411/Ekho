import os
import time
import json
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or r"C:\Users\Vexo4\Documents\ekho-app\ekho-backend\service-account.json"
PROJECT_ID = "ekho-477607"
LOCATION = "us-central1"
MODEL_ID = "veo-3.1-generate-preview"

# paste your operation name here to test
OPERATION_NAME = "projects/ekho-477607/locations/us-central1/publishers/google/models/veo-3.1-generate-preview/operations/4358c99c-eecf-49c5-9b08-77e021f0bed3"


def get_token():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account file not found at: {SERVICE_ACCOUNT_FILE}")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    return creds.token


def fetch_operation():
    token = get_token()
    url = (
        f"https://{LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}"
        f"/publishers/google/models/{MODEL_ID}:fetchPredictOperation"
    )
    body = { "operationName": OPERATION_NAME }

    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=body,
    )
    print("Status:", r.status_code)
    print("Body:", r.text[:4000])
    if not r.ok:
        return None
    return r.json()


def main():
    while True:
        data = fetch_operation()
        if not data:
            break

        if data.get("done"):
            print("\nDONE = true")
            print(json.dumps(data, indent=2)[:6000])
            break

        print("Not done yet, waiting 10s...")
        time.sleep(10)


if __name__ == "__main__":
    main()
