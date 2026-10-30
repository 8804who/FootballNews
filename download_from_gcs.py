import argparse
import os
from datetime import datetime, timedelta, timezone

from google.cloud import storage
from google.oauth2 import service_account

BUCKET_NAME = "my-football-news"
GCS_PREFIX = "football-news/datas"
SERVICE_ACCOUNT_FILE = "gen-lang-client.json"
DATA_TYPES = ["fotmob", "news_rss", "newsletter"]


def get_client():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return storage.Client(credentials=credentials, project=credentials.project_id)


def download_prefix(bucket, gcs_prefix: str, local_dir: str):
    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    if not blobs:
        print(f"  No files found: gs://{bucket.name}/{gcs_prefix}")
        return 0

    count = 0
    for blob in blobs:
        relative = blob.name[len(gcs_prefix):].lstrip("/")
        local_path = os.path.join(local_dir, relative)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob.download_to_filename(local_path)
        print(f"  Downloaded: {local_path}")
        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Download football data from GCS")
    parser.add_argument(
        "--days",
        type=int,
        default=8,
        help="Number of past days to download in addition to today (default: 8)",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Specific date to download in YYYYMMDD format (overrides --days)",
    )
    parser.add_argument(
        "--types",
        type=str,
        default=",".join(DATA_TYPES),
        help=f"Comma-separated data types to download (default: {','.join(DATA_TYPES)})",
    )
    args = parser.parse_args()

    types = [t.strip() for t in args.types.split(",")]
    invalid = [t for t in types if t not in DATA_TYPES]
    if invalid:
        parser.error(f"Unknown data types: {invalid}. Valid: {DATA_TYPES}")

    if args.date:
        dates = [args.date]
    else:
        today = datetime.now(timezone.utc)
        # Same folders generate_newsletter.yaml downloads: an edition's
        # matches sit in the folders from last Monday through today
        # (collect_news.py names folders by the day it runs and looks a few
        # days back; edition.py picks matches by kickoff time).
        dates = [
            (today - timedelta(days=i)).strftime("%Y%m%d")
            for i in range(0, args.days + 1)
        ]

    client = get_client()
    bucket = client.bucket(BUCKET_NAME)

    total = 0
    for data_type in types:
        for date_str in dates:
            gcs_prefix = f"{GCS_PREFIX}/{data_type}/{date_str}"
            local_dir = f"datas/{data_type}/{date_str}"
            os.makedirs(local_dir, exist_ok=True)
            print(f"[{data_type}/{date_str}]")
            total += download_prefix(bucket, gcs_prefix, local_dir)

    print(f"\nDone. {total} file(s) downloaded.")


if __name__ == "__main__":
    main()
