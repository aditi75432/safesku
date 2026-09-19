from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

from .workspace import WorkspaceService


def _state_table():
    name = os.environ["SAFE_SKU_STATE_TABLE"]
    return boto3.resource("dynamodb").Table(name)


def _update_job(table: Any, job_id: str, **fields: Any) -> None:
    expressions = ["#updated = :updated"]
    names = {"#updated": "updated_at"}
    values = {":updated": datetime.now(timezone.utc).isoformat()}
    for index, (key, value) in enumerate(fields.items()):
        names[f"#a{index}"] = key
        values[f":v{index}"] = value
        expressions.append(f"#a{index} = :v{index}")
    table.update_item(
        Key={"pk": f"JOB#{job_id}", "sk": "META"},
        UpdateExpression="SET " + ", ".join(expressions),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Turn one S3 bundle into an immutable SQLite investigation snapshot.

    The worker intentionally reuses the same WorkspaceService used locally. This keeps
    the local and AWS ingestion semantics aligned while S3/DynamoDB provide durable
    cloud storage and job state.
    """
    job_id = str(event["job_id"])
    bucket = str(event["bucket"])
    key = str(event["key"])
    filename = str(event.get("filename") or "safesku-bundle.zip")

    s3 = boto3.client("s3")
    table = _state_table()
    root = Path("/tmp") / f"safesku-job-{job_id}"
    zip_path = root / filename
    root.mkdir(parents=True, exist_ok=True)

    try:
        _update_job(table, job_id, status="running", message="Downloading bundle from S3")
        s3.download_file(bucket, key, str(zip_path))

        service = WorkspaceService(root=root / "workspace")
        with zip_path.open("rb") as handle:
            imported = service.import_bundle_stream(filename, handle)

        datasets = imported.get("datasets") or []
        for index, dataset in enumerate(datasets, start=1):
            _update_job(
                table,
                job_id,
                message=f"Ingesting dataset {index}/{len(datasets)}: {dataset.get('file_name', '')}",
                processed=index - 1,
                total=len(datasets),
            )
            if dataset.get("status") == "queued":
                service.ingest_dataset(dataset["dataset_id"])

        _update_job(table, job_id, message="Preparing investigation snapshot")
        overview = service.overview()

        snapshot_key = f"snapshots/{job_id}/safesku.db"
        db_path = root / "workspace" / "safesku.db"
        # WorkspaceStore uses WAL mode locally. Checkpoint before publishing the
        # immutable snapshot so no committed rows remain only in a sidecar WAL file.
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        s3.upload_file(str(db_path), bucket, snapshot_key, ExtraArgs={"ContentType": "application/x-sqlite3"})
        s3.put_object(
            Bucket=bucket,
            Key=f"snapshots/{job_id}/overview.json",
            Body=json.dumps(overview, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

        table.put_item(Item={
            "pk": "WORKSPACE",
            "sk": "CURRENT",
            "entity": "workspace_snapshot",
            "job_id": job_id,
            "snapshot_key": snapshot_key,
            "overview": overview,
            "published_at": datetime.now(timezone.utc).isoformat(),
        })
        _update_job(table, job_id, status="completed", processed=len(datasets), total=len(datasets), message="SafeSKU cloud workspace is ready")
        return {"ok": True, "job_id": job_id, "snapshot_key": snapshot_key, "overview": overview}
    except Exception as exc:
        _update_job(
            table,
            job_id,
            status="failed",
            message=f"{type(exc).__name__}: {exc}",
        )
        raise
    finally:
        shutil.rmtree(root, ignore_errors=True)
