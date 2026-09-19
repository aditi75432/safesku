from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from .investigation.agent import _extract_recall_number, build_safety_case, run_bedrock_agent
from .buildit import authorize, build_it_enabled, stack_status
from .local_agent import run_local_agent
from .local_search import LocalOpenSearch
from .cloud import CloudWorkspace, is_cloud_mode
from .investigation.store import DataStore
from .workspace import WorkspaceService
from .local_bundle_upload import router as local_bundle_upload_router


app = FastAPI(
    title="SafeSKU Product Safety Intelligence",
    version="0.4.0",
    description="Interactive, evidence-grounded product-safety investigation workspace.",
)

app.include_router(local_bundle_upload_router)

store = DataStore()
workspace = WorkspaceService()
cloud_workspace = CloudWorkspace()
STATIC_DIR = Path(__file__).parent / "static"

# Legacy in-memory state remains only for the compact demo bundle. Uploaded-product
# decisions live in the workspace SQLite store so they survive page refreshes.
_review_lock = Lock()
_review_decisions: dict[str, dict[str, dict[str, str]]] = {}
_history: list[dict[str, Any]] = []


class InvestigationRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    recall_number: str | None = None


class ReviewRequest(BaseModel):
    recall_number: str = Field(min_length=1, max_length=32)
    parent_asin: str = Field(min_length=1, max_length=32)
    decision: str = Field(pattern=r"^(MATCH|NON_MATCH|UNCERTAIN)$")
    note: str = Field(default="", max_length=500)


def _runtime_workspace() -> WorkspaceService | None:
    """Return the durable workspace for the current deployment mode."""
    if is_cloud_mode():
        return cloud_workspace.service()
    return workspace if workspace.has_data else None


def _using_workspace() -> bool:
    return _runtime_workspace() is not None


class WorkspaceProvider:
    """Adapter that lets the existing investigation layer consume workspace cases."""

    def find_case(self, recall_number: str) -> dict[str, Any] | None:
        runtime = _runtime_workspace()
        return runtime.case_for_recall(recall_number) if runtime else None


def _case_provider() -> Any:
    return WorkspaceProvider() if _using_workspace() else store


def _case_reviews(recall_number: str) -> dict[str, dict[str, str]]:
    if is_cloud_mode():
        return cloud_workspace.state.reviews(recall_number)
    with _review_lock:
        return dict(_review_decisions.get(recall_number, {}))


def _apply_reviews(result: dict[str, Any]) -> None:
    recall_number = str(result.get("recall", {}).get("recall_number") or "")
    if _using_workspace() and not is_cloud_mode():
        workspace.apply_reviews(result)
    decisions = _case_reviews(recall_number)
    candidates = result.get("amazon_candidates", [])
    for candidate in candidates:
        asin = str(candidate.get("parent_asin") or "")
        decision = decisions.get(asin)
        if not decision:
            continue
        candidate["review_label"] = decision.get("decision")
        candidate["reviewer_notes"] = decision.get("note", "")
        candidate["reviewed_at"] = decision.get("reviewed_at")
        candidate["review_source"] = "demo_human_review"

    top = candidates[0] if candidates else None
    status = str((result.get("derived_signals") or {}).get("identity_status") or "not_available")
    if top:
        label = str(top.get("review_label") or "").upper()
        if label == "MATCH":
            status = "working_match"
        elif label == "UNCERTAIN":
            status = "human_review_required"
        elif label == "NON_MATCH":
            status = "no_confirmed_match"
        elif not label:
            status = "ranked_candidate_only"
    derived = result.setdefault("derived_signals", {})
    derived["identity_status"] = status
    derived["human_review_required"] = status in {
        "human_review_required", "ranked_candidate_only", "no_confirmed_match",
    }
    derived["reviewed_candidate_count"] = sum(1 for c in candidates if c.get("review_label"))


