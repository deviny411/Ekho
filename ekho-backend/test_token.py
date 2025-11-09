import google.auth
from google.auth.transport.requests import Request

def main():
    creds, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    print("Project from ADC:", project)
    print("Got access token (first 40 chars):", creds.token[:40])

if __name__ == "__main__":
    main()
