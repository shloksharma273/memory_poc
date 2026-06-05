"""
Background worker service for processing memory ingestion jobs asynchronously.
"""

import time
import traceback
from datetime import datetime, timezone
from db.arango_client import get_db
from services.memory_service import process_memory_event


def fetch_next_job(db) -> dict | None:
    """
    Atomically find one pending job and mark it as processing to prevent duplicates.
    """
    query = """
    FOR job IN memory_ingestion_log
        FILTER job.status == "pending"
        SORT job.created_at ASC
        LIMIT 1
        UPDATE job WITH {
            status: "processing",
            started_at: @started_at
        } IN memory_ingestion_log
        RETURN NEW
    """
    cursor = db.aql.execute(
        query,
        bind_vars={"started_at": datetime.now(timezone.utc).isoformat()}
    )
    results = list(cursor)
    return results[0] if results else None


def run_worker_once(db) -> bool:
    """
    Fetches and processes a single ingestion job.
    Returns True if a job was processed, False otherwise.
    """
    try:
        job = fetch_next_job(db)
        if not job:
            return False

        job_key = job["_key"]
        event_key = job["memory_event_id"]
        print(f"📦 Processing ingestion job {job_key} for event {event_key}...")

        try:
            process_memory_event(event_key)

            # Update job to completed
            db.collection("memory_ingestion_log").update(
                job_key,
                {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": None,
                }
            )
            print(f"✓ Job {job_key} completed successfully.")
        except Exception as e:
            print(f"✗ Job {job_key} failed: {e}")
            traceback.print_exc()

            retry_count = job.get("retry_count", 0) + 1
            if retry_count < 3:
                # Move back to pending for retry
                db.collection("memory_ingestion_log").update(
                    job_key,
                    {
                        "status": "pending",
                        "error": str(e),
                        "retry_count": retry_count,
                        "started_at": None,
                    }
                )
                print(f"🔄 Job {job_key} queued for retry (retry count: {retry_count}).")
            else:
                # Keep failed
                db.collection("memory_ingestion_log").update(
                    job_key,
                    {
                        "status": "failed",
                        "error": str(e),
                        "retry_count": retry_count,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                print(f"❌ Job {job_key} exceeded max retries and is marked failed.")
        return True
    except Exception as e:
        print(f"⚠️ Error in worker loop iteration: {e}")
        traceback.print_exc()
        return False


def worker_loop():
    """Infinite loop for the background worker."""
    print("👷 Ingestion worker starting...")
    # Small pause to allow application/database startup to finish
    time.sleep(2)
    db = get_db()
    print("👷 Ingestion worker ready and polling.")
    while True:
        processed = run_worker_once(db)
        if not processed:
            time.sleep(5)


if __name__ == "__main__":
    try:
        worker_loop()
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")