def _record_history(result: dict[str, Any]) -> None:
    recall = result.get("recall") or {}
    item = {
        "investigation_id": result.get("investigation_id"),
        "recall_number": recall.get("recall_number"),
        "product_name": recall.get("product_name"),
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "agent_mode": result.get("agent_mode"),
        "pre_recall_public_incident_count": (result.get("derived_signals") or {}).get(
            "pre_recall_public_incident_count", 0,
        ),
    }
    if is_cloud_mode():
        cloud_workspace.state.record_history(result)
        return
    with _review_lock:
        _history.insert(0, item)
        del _history[20:]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "safesku-product-safety",
        "agent_mode": os.getenv("SAFE_SKU_AGENT_MODE", "auto"),
        "cloud_mode": is_cloud_mode(),
        "build_it": stack_status() if build_it_enabled() else None,
    }


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    runtime = _runtime_workspace()
    if runtime is not None:
        data = runtime.overview()
        data["workspace_mode"] = True
        data["agent_mode"] = os.getenv("SAFE_SKU_AGENT_MODE", "auto")
        return data
    cases = store.list_cases()
    return {
        "available_cases": len(cases),
        "public_incidents": sum(int(c.get("incident_count") or 0) for c in cases),
        "identity_candidates": sum(int(c.get("candidate_count") or 0) for c in cases),
        "agent_mode": os.getenv("SAFE_SKU_AGENT_MODE", "auto"),
        "data_contract": "CPSC + SaferProducts.gov + Amazon identity artifacts",
        "workspace_mode": False,
    }


@app.get("/api/cases")
def cases() -> dict[str, object]:
    if _using_workspace():
        runtime = _runtime_workspace()
        rows = runtime.store.list_recalls("", limit=1000) if runtime else []
        return {
            "cases": [
                {
                    "recall_number": r["recall_number"],
                    "recall_date": r.get("recall_date"),
                    "product_name": r.get("product_name"),
                    "has_amazon": bool(runtime and runtime.store.counts()["marketplace_products"] > 0),
                    "incident_count": 0,
                    "candidate_count": 0,
                    "hazards": r.get("hazards"),
                }
                for r in rows
            ]
        }
    return {"cases": store.list_cases()}


@app.get("/api/search")
def search(q: str = Query(default="", max_length=200), limit: int = Query(default=12, ge=1, le=50)) -> dict[str, Any]:
    if build_it_enabled() and os.getenv("SAFE_SKU_SEARCH_MODE", "sqlite").lower() == "opensearch":
        searcher = LocalOpenSearch()
        results = searcher.search(q, limit=limit) if searcher.available else []
        if results:
            return {"query": q, "results": results, "search_engine": "opensearch"}
    runtime = _runtime_workspace()
    if runtime is not None:
        data = runtime.search(q, limit=limit)
        return {"query": q, "results": data["recalls"] + data["products"], "search_engine": "sqlite"}
    return {"query": q, "results": store.search_cases(q, limit=limit), "search_engine": "sqlite"}


@app.get("/api/history")
def history() -> dict[str, Any]:
    if is_cloud_mode():
        return {"items": cloud_workspace.state.history()}
    with _review_lock:
        return {"items": list(_history)}


# ----------------------------- Data Workspace -----------------------------


@app.get("/api/workspace/overview")
def workspace_overview() -> dict[str, Any]:
    runtime = _runtime_workspace()
    return runtime.overview() if runtime else {"datasets": 0, "ready_datasets": 0, "recalls": 0, "incidents": 0, "marketplace_products": 0, "marketplace_reviews": 0}


@app.get("/api/workspace/datasets")
def workspace_datasets() -> dict[str, Any]:
    runtime = _runtime_workspace()
    return {"datasets": runtime.datasets() if runtime else []}


@app.get("/api/workspace/bundles")
def workspace_bundles() -> dict[str, Any]:
    if is_cloud_mode():
        current = cloud_workspace.state.current_snapshot()
        return {"bundles": [{"bundle_id": current.get("job_id"), "status": "ready", "snapshot_key": current.get("snapshot_key"), "overview": current.get("overview", {})}] if current else []}
    return {"bundles": workspace.store.list_bundles()}


