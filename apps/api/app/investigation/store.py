from __future__ import annotations

import csv
import glob
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[4]


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _norm_text(text: Any) -> str:
    value = _clean(text).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: Any) -> set[str]:
    value = _norm_text(text)
    stop = {
        "the", "and", "for", "with", "due", "to", "of", "a", "an", "in", "on",
        "model", "number", "recall", "sold", "including", "online", "new", "inc",
        "llc", "co", "company", "brand", "product", "products",
    }
    return {t for t in value.split() if len(t) >= 2 and t not in stop}


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _date_value(value: Any) -> date | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value


def _candidate_files(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(Path(p) for p in glob.glob(str(ROOT / pattern), recursive=True))
    # Preserve first occurrence order.
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path.resolve()).lower()
        if path.is_file() and key not in seen:
            seen.add(key)
            out.append(path)
    return out


@dataclass
class DataStore:
    """Small read-only adapter over the SafeSKU research artifacts.

    The deployment path intentionally reads a compact demo bundle first. For local
    development it can discover existing linkage/incident artifacts from data/.
    """

    demo_bundle_path: Path | None = None

    def __post_init__(self) -> None:
        configured = os.getenv("SAFE_SKU_DEMO_BUNDLE", "").strip()
        if configured:
            self.demo_bundle_path = Path(configured)
        elif self.demo_bundle_path is None:
            self.demo_bundle_path = ROOT / "data" / "demo" / "safesku_cases.json"
        self.bundle: dict[str, Any] = self._load_bundle(self.demo_bundle_path)

    @staticmethod
    def _load_bundle(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"cases": []}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"cases": []}
        return value if isinstance(value, dict) else {"cases": []}

    def _case_from_bundle(self, recall_number: str) -> dict[str, Any] | None:
        for case in self.bundle.get("cases", []):
            if _clean(case.get("recall", {}).get("recall_number")) == str(recall_number):
                return case
        return None

    def find_case(self, recall_number: str) -> dict[str, Any] | None:
        # Build It investigations must read the active uploaded workspace, not the
        # older research-review files that may still exist under data/benchmark/.
        # This keeps the investigator aligned with the exact data shown by the UI.
        if os.getenv("SAFE_SKU_BUILD_IT", "false").lower() == "true":
            try:
                from ..workspace.service import WorkspaceService

                case = WorkspaceService().case_for_recall(str(recall_number))
                if case is not None:
                    return case
            except Exception:
                # Fall back to the portable/demo artifacts for non-Build-It usage
                # and for local environments where the workspace is not initialized.
                pass

        case = self._case_from_bundle(recall_number)
        if case:
            return case
        return self._discover_case(recall_number)

    def list_cases(self) -> list[dict[str, Any]]:
        bundle_cases = self.bundle.get("cases", [])
        if bundle_cases:
            return [
                {
                    "recall_number": _clean(c.get("recall", {}).get("recall_number")),
                    "recall_date": _clean(c.get("recall", {}).get("recall_date")),
                    "product_name": _clean(c.get("recall", {}).get("product_name")),
                    "has_amazon": bool(c.get("amazon_candidates")),
                    "incident_count": len(c.get("incidents", [])),
                    "candidate_count": len(c.get("amazon_candidates", [])),
                    "hazards": _clean(c.get("recall", {}).get("hazards")),
                }
                for c in bundle_cases
            ]
        return []

    def search_cases(self, query: str, limit: int = 12) -> list[dict[str, Any]]:
        """Search the compact investigation catalog used by the interactive workspace."""
        needle = _norm_text(query)
        rows = self.list_cases()
        if not needle:
            return rows[:limit]

        terms = set(needle.split())

        def score(row: dict[str, Any]) -> tuple[int, str]:
            hay = _norm_text(" ".join(
                [
                    str(row.get("recall_number", "")),
                    str(row.get("product_name", "")),
                    str(row.get("recall_date", "")),
                    str(row.get("hazards", "")),
                ]
            ))
            exact = needle in hay
            overlap = len(terms & set(hay.split()))
            return (100 if exact else overlap, str(row.get("recall_number", "")))

        matches = [r for r in rows if score(r)[0] > 0]
        matches.sort(key=lambda r: (-score(r)[0], str(r.get("recall_number", ""))))
        return matches[:limit]

    def _discover_case(self, recall_number: str) -> dict[str, Any] | None:
        # Prefer the enriched CPSC↔SaferProducts review artifact already produced by the project.
        safety_paths = _candidate_files([
            "data/benchmark/linkage/*adjudicated*.jsonl",
            "data/benchmark/linkage/*.jsonl",
            "data/processed/**/*safer*.jsonl",
            "data/processed/**/*.jsonl",
        ])
        recalls: dict[str, dict[str, Any]] = {}
        incidents: list[dict[str, Any]] = []
        for path in safety_paths:
            for record in _iter_jsonl(path):
                number = _clean(record.get("cpsc_recall_number") or record.get("recall_number"))
                if number:
                    recalls.setdefault(number, record)
                if "incident_date" in record or "publication_date" in record:
                    if number == str(recall_number):
                        incidents.append(record)

        recall = recalls.get(str(recall_number))
        if recall is None:
            recall = self._discover_recall(str(recall_number))
        if recall is None:
            return None

        amazon_candidates = self._discover_amazon_candidates(str(recall_number), recall)
        incident_rows = self._dedupe_incidents(incidents)
        return self._make_case(recall, amazon_candidates, incident_rows)

    def _discover_recall(self, recall_number: str) -> dict[str, Any] | None:
        paths = _candidate_files([
            "data/processed/**/*cpsc*.jsonl",
            "data/benchmark/cpsc/**/*.jsonl",
            "data/processed/**/*.jsonl",
        ])
        for path in paths:
            for record in _iter_jsonl(path):
                number = _clean(record.get("recall_number") or record.get("cpsc_recall_number"))
                if number == recall_number:
                    return record
        return None

    def _discover_amazon_candidates(self, recall_number: str, recall: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        csv_paths = _candidate_files([
            "data/benchmark/amazon_linkage/*adjudicated*.csv",
            "data/benchmark/amazon_linkage/*review*.csv",
        ])
        for path in csv_paths:
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle):
                        if _clean(row.get("cpsc_recall_number")) == recall_number:
                            candidates.append(self._amazon_row(row))
            except OSError:
                pass

        if not candidates:
            # Generic JSONL candidate artifacts are supported as well.
            paths = _candidate_files([
                "data/benchmark/amazon_linkage/**/*.jsonl",
                "data/processed/**/*amazon*candidate*.jsonl",
            ])
            for path in paths:
                for row in _iter_jsonl(path):
                    if _clean(row.get("cpsc_recall_number") or row.get("recall_number")) == recall_number:
                        candidates.append(self._amazon_row(row))

        if not candidates:
            return []

        # Deterministic evidence score. This is explicitly NOT a calibrated probability.
        scored: list[dict[str, Any]] = []
        for row in candidates:
            scored.append(self._score_amazon(row, recall))
        scored.sort(key=lambda x: (-float(x["evidence_score"]), str(x.get("parent_asin", ""))))
        return scored[:10]

    def _amazon_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "parent_asin": _clean(row.get("amazon_parent_asin") or row.get("parent_asin") or row.get("asin")),
            "title": _clean(row.get("amazon_title") or row.get("title")),
            "brand": _clean(row.get("amazon_brand") or row.get("brand")),
            "manufacturer": _clean(row.get("amazon_manufacturer") or row.get("manufacturer")),
            "model": _clean(row.get("amazon_model") or row.get("model")),
            "upc": _clean(row.get("amazon_upc") or row.get("upc")),
            "category": _clean(row.get("amazon_category") or row.get("category")),
            "exact_upc": int(float(row.get("exact_upc", 0) or 0)),
            "shared_product_token_count": int(float(row.get("shared_product_token_count", 0) or 0)),
            "product_token_jaccard": float(row.get("product_token_jaccard", 0) or 0),
            "product_name_sequence_similarity": float(row.get("product_name_sequence_similarity", 0) or 0),
            "brand_relation": _clean(row.get("brand_relation")),
            "blocking_sources": _clean(row.get("blocking_sources")),
            "candidate_bucket_size": int(float(row.get("candidate_bucket_size", 0) or 0)),
        }

    def _score_amazon(self, row: dict[str, Any], recall: dict[str, Any]) -> dict[str, Any]:
        cpsc_name = _clean(recall.get("product_name") or recall.get("cpsc_product_name"))
        cpsc_tokens = _tokens(cpsc_name)
        amazon_tokens = _tokens(row.get("title"))
        shared = len(cpsc_tokens & amazon_tokens)
        jac = _jaccard(cpsc_tokens, amazon_tokens)
        score = (
            0.58 * min(shared / max(len(cpsc_tokens), 1), 1.0)
            + 0.22 * jac
            + 0.12 * float(row.get("product_name_sequence_similarity", 0) or 0)
            + 0.08 * (1.0 if row.get("brand_relation") == "brand_in_cpsc_name" else 0.0)
        )
        if int(row.get("exact_upc", 0) or 0) == 1:
            score = 1.0
        score = max(0.0, min(score, 1.0))
        out = dict(row)
        out["evidence_score"] = round(score, 3)
        out["shared_tokens_recomputed"] = shared
        out["jaccard_recomputed"] = round(jac, 3)
        out["evidence"] = []
        if int(row.get("exact_upc", 0) or 0) == 1:
            out["evidence"].append("Exact UPC agreement")
        if row.get("brand_relation") == "brand_in_cpsc_name":
            out["evidence"].append("Brand aligns with recall product")
        if shared >= 2:
            out["evidence"].append(f"{shared} shared product-name tokens")
        if float(row.get("product_name_sequence_similarity", 0) or 0) >= 0.7:
            out["evidence"].append("High title similarity")
        if row.get("model"):
            out["evidence"].append("Marketplace model identifier available")
        return out

    @staticmethod
    def _dedupe_incidents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        output: list[dict[str, Any]] = []
        for row in rows:
            key = _clean(row.get("saferproducts_source_record_id") or row.get("source_record_id"))
            key = key or json.dumps(row, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
        output.sort(key=lambda x: (_clean(x.get("publication_date")), _clean(x.get("incident_date"))))
        return output[:20]

    def _make_case(
        self,
        recall: dict[str, Any],
        amazon_candidates: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "recall": self._recall_view(recall),
            "amazon_candidates": amazon_candidates,
            "incidents": [self._incident_view(i) for i in incidents],
        }

    @staticmethod
    def _recall_view(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "recall_number": _clean(record.get("recall_number") or record.get("cpsc_recall_number")),
            "source_record_id": _clean(record.get("source_record_id") or record.get("cpsc_source_record_id")),
            "recall_date": _clean(record.get("recall_date") or record.get("cpsc_recall_date")),
            "product_name": _clean(record.get("product_name") or record.get("cpsc_product_name")),
            "title": _clean(record.get("title") or record.get("cpsc_title")),
            "hazards": record.get("hazards") or record.get("cpsc_hazards") or [],
            "description": _clean(record.get("description") or record.get("cpsc_description")),
            "url": _clean(record.get("url") or record.get("cpsc_url")),
        }

    @staticmethod
    def _incident_view(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_record_id": _clean(
                record.get("saferproducts_source_record_id") or record.get("source_record_id")
            ),
            "incident_date": _clean(record.get("incident_date")),
            "publication_date": _clean(record.get("publication_date")),
            "brand": _clean(record.get("incident_brand") or record.get("product_brand")),
            "model": _clean(record.get("incident_model") or record.get("product_model")),
            "upc": _clean(record.get("incident_upc") or record.get("product_upc")),
            "product_description": _clean(
                record.get("incident_product_description") or record.get("product_description")
            ),
            "description": _clean(record.get("incident_description") or record.get("description")),
            "manufacturer": _clean(record.get("incident_manufacturer") or record.get("manufacturer_name")),
            "retailer": _clean(record.get("incident_retailer") or record.get("retailer_name")),
        }


def is_pre_recall_public(incident: dict[str, Any], recall_date: str) -> bool:
    recall = _date_value(recall_date)
    inc = _date_value(incident.get("incident_date"))
    pub = _date_value(incident.get("publication_date"))
    return bool(recall and inc and pub and inc < recall and pub < recall)
