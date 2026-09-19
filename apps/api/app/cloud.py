from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


def is_cloud_mode() -> bool:
    return os.getenv("SAFE_SKU_CLOUD_MODE", "false").lower() == "true"


def _safe_filename(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
    return value or "safesku-bundle.zip"


class CloudState:
    """Small DynamoDB-backed control plane for cloud jobs, reviews, and history."""

    def __init__(self) -> None:
        table_name = os.getenv("SAFE_SKU_STATE_TABLE", "").strip()
        self.enabled = bool(table_name)
        self.table = boto3.resource("dynamodb").Table(table_name) if self.enabled else None

    def _put(self, item: dict[str, Any]) -> None:
        if not self.enabled:
            return
        assert self.table is not None
        self.table.put_item(Item=item)

    def create_job(self, job_id: str, bucket: str, key: str, filename: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._put({
            "pk": f"JOB#{job_id}",
            "sk": "META",
            "entity": "job",
            "job_id": job_id,
            "status": "queued",
            "processed": 0,
            "total": 0,
            "message": "Upload accepted. Waiting for the ingestion workflow.",
            "bucket": bucket,
            "key": key,
            "filename": filename,
            "created_at": now,
            "updated_at": now,
        })

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not self.enabled:
            return
        assert self.table is not None
        names = {"#updated": "updated_at"}
        values: dict[str, Any] = {":updated": datetime.now(timezone.utc).isoformat()}
        expressions = ["#updated = :updated"]
        for index, (key, value) in enumerate(fields.items()):
            attr = f"#a{index}"
            val = f":v{index}"
            names[attr] = key
            values[val] = value
            expressions.append(f"{attr} = {val}")
        self.table.update_item(
            Key={"pk": f"JOB#{job_id}", "sk": "META"},
            UpdateExpression="SET " + ", ".join(expressions),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        assert self.table is not None
        item = self.table.get_item(Key={"pk": f"JOB#{job_id}", "sk": "META"}).get("Item")
        return dict(item) if item else None

    def set_current_snapshot(self, job_id: str, snapshot_key: str, overview: dict[str, Any]) -> None:
        self._put({
            "pk": "WORKSPACE",
            "sk": "CURRENT",
            "entity": "workspace_snapshot",
            "job_id": job_id,
            "snapshot_key": snapshot_key,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "overview": overview,
        })

    def current_snapshot(self) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        assert self.table is not None
        item = self.table.get_item(Key={"pk": "WORKSPACE", "sk": "CURRENT"}).get("Item")
        return dict(item) if item else None

    def save_review(self, recall_number: str, parent_asin: str, decision: str, note: str) -> dict[str, Any]:
        reviewed_at = datetime.now(timezone.utc).isoformat()
        item = {
            "pk": f"REVIEW#{recall_number}",
            "sk": parent_asin.upper(),
            "entity": "review",
            "recall_number": recall_number,
            "parent_asin": parent_asin.upper(),
            "decision": decision,
            "note": note,
            "reviewed_at": reviewed_at,
        }
        self._put(item)
        return {"decision": decision, "note": note, "reviewed_at": reviewed_at}

    def reviews(self, recall_number: str) -> dict[str, dict[str, str]]:
        if not self.enabled:
            return {}
        assert self.table is not None
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq(f"REVIEW#{recall_number}"),
        )
        return {
            str(item["parent_asin"]): {
                "decision": str(item.get("decision") or ""),
                "note": str(item.get("note") or ""),
                "reviewed_at": str(item.get("reviewed_at") or ""),
            }
            for item in response.get("Items", [])
        }

    def record_history(self, result: dict[str, Any]) -> None:
        if not self.enabled:
            return
        recall = result.get("recall") or {}
        ran_at = datetime.now(timezone.utc).isoformat()
        investigation_id = str(result.get("investigation_id") or uuid.uuid4().hex)
        self._put({
            "pk": "HISTORY",
            "sk": f"{ran_at}#{investigation_id}",
            "entity": "history",
            "investigation_id": investigation_id,
            "recall_number": recall.get("recall_number"),
            "product_name": recall.get("product_name"),
            "ran_at": ran_at,
            "agent_mode": result.get("agent_mode"),
            "pre_recall_public_incident_count": int((result.get("derived_signals") or {}).get("pre_recall_public_incident_count") or 0),
        })

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        assert self.table is not None
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq("HISTORY"),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [dict(item) for item in response.get("Items", [])]


class CloudWorkspace:
    """Loads the latest immutable SQLite workspace snapshot from S3."""

    def __init__(self) -> None:
        self.bucket = os.getenv("SAFE_SKU_UPLOAD_BUCKET", "").strip()
        self.state = CloudState()
        self.s3 = boto3.client("s3")
        self._loaded_job_id: str | None = None
        self._service: Any = None

    def service(self) -> Any:
        from .workspace import WorkspaceService

        current = self.state.current_snapshot()
        if not current:
            return None
        job_id = str(current.get("job_id") or "")
        if self._service is not None and self._loaded_job_id == job_id:
            return self._service

        root = Path("/tmp") / "safesku-cloud" / job_id
        root.mkdir(parents=True, exist_ok=True)
        db_path = root / "safesku.db"
        if not db_path.exists():
            snapshot_key = str(current["snapshot_key"])
            self.s3.download_file(self.bucket, snapshot_key, str(db_path))

        self._service = WorkspaceService(root=root)
        self._loaded_job_id = job_id
        return self._service

    def presign_bundle(self, filename: str, size_bytes: int) -> dict[str, Any]:
        if not self.bucket:
            raise RuntimeError("SAFE_SKU_UPLOAD_BUCKET is not configured.")
        safe_name = _safe_filename(filename)
        upload_id = f"UP-{uuid.uuid4().hex[:12].upper()}"
        key = f"incoming/{upload_id}/{safe_name}"
        url = self.s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": "application/zip"},
            ExpiresIn=900,
        )
        return {
            "upload_id": upload_id,
            "bucket": self.bucket,
            "key": key,
            "filename": safe_name,
            "size_bytes": int(size_bytes),
            "expires_in_seconds": 900,
            "url": url,
        }