class CloudUploadCompleteRequest(BaseModel):
    upload_id: str = Field(min_length=3, max_length=64)
    key: str = Field(min_length=1, max_length=1024)
    filename: str = Field(min_length=1, max_length=255)


@app.get("/api/cloud/config")
def cloud_config() -> dict[str, Any]:
    return {
        "enabled": is_cloud_mode(),
        "direct_s3_upload": is_cloud_mode(),
        "max_browser_upload_mb": 500,
        "message": "Cloud uploads use a presigned S3 URL. API Gateway is not used for bundle bytes.",
    }


@app.post("/api/cloud/uploads/presign")
def cloud_presign(filename: str = Query(..., min_length=1, max_length=255), size_bytes: int = Query(..., ge=1, le=500 * 1024 * 1024)) -> dict[str, Any]:
    if not is_cloud_mode():
        raise HTTPException(status_code=404, detail="Cloud upload mode is disabled for this deployment.")
    try:
        return {"ok": True, "upload": cloud_workspace.presign_bundle(filename, size_bytes)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create an upload URL: {exc}") from exc


@app.post("/api/cloud/uploads/complete")
def cloud_complete(request: CloudUploadCompleteRequest) -> dict[str, Any]:
    if not is_cloud_mode():
        raise HTTPException(status_code=404, detail="Cloud upload mode is disabled for this deployment.")
    expected_prefix = "incoming/"
    if not request.key.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="Invalid upload key.")
    bucket = os.getenv("SAFE_SKU_UPLOAD_BUCKET", "").strip()
    state_machine = os.getenv("SAFE_SKU_STATE_MACHINE_ARN", "").strip()
    if not bucket or not state_machine:
        raise HTTPException(status_code=500, detail="Cloud storage configuration is incomplete.")
    try:
        head = cloud_workspace.s3.head_object(Bucket=bucket, Key=request.key)
        job_id = f"JOB-{request.upload_id.replace('UP-', '')}"
        cloud_workspace.state.create_job(job_id, bucket, request.key, request.filename)
        sf = boto3.client("stepfunctions")
        execution = sf.start_execution(
            stateMachineArn=state_machine,
            name=job_id,
            input=json.dumps({
                "job_id": job_id,
                "bucket": bucket,
                "key": request.key,
                "filename": request.filename,
                "bytes": int(head.get("ContentLength") or 0),
            }),
        )
        cloud_workspace.state.update_job(job_id, execution_arn=execution["executionArn"], message="Ingestion workflow started")
        return {"ok": True, "job": cloud_workspace.state.get_job(job_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not start the ingestion workflow: {exc}") from exc


@app.get("/api/cloud/jobs/{job_id}")
def cloud_job(job_id: str) -> dict[str, Any]:
    if not is_cloud_mode():
        raise HTTPException(status_code=404, detail="Cloud mode is disabled for this deployment.")
    job = cloud_workspace.state.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Cloud job {job_id} was not found.")
    return job


@app.post("/api/workspace/bundles/import")
async def import_bundle(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> dict[str, Any]:
    if is_cloud_mode():
        raise HTTPException(status_code=400, detail="AWS deployment uses /api/cloud/uploads/presign and /api/cloud/uploads/complete for bundle uploads.")
    name = file.filename or "safesku-bundle.zip"
    if not name.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="SafeSKU Bundle must be a .zip file.")
    try:
        result = workspace.import_bundle_stream(name, file.file)
        workspace.store.add_bundle(
            result["bundle_id"],
            result["bundle_file"],
            str((result.get("workspace") or {}).get("name") or "SafeSKU workspace"),
            str((result.get("workspace") or {}).get("description") or ""),
        )
        for dataset in result["datasets"]:
            workspace.store.add_bundle_dataset(
                result["bundle_id"], dataset["dataset_id"],
                dataset.get("bundle_member_path", dataset["file_name"]), dataset["source_type"],
            )
            if dataset.get("status") == "queued":
                background_tasks.add_task(workspace.ingest_dataset, dataset["dataset_id"])
        return {"ok": True, "bundle": result}
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workspace/datasets/upload")
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_type: str | None = Query(default=None),
) -> dict[str, Any]:
    if is_cloud_mode():
        raise HTTPException(status_code=400, detail="Use a SafeSKU Bundle for the AWS deployment. Individual uploads are available in local developer mode.")
    name = file.filename or "upload"
    try:
        dataset = workspace.save_upload_stream(name, file.file, source_hint=source_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(workspace.ingest_dataset, dataset["dataset_id"])
    return {"ok": True, "dataset": dataset}


@app.delete("/api/workspace/datasets/{dataset_id}")
def delete_dataset(dataset_id: str) -> dict[str, Any]:
    if is_cloud_mode():
        raise HTTPException(status_code=400, detail="Dataset deletion is managed through a new workspace bundle in AWS.")
    if not workspace.store.delete_dataset(dataset_id):
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} was not found.")
    return {"ok": True, "dataset_id": dataset_id}


@app.post("/api/workspace/analyze")
def start_analysis(background_tasks: BackgroundTasks) -> dict[str, Any]:
    if is_cloud_mode():
        current = cloud_workspace.state.current_snapshot()
        if not current:
            raise HTTPException(status_code=400, detail="Upload a SafeSKU Bundle first. Cloud analysis starts automatically after ingestion.")
        return {"job": {"job_id": current.get("job_id"), "status": "completed", "message": "Cloud workspace is already analyzed and ready."}}
    if workspace.store.counts()["recalls"] == 0:
        raise HTTPException(status_code=400, detail="Upload at least one CPSC recall dataset first.")
    job = workspace.start_analysis(background_tasks.add_task)
    return {"job": job}


@app.get("/api/workspace/jobs/{job_id}")
def analysis_job(job_id: str) -> dict[str, Any]:
    job = cloud_workspace.state.get_job(job_id) if is_cloud_mode() else workspace.job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} was not found.")
    return job


