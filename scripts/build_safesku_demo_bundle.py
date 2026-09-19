from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as h:
        for line in h:
            line = line.strip()
            if not line:
                continue
            try:
                x = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(x, dict):
                yield x


def discover_safety() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    preferred = list((ROOT / "data/benchmark/linkage").glob("*adjudicated*.jsonl"))
    paths = preferred or list((ROOT / "data/benchmark/linkage").glob("*.jsonl"))
    for path in paths:
        for row in jsonl(path):
            recall = clean(row.get("cpsc_recall_number") or row.get("recall_number"))
            if not recall:
                continue
            if "incident_date" in row or "publication_date" in row:
                out.setdefault(recall, []).append(row)
    return out


def discover_amazon() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    paths = list((ROOT / "data/benchmark/amazon_linkage").glob("*adjudicated*.csv"))
    if not paths:
        paths = list((ROOT / "data/benchmark/amazon_linkage").glob("*.csv"))
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as h:
            for row in csv.DictReader(h):
                recall = clean(row.get("cpsc_recall_number"))
                if recall:
                    out.setdefault(recall, []).append(row)
    return out


def score(row: dict[str, Any]) -> float:
    exact = int(float(clean(row.get("exact_upc")) or 0))
    if exact:
        return 1.0
    shared = float(clean(row.get("shared_product_token_count")) or 0)
    jac = float(clean(row.get("product_token_jaccard")) or 0)
    sim = float(clean(row.get("product_name_sequence_similarity")) or 0)
    brand = 1.0 if clean(row.get("brand_relation")) == "brand_in_cpsc_name" else 0.0
    return max(0.0, min(0.58*min(shared/8,1) + 0.22*jac + 0.12*sim + 0.08*brand, 1.0))


def amazon_view(row: dict[str, Any]) -> dict[str, Any]:
    evidence = []
    if int(float(clean(row.get("exact_upc")) or 0)) == 1:
        evidence.append("Exact UPC agreement")
    if clean(row.get("brand_relation")) == "brand_in_cpsc_name":
        evidence.append("Brand aligns with recall product")
    shared = int(float(clean(row.get("shared_product_token_count")) or 0))
    if shared >= 2:
        evidence.append(f"{shared} shared product-name tokens")
    if float(clean(row.get("product_name_sequence_similarity")) or 0) >= 0.7:
        evidence.append("High title similarity")
    return {
        "review_label": clean(row.get("review_label")),
        "reviewer_notes": clean(row.get("reviewer_notes")),
        "parent_asin": clean(row.get("amazon_parent_asin")),
        "title": clean(row.get("amazon_title")),
        "brand": clean(row.get("amazon_brand")),
        "manufacturer": clean(row.get("amazon_manufacturer")),
        "model": clean(row.get("amazon_model")),
        "upc": clean(row.get("amazon_upc")),
        "category": clean(row.get("amazon_category")),
        "exact_upc": int(float(clean(row.get("exact_upc")) or 0)),
        "shared_product_token_count": int(float(clean(row.get("shared_product_token_count")) or 0)),
        "product_token_jaccard": float(clean(row.get("product_token_jaccard")) or 0),
        "product_name_sequence_similarity": float(clean(row.get("product_name_sequence_similarity")) or 0),
        "brand_relation": clean(row.get("brand_relation")),
        "evidence_score": round(score(row), 3),
        "evidence": evidence,
    }


def recall_view(row: dict[str, Any]) -> dict[str, Any]:
    def parse_hazards(value: Any) -> Any:
        if isinstance(value, list):
            return value
        try:
            return json.loads(clean(value))
        except json.JSONDecodeError:
            return clean(value)
    return {
        "recall_number": clean(row.get("cpsc_recall_number")),
        "source_record_id": clean(row.get("cpsc_source_record_id")),
        "recall_date": clean(row.get("cpsc_recall_date")),
        "product_name": clean(row.get("cpsc_product_name")),
        "title": clean(row.get("cpsc_title")),
        "description": clean(row.get("cpsc_description")),
        "hazards": parse_hazards(row.get("cpsc_hazards")),
        "url": clean(row.get("cpsc_url")),
    }


def incident_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_record_id": clean(row.get("saferproducts_source_record_id")),
        "incident_date": clean(row.get("incident_date")),
        "publication_date": clean(row.get("publication_date")),
        "brand": clean(row.get("incident_brand")),
        "model": clean(row.get("incident_model")),
        "upc": clean(row.get("incident_upc")),
        "product_description": clean(row.get("incident_product_description")),
        "description": clean(row.get("incident_description")),
        "manufacturer": clean(row.get("incident_manufacturer")),
        "retailer": clean(row.get("incident_retailer")),
    }


def main() -> None:
    safety = discover_safety()
    amazon = discover_amazon()
    overlap = set(safety) & set(amazon)
    if not overlap:
        raise SystemExit("No recall number is currently present in both the CPSC/SaferProducts and Amazon review artifacts.")

    # Prefer a known, demonstration-friendly recall when its evidence exists.
    preferred = ["22754", "20111", "22083", "21741", "22117"]
    selected = [r for r in preferred if r in overlap] + sorted(overlap - set(preferred))
    selected = selected[:3]

    cases = []
    for recall_number in selected:
        safety_rows = safety[recall_number]
        amazon_rows = sorted(amazon[recall_number], key=lambda r: (-score(r), clean(r.get("amazon_parent_asin"))))[:8]
        cases.append({
            "recall": recall_view(safety_rows[0]),
            "amazon_candidates": [amazon_view(r) for r in amazon_rows],
            "incidents": [incident_view(r) for r in safety_rows[:20]],
        })

    # Keep the bundle compact and auditable.
    bundle = {
        "bundle_version": "0.2",
        "description": "SafeSKU demo bundle generated from the project's real benchmark artifacts.",
        "cases": cases,
    }
    out = ROOT / "data/demo/safesku_cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"SafeSKU demo bundle built: {out}")
    print(f"Selected recalls: {', '.join(selected)}")
    for case in cases:
        print(f"  {case['recall']['recall_number']}: Amazon candidates={len(case['amazon_candidates'])}, incidents={len(case['incidents'])}")


if __name__ == "__main__":
    main()
