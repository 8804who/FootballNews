"""Google Cloud Storage: the bucket that hands data between the workflows.

Credentials come from the service-account key file when it's present (local
runs), otherwise from Application Default Credentials (CI).
"""

import os

import google.auth
from google.cloud import storage
from google.oauth2 import service_account

BUCKET_NAME = "my-football-news"
DATA_PREFIX = "football-news/datas"
SERVICE_ACCOUNT_FILE = "gen-lang-client.json"


def credentials(scopes):
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        return service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    creds, _ = google.auth.default(scopes=scopes)
    return creds


def client() -> storage.Client:
    creds = credentials(["https://www.googleapis.com/auth/cloud-platform"])
    return storage.Client(credentials=creds, project=creds.project_id)


def download_prefix(bucket, gcs_prefix: str, local_dir: str, verbose: bool = True) -> int:
    """Download every blob under `gcs_prefix` into `local_dir`; returns the count."""
    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    if not blobs and verbose:
        print(f"  No files found: gs://{bucket.name}/{gcs_prefix}")
    for blob in blobs:
        local_path = os.path.join(local_dir, blob.name[len(gcs_prefix):].lstrip("/"))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob.download_to_filename(local_path)
        if verbose:
            print(f"  Downloaded: {local_path}")
    return len(blobs)