@app.get("/api/workspace/review-queue")
def review_queue(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    runtime = _runtime_workspace()
    if runtime is None:
        return {"items": []}
    return {"items": runtime.review_queue(limit)}


@app.get("/api/workspace/products/{parent_asin}/reviews")
def product_reviews(parent_asin: str, q: str = Query(default="", max_length=100), limit: int = Query(default=30, ge=1, le=100)) -> dict[str, Any]:
    runtime = _runtime_workspace()
    if runtime is None:
        return {"parent_asin": parent_asin.upper(), "reviews": []}
    return {
        "parent_asin": parent_asin.upper(),
        "reviews": runtime.store.get_reviews_for_product(parent_asin.upper(), q, limit),
    }


# ---------------------------- Human review state --------------------------


@app.post("/api/reviews")
def review(request: ReviewRequest) -> dict[str, Any]:
    if build_it_enabled():
        policy = authorize("review_identity", resource_id=request.recall_number.strip())
        if not policy["allowed"]:
            raise HTTPException(status_code=403, detail={"message": "Cedar denied the identity-review action.", "policy": policy})
    recall_number = request.recall_number.strip()
    asin = request.parent_asin.strip().upper()
    provider = _case_provider()
    case = provider.find_case(recall_number)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Recall {recall_number} was not found.")
    valid_asins = {str(c.get("parent_asin") or "").upper() for c in case.get("amazon_candidates", [])}
    if asin not in valid_asins:
        raise HTTPException(status_code=404, detail=f"Candidate {asin} is not present in recall {recall_number}.")

    if is_cloud_mode():
        saved = cloud_workspace.state.save_review(recall_number, asin, request.decision, request.note.strip())
    elif _using_workspace():
        saved = workspace.review(recall_number, asin, request.decision, request.note.strip())
    else:
        saved = {
            "decision": request.decision,
            "note": request.note.strip(),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        with _review_lock:
            _review_decisions.setdefault(recall_number, {})[asin] = saved
    return {"ok": True, "recall_number": recall_number, "parent_asin": asin, **saved}


# ------------------------------ Investigations ----------------------------


@app.get("/api/evidence/{recall_number}/{evidence_id}")
def evidence_detail(recall_number: str, evidence_id: str) -> dict[str, Any]:
    runtime = _runtime_workspace()
    if runtime is not None:
        payload = runtime.evidence(recall_number, evidence_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} was not found.")
        return {"evidence_id": evidence_id, **payload}

    try:
        result = build_safety_case(store, recall_number, f"Open evidence {evidence_id}")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for item in result.get("evidence", []):
        if item.get("evidence_id") == evidence_id:
            source_id = item.get("record_id")
            payload: dict[str, Any] = {"evidence": item}
            for incident in result.get("incidents", []):
                if incident.get("source_record_id") == source_id:
                    payload["record"] = incident
                    break
            if source_id == result.get("recall", {}).get("source_record_id"):
                payload["record"] = result.get("recall")
            for candidate in result.get("amazon_candidates", []):
                if candidate.get("parent_asin") == source_id:
                    payload["record"] = candidate
                    break
            return payload
    raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} was not found.")


@app.get("/api/investigations/{recall_number}/export")
def export_case(recall_number: str, format: str = Query(default="json", pattern=r"^(json|csv)$")) -> Response:
    if build_it_enabled():
        policy = authorize("export", resource_id=recall_number)
        if not policy["allowed"]:
            raise HTTPException(status_code=403, detail={"message": "Cedar denied the export action.", "policy": policy})
    provider = _case_provider()
    try:
        result = build_safety_case(provider, recall_number, f"Export investigation {recall_number}")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _apply_reviews(result)
    if format == "json":
        body = JSONResponse(result)
        body.headers["Content-Disposition"] = f'attachment; filename="safesku_{recall_number}.json"'
        return body

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "id", "source", "title", "date", "status", "details"])
    for item in result.get("evidence", []):
        writer.writerow([
            "evidence", item.get("evidence_id"), item.get("source"), item.get("title"), item.get("date"), "", item.get("kind"),
        ])
    for candidate in result.get("amazon_candidates", []):
        writer.writerow([
            "candidate", candidate.get("parent_asin"), "Amazon marketplace", candidate.get("title"), "",
            candidate.get("review_label", ""), f"score={candidate.get('evidence_score', 0)}",
        ])
    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="safesku_{recall_number}.csv"'},
    )


