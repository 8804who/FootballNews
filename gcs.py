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
    # User logins and compute-engine identities carry no project_id; with
    # None the client finds the project from the environment itself.
    return storage.Client(credentials=creds, project=getattr(creds, "project_id", None))


def download_prefix(bucket, gcs_prefix: str, local_dir: str, verbose: bool = True) -> int:
    """Download every blob under `gcs_prefix` into `local_dir`; returns the count."""
    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    if not blobs and verbose:
        print(f"  No files found: gs://{bucket.name}/{gcs_prefix}")
    count = 0
    for blob in blobs:
        rel = blob.name[len(gcs_prefix):].lstrip("/")
        if not rel or rel.endswith("/"):  # folder placeholder, not a file
            continue
        local_path = os.path.join(local_dir, rel)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob.download_to_filename(local_path)
        count += 1
        if verbose:
            print(f"  Downloaded: {local_path}")
    return count
