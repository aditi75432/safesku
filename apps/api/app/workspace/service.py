from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
import shutil
import tempfile
import threading
import zipfile
from typing import BinaryIO
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .bundle import BUNDLE_FORMAT, _safe_member_name, read_manifest, sha256_file
from .reader import iter_records
from .schema import canonicalize, detect_source
from .store import WorkspaceStore


ROOT = Path(__file__).resolve().parents[4]


def _norm(text: Any) -> str:
    value = "" if text is None else str(text).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: Any) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "due", "to", "of", "a", "an", "in", "on", "new", "product", "products", "model", "number"}
    return {t for t in _norm(text).split() if len(t) >= 3 and t not in stop}


def _date_before(incident: dict[str, Any], recall_date: str) -> bool:
    return bool(
        incident.get("incident_date")
        and incident.get("publication_date")
        and incident["incident_date"][:10] < recall_date[:10]
        and incident["publication_date"][:10] < recall_date[:10]
    )


class WorkspaceService:
    """Product-level orchestration for uploaded SafeSKU artifacts."""

    def __init__(self, root: Path | None = None):
        self.root = root or Path(os.getenv("SAFE_SKU_RUNTIME_DIR", str(ROOT / "data" / "runtime")))
        self.upload_dir = self.root / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.store = WorkspaceStore(self.root / "safesku.db")

    @property
    def has_data(self) -> bool:
        counts = self.store.counts()
        return any(counts.values())

    def save_upload(self, file_name: str, content: bytes, source_hint: str | None = None) -> dict[str, Any]:
        from io import BytesIO
        return self.save_upload_stream(file_name, BytesIO(content), source_hint)

    def _register_local_file(self, file_name: str, path: Path, source_hint: str | None = None) -> dict[str, Any]:
        """Register an already-persisted file as a workspace dataset."""
        fingerprint, _ = sha256_file(path)
        existing = self.store.find_dataset_by_fingerprint(fingerprint)
        if existing:
            path.unlink(missing_ok=True)
            return existing
        with path.open("rb") as handle:
            headers = self._peek_headers(file_name, handle.read(200_000))
        source_type = detect_source(headers, file_name, source_hint)
        dataset_id = f"DS-{uuid.uuid4().hex[:12].upper()}"
        return self.store.add_dataset(dataset_id, source_type, file_name, str(path), fingerprint)

    def save_upload_stream(self, file_name: str, stream: BinaryIO, source_hint: str | None = None) -> dict[str, Any]:
        """Persist an upload without reading the entire artifact into RAM."""
        dataset_id = f"DS-{uuid.uuid4().hex[:12].upper()}"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file_name).name)
        path = self.upload_dir / f"{dataset_id}_{safe_name}"
        digest = hashlib.sha256()
        sample = bytearray()
        total = 0
        try:
            with path.open("wb") as out:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    out.write(chunk)
                    total += len(chunk)
                    if len(sample) < 200_000:
                        sample.extend(chunk[: 200_000 - len(sample)])
            if total == 0:
                raise ValueError("The uploaded file is empty.")
            fingerprint = digest.hexdigest()
            existing = self.store.find_dataset_by_fingerprint(fingerprint)
            if existing:
                path.unlink(missing_ok=True)
                return existing
            headers = self._peek_headers(file_name, bytes(sample))
            source_type = detect_source(headers, file_name, source_hint)
            return self.store.add_dataset(dataset_id, source_type, safe_name, str(path), fingerprint)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _peek_headers(file_name: str, content: bytes) -> set[str]:
        text = content[:200_000].decode("utf-8-sig", errors="ignore")
        suffixes = [s.lower() for s in Path(file_name).suffixes]
        if ".csv" in suffixes:
            import csv
            first = text.splitlines()[0] if text.splitlines() else ""
            return {h.strip() for h in next(csv.reader([first]), [])}
        try:
            if any(suffix in {".json", ".jsonl", ".ndjson"} for suffix in suffixes):
                line = next((x for x in text.splitlines() if x.strip()), text)
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return set(obj.keys())
                if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                    return set(obj[0].keys())
        except json.JSONDecodeError:
            pass
        return set()

    def import_bundle_stream(self, file_name: str, stream: BinaryIO) -> dict[str, Any]:
        """Import one SafeSKU bundle and register every dataset it contains."""
        bundle_dir = self.root / "bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file_name).name)
        bundle_id = f"BND-{uuid.uuid4().hex[:12].upper()}"
        archive_path = bundle_dir / f"{bundle_id}_{safe_name}"
        try:
            with archive_path.open("wb") as out:
                shutil.copyfileobj(stream, out, length=1024 * 1024)
            if archive_path.stat().st_size == 0:
                raise ValueError("The uploaded bundle is empty.")

            extract_dir = Path(tempfile.mkdtemp(prefix=f"{bundle_id}_", dir=str(bundle_dir)))
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    if zf.testzip() is not None:
                        raise ValueError("The SafeSKU bundle contains a corrupt archive member.")
                    manifest = read_manifest(zf)
                    members = {_safe_member_name(info.filename): info for info in zf.infolist() if not info.is_dir()}
                    registered: list[dict[str, Any]] = []
                    for dataset in manifest["datasets"]:
                        member = members.get(dataset["path"])
                        if member is None:
                            raise ValueError(f"Bundle is missing dataset member: {dataset['path']}")
                        target = extract_dir / dataset["path"]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member, "r") as source, target.open("wb") as dest:
                            shutil.copyfileobj(source, dest, length=1024 * 1024)
                        actual_sha, actual_bytes = sha256_file(target)
                        if actual_sha != dataset["sha256"]:
                            raise ValueError(f"Checksum mismatch for {dataset['path']}.")
                        expected_bytes = int(dataset.get("bytes") or 0)
                        if expected_bytes and expected_bytes != actual_bytes:
                            raise ValueError(f"Byte count mismatch for {dataset['path']}.")
                        stored_name = f"bundle_{uuid.uuid4().hex[:12]}_{re.sub(r"[^A-Za-z0-9._-]+", "_", Path(dataset["name"]).name)}"
                        stored_path = self.upload_dir / stored_name
                        shutil.move(str(target), stored_path)
                        registered_row = self._register_local_file(
                            dataset["name"], stored_path, dataset["source_type"],
                        )
                        registered_row["bundle_member_path"] = dataset["path"]
                        registered.append(registered_row)
                # _register_local_file removes duplicate paths. Clean any remaining files.
                result = {
                    "bundle_id": manifest.get("bundle_id") or bundle_id,
                    "format": BUNDLE_FORMAT,
                    "bundle_file": safe_name,
                    "workspace": manifest.get("workspace") or {},
                    "datasets": registered,
                    "dataset_count": len(registered),
                }
                return result
            finally:
                shutil.rmtree(extract_dir, ignore_errors=True)
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise

    def ingest_dataset(self, dataset_id: str) -> None:
        meta = self.store.get_dataset(dataset_id)
        if not meta:
            return
        self.store.set_dataset_status(dataset_id, "processing")
        total = accepted = rejected = 0
        try:
            path = Path(meta["file_path"])
            source_type = str(meta["source_type"])
            batch: list[dict[str, Any]] = []
            for raw in iter_records(path):
                total += 1
                try:
                    batch.append(canonicalize(source_type, raw).values)
                except (ValueError, KeyError, TypeError):
                    rejected += 1
                if len(batch) >= 1000:
                    a, r = self.store.insert_rows(source_type, dataset_id, batch)
                    accepted += a
                    rejected += r
                    batch.clear()
                    self.store.set_dataset_status(dataset_id, "processing", row_count=total, accepted=accepted, rejected=rejected)
            if batch:
                a, r = self.store.insert_rows(source_type, dataset_id, batch)
                accepted += a
                rejected += r
            self.store.set_dataset_status(
                dataset_id, "ready", row_count=total, accepted=accepted, rejected=rejected, completed=True
            )
        except Exception as exc:
            self.store.set_dataset_status(
                dataset_id, "failed", row_count=total, accepted=accepted, rejected=rejected,
                error=f"{type(exc).__name__}: {exc}", completed=True,
            )

    def datasets(self) -> list[dict[str, Any]]:
        return self.store.list_datasets()

    def overview(self) -> dict[str, Any]:
        counts = self.store.counts()
        datasets = self.datasets()
        return {
            "datasets": len(datasets),
            "ready_datasets": sum(1 for d in datasets if d["status"] == "ready"),
            **counts,
        }

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        return {
            "query": query,
            "recalls": self.store.list_recalls(query, limit),
            "products": self.store.search_products(query, min(limit * 10, 200)),
        }

    def _incident_candidates(self, recall: dict[str, Any]) -> list[dict[str, Any]]:
        rows = self.store.get_incidents_for_recall(recall["recall_number"], recall.get("product_name", ""), limit=40)
        return rows

    def _marketplace_candidates(self, recall: dict[str, Any]) -> list[dict[str, Any]]:
        supplied = self.store.get_candidates(recall["recall_number"])
        if supplied:
            # Candidate datasets contain linkage features but are not guaranteed to
            # be stored in rank order. Re-score the supplied candidates using the
            # same deterministic identity evidence model used for generated rows.
            ranked: list[dict[str, Any]] = []
            for row in supplied:
                scored = self._score_linkage_candidate(recall, row)
                ranked.append(scored)
            ranked.sort(key=lambda r: (-float(r["evidence_score"]), str(r.get("parent_asin", ""))))
            return ranked[:20]

        results: dict[str, dict[str, Any]] = {}
        upc = str(recall.get("upc") or "").strip()
        for row in self.store.get_products_by_upc(upc):
            results[row["parent_asin"]] = self._score_candidate(recall, row, exact_upc=True)

        product_name = recall.get("product_name") or recall.get("title") or ""
        recall_tokens = _tokens(product_name)
        if recall_tokens:
            candidates = self.store.search_products(product_name, limit=300)
            for row in candidates:
                asin = row["parent_asin"]
                if asin in results:
                    continue
                scored = self._score_candidate(recall, row, exact_upc=False)
                if scored["shared_token_count"] >= 2 or scored["title_similarity"] >= 0.72 or scored["brand_match"]:
                    results[asin] = scored

        ranked = sorted(results.values(), key=lambda r: (-float(r["evidence_score"]), r["parent_asin"]))
        top = ranked[:20]
        self.store.save_generated_candidates(recall["recall_number"], top)
        return top

    @staticmethod
    def _score_linkage_candidate(recall: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
        """Rank an already-generated linkage row without treating the score as probability."""
        shared = int(row.get("shared_product_token_count") or 0)
        jaccard = float(row.get("product_token_jaccard") or 0.0)
        sequence_similarity = float(row.get("product_name_sequence_similarity") or 0.0)
        exact_upc = bool(int(row.get("exact_upc") or 0))
        recall_tokens = _tokens(recall.get("product_name") or recall.get("title") or "")
        brand_relation = str(row.get("brand_relation") or "")

        score = (
            0.58 * min(shared / max(len(recall_tokens), 1), 1.0)
            + 0.22 * jaccard
            + 0.12 * sequence_similarity
            + 0.08 * (1.0 if brand_relation == "brand_in_cpsc_name" else 0.0)
        )
        if exact_upc:
            score = 1.0
        score = max(0.0, min(score, 1.0))

        evidence: list[str] = []
        if exact_upc:
            evidence.append("Exact UPC agreement")
        if brand_relation == "brand_in_cpsc_name":
            evidence.append("Brand aligns with recall product")
        if shared >= 2:
            evidence.append(f"{shared} shared product-name tokens")
        if sequence_similarity >= 0.7:
            evidence.append("High title similarity")
        if row.get("model"):
            evidence.append("Marketplace model identifier available")

        return {
            "parent_asin": row.get("parent_asin", ""),
            "title": row.get("title", ""),
            "brand": row.get("brand", ""),
            "model": row.get("model", ""),
            "upc": row.get("upc", ""),
            "category": row.get("category", ""),
            "exact_upc": int(exact_upc),
            "shared_token_count": shared,
            "jaccard": round(jaccard, 3),
            "title_similarity": round(sequence_similarity, 3),
            "brand_match": brand_relation == "brand_in_cpsc_name",
            "model_match": False,
            "evidence_score": round(score, 3),
            "evidence": evidence,
            "blocking_sources": row.get("blocking_sources", ""),
            "candidate_bucket_size": row.get("candidate_bucket_size", 0),
            "review_label": row.get("review_label", ""),
        }

    @staticmethod
    def _score_candidate(recall: dict[str, Any], row: dict[str, Any], exact_upc: bool) -> dict[str, Any]:
        recall_name = recall.get("product_name") or recall.get("title") or ""
        candidate_title = row.get("title") or ""
        rt = _tokens(recall_name)
        at = _tokens(candidate_title)
        shared = len(rt & at)
        union = len(rt | at)
        jaccard = shared / union if union else 0.0
        title_similarity = SequenceMatcher(None, _norm(recall_name), _norm(candidate_title)).ratio()
        brand_match = bool(recall.get("brand") and row.get("brand") and _norm(recall["brand"]) == _norm(row["brand"]))
        model_match = bool(recall.get("model") and row.get("model") and _norm(recall["model"]) == _norm(row["model"]))
        score = 0.0
        score += 0.45 if exact_upc else 0.0
        score += 0.25 * min(shared / max(len(rt), 1), 1.0)
        score += 0.18 * jaccard
        score += 0.08 * title_similarity
        score += 0.04 if brand_match else 0.0
        score += 0.03 if model_match else 0.0
        score = 1.0 if exact_upc else min(score, 0.99)
        evidence = []
        if exact_upc:
            evidence.append("Exact UPC agreement")
        if brand_match:
            evidence.append("Brand agreement")
        if model_match:
            evidence.append("Model agreement")
        if shared >= 2:
            evidence.append(f"{shared} shared product-name tokens")
        if title_similarity >= 0.72:
            evidence.append("Strong title similarity")
        return {
            "parent_asin": row.get("parent_asin", ""),
            "title": candidate_title,
            "brand": row.get("brand", ""),
            "model": row.get("model", ""),
            "upc": row.get("upc", ""),
            "category": row.get("category", ""),
            "exact_upc": int(exact_upc),
            "shared_token_count": shared,
            "jaccard": round(jaccard, 3),
            "title_similarity": round(title_similarity, 3),
            "brand_match": brand_match,
            "model_match": model_match,
            "evidence_score": round(score, 3),
            "evidence": evidence,
        }

    def case_for_recall(self, recall_number: str, query: str = "") -> dict[str, Any] | None:
        recall = self.store.get_recall(recall_number)
        if not recall:
            return None
        incidents = self._incident_candidates(recall)
        candidates = self._marketplace_candidates(recall)
        reviews_by_asin: dict[str, int] = {}
        for candidate in candidates[:10]:
            reviews_by_asin[candidate["parent_asin"]] = len(self.store.get_reviews_for_product(candidate["parent_asin"], limit=100))
        return {
            "recall": recall,
            "incidents": incidents,
            "amazon_candidates": candidates,
            "marketplace_review_counts": reviews_by_asin,
        }

    def review(self, recall_number: str, parent_asin: str, decision: str, note: str) -> dict[str, Any]:
        return self.store.save_review(recall_number, parent_asin, decision, note)

    def apply_reviews(self, case: dict[str, Any]) -> None:
        recall_number = str(case.get("recall", {}).get("recall_number") or "")
        decisions = self.store.get_reviews(recall_number)
        for candidate in case.get("amazon_candidates", []):
            decision = decisions.get(candidate.get("parent_asin"))
            if decision:
                candidate["review_label"] = decision["decision"]
                candidate["reviewer_notes"] = decision["note"]
                candidate["reviewed_at"] = decision["reviewed_at"]

    def review_queue(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list_review_queue(limit)

    def start_analysis(self, background_runner) -> dict[str, Any]:
        job_id = f"JOB-{uuid.uuid4().hex[:10].upper()}"
        total = self.store.counts()["recalls"]
        self.store.new_job(job_id, total)
        background_runner(self._run_analysis, job_id)
        return self.store.get_job(job_id) or {"job_id": job_id, "status": "queued", "total": total}

    def _run_analysis(self, job_id: str) -> None:
        self.store.update_job(job_id, status="running", message="Building investigation index")
        total = self.store.counts()["recalls"]
        processed = 0
        for recall in self.store.list_recalls("", limit=max(total, 1)):
            # Candidate generation is demand-driven. The loop warms the most expensive
            # query path so the first investigation after a bulk upload is responsive.
            self._incident_candidates(recall)
            self._marketplace_candidates(recall)
            processed += 1
            if processed == 1 or processed % 10 == 0 or processed == total:
                self.store.update_job(job_id, processed=processed, total=total, message=f"Prepared {processed}/{total} recall investigations")
        use_opensearch = (
            os.getenv("SAFE_SKU_BUILD_IT", "false").lower() == "true"
            and os.getenv("SAFE_SKU_SEARCH_MODE", "sqlite").lower() == "opensearch"
        )
        if use_opensearch:
            # Keep the HTTP request fast. The SAM local container is long-lived, so
            # the index can be built by a dedicated local worker after the response.
            self.store.update_job(job_id, message="Preparing local OpenSearch index")
            threading.Thread(
                target=self._index_opensearch,
                args=(job_id,),
                name=f"safesku-opensearch-{job_id}",
                daemon=True,
            ).start()
            return

        self.store.update_job(
            job_id, status="completed", processed=processed, total=total,
            message="Analysis ready", complete=True,
        )

    def _index_opensearch(self, job_id: str) -> None:
        """Index the active SAM-local workspace without blocking the HTTP request."""
        try:
            from ..local_search import LocalOpenSearch

            self.store.update_job(job_id, message="Indexing evidence in local OpenSearch")
            indexed = LocalOpenSearch().sync_sqlite(self.root / "safesku.db")
            total = self.store.counts()["recalls"]
            self.store.update_job(
                job_id,
                status="completed",
                processed=total,
                total=total,
                message=f"Analysis ready · OpenSearch indexed {indexed:,} evidence documents",
                complete=True,
            )
        except Exception as exc:
            self.store.update_job(
                job_id,
                status="completed",
                message=f"Analysis ready · OpenSearch unavailable; SQLite retained ({type(exc).__name__})",
                complete=True,
            )

    def job(self, job_id: str) -> dict[str, Any] | None:
        return self.store.get_job(job_id)

    def evidence(self, recall_number: str, evidence_id: str) -> dict[str, Any] | None:
        case = self.case_for_recall(recall_number)
        if not case:
            return None
        if evidence_id == f"E-CPSC-{recall_number}":
            return {"source": "CPSC", "record": case["recall"]}
        prefix = f"E-SP-{recall_number}-"
        if evidence_id.startswith(prefix):
            try:
                index = int(evidence_id[len(prefix):]) - 1
                return {"source": "SaferProducts.gov", "record": case["incidents"][index]}
            except (ValueError, IndexError):
                return None
        prefix = f"E-AMZ-{recall_number}-"
        if evidence_id.startswith(prefix):
            try:
                index = int(evidence_id[len(prefix):]) - 1
                return {"source": "Amazon marketplace", "record": case["amazon_candidates"][index]}
            except (ValueError, IndexError):
                return None
        return None