@app.post("/api/investigations")
def investigate(request: InvestigationRequest) -> dict[str, object]:
    recall_number = (request.recall_number or _extract_recall_number(request.query) or "").strip()
    if build_it_enabled() and recall_number:
        policy = authorize("investigate", resource_id=recall_number)
        if not policy["allowed"]:
            raise HTTPException(status_code=403, detail={"message": "Cedar denied the investigation action.", "policy": policy})
    if not recall_number:
        raise HTTPException(status_code=400, detail="Provide a CPSC recall number, e.g. 'Investigate recall 23034'.")

    provider = _case_provider()
    try:
        result = build_safety_case(provider, recall_number, request.query)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _apply_reviews(result)
    mode = os.getenv("SAFE_SKU_AGENT_MODE", "auto").lower()
    if mode in {"local", "strands_local"} and build_it_enabled():
        try:
            brief, agent_trace = run_local_agent(provider, recall_number, request.query)
            result["safety_brief"] = brief
            result["agent_trace"] = agent_trace
            result["agent_mode"] = "strands_ollama_local"
        except Exception as exc:
            result["agent_mode"] = "local_deterministic_fallback"
            result["agent_warning"] = f"Local Strands agent unavailable; deterministic evidence workflow used: {type(exc).__name__}"
    elif mode in {"auto", "bedrock"} and os.getenv("AWS_REGION"):
        try:
            brief, agent_trace = run_bedrock_agent(provider, recall_number, request.query)
            result["safety_brief"] = brief
            result["agent_trace"] = agent_trace
            result["agent_mode"] = "strands_bedrock"
        except Exception as exc:
            result["agent_mode"] = "local_deterministic_fallback"
            result["agent_warning"] = f"Bedrock agent unavailable; deterministic evidence workflow used: {type(exc).__name__}"

    _apply_reviews(result)
    _record_history(result)
    return result
