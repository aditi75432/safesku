from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "the", "and", "for", "with", "from", "due", "risk", "serious",
    "injury", "death", "hazard", "sold", "recalls", "recall",
    "product", "products", "model", "number", "this", "that",
    "inc", "llc", "corp", "corporation", "company", "manufactured",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_text(value: Any) -> str:
    if value in (None, ""):
        return ""

    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def tokens(value: Any) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(normalize_text(value))
        if len(token) >= 3 and token not in STOPWORDS
    }


def first_product(recall: dict[str, Any]) -> dict[str, Any]:
    products = recall.get("products") or []
    return products[0] if products else {}


def cpsc_brand(recall: dict[str, Any]) -> str:
    manufacturers = recall.get("manufacturers") or []
    if manufacturers:
        return normalize_text(manufacturers[0].get("name"))

    importers = recall.get("importers") or []
    if importers:
        return normalize_text(importers[0].get("name"))

    return ""


def cpsc_identity_tokens(recall: dict[str, Any]) -> set[str]:
    product = first_product(recall)
    values = (
        recall.get("title"),
        product.get("name"),
        product.get("description"),
        cpsc_brand(recall),
    )

    result: set[str] = set()
    for value in values:
        result.update(tokens(value))

    return result


def incident_identity_tokens(incident: dict[str, Any]) -> set[str]:
    values = (
        incident.get("product_brand"),
        incident.get("product_model"),
        incident.get("product_description"),
        incident.get("manufacturer_name"),
        incident.get("retailer_name"),
    )

    result: set[str] = set()
    for value in values:
        result.update(tokens(value))

    return result


def normalized_upc(value: Any) -> str:
    return normalize_compact(value)


def incident_brand(incident: dict[str, Any]) -> str:
    return normalize_text(incident.get("product_brand"))


def incident_model(incident: dict[str, Any]) -> str:
    return normalize_compact(incident.get("product_model"))


def cpsc_recall_upcs(recall: dict[str, Any]) -> set[str]:
    return {
        normalized_upc(value)
        for value in (recall.get("product_upcs") or [])
        if normalized_upc(value)
    }


def build_inverted_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        incident_id = incident["source_record_id"]
        for token in incident_identity_tokens(incident):
            index[token].add(incident_id)

    return dict(index)


def build_brand_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        brand = incident_brand(incident)
        if brand:
            index[brand].add(incident["source_record_id"])

    return dict(index)


def build_brand_model_index(
    incidents: list[dict[str, Any]],
) -> dict[tuple[str, str], set[str]]:
    index: defaultdict[tuple[str, str], set[str]] = defaultdict(set)

    for incident in incidents:
        brand = incident_brand(incident)
        model = incident_model(incident)
        if brand and model:
            index[(brand, model)].add(incident["source_record_id"])

    return dict(index)


def build_upc_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        upc = normalized_upc(incident.get("product_upc"))
        if upc:
            index[upc].add(incident["source_record_id"])

    return dict(index)


def candidate_count_stats(counts: list[int]) -> dict[str, Any]:
    counts_sorted = sorted(counts)

    if not counts_sorted:
        return {
            "min": 0,
            "median": 0,
            "mean": 0,
            "p90": 0,
            "max": 0,
            "recalls_with_candidates": 0,
        }

    def percentile(p: float) -> int:
        index = min(
            len(counts_sorted) - 1,
            math.ceil(p * len(counts_sorted)) - 1,
        )
        return counts_sorted[index]

    return {
        "min": counts_sorted[0],
        "median": counts_sorted[len(counts_sorted) // 2],
        "mean": round(sum(counts_sorted) / len(counts_sorted), 2),
        "p90": percentile(0.90),
        "max": counts_sorted[-1],
        "recalls_with_candidates": sum(
            count > 0 for count in counts_sorted
        ),
    }


def main() -> None:
    cpsc = load_jsonl(Path("data/benchmark/cpsc/recalls.jsonl"))
    incidents = load_jsonl(
        Path("data/benchmark/saferproducts/incidents.jsonl")
    )

    incidents_by_id = {
        incident["source_record_id"]: incident
        for incident in incidents
    }

    upc_index = build_upc_index(incidents)
    brand_index = build_brand_index(incidents)
    brand_model_index = build_brand_model_index(incidents)
    token_index = build_inverted_index(incidents)

    token_frequency = Counter(
        token
        for incident in incidents
        for token in incident_identity_tokens(incident)
    )

    strategies: dict[str, list[int]] = {
        "upc": [],
        "cpsc_brand_to_incident_brand": [],
        "brand_model": [],
        "any_identity_token": [],
        "rarest_cpsc_token": [],
        "rarest_two_cpsc_tokens": [],
    }

    samples: list[dict[str, Any]] = []

    for recall in cpsc:
        recall_id = recall["source_record_id"]
        product = first_product(recall)
        brand = cpsc_brand(recall)
        upcs = cpsc_recall_upcs(recall)
        identity_tokens = cpsc_identity_tokens(recall)

        upc_candidates: set[str] = set()
        for upc in upcs:
            upc_candidates.update(upc_index.get(upc, set()))

        strategies["upc"].append(len(upc_candidates))
        strategies["cpsc_brand_to_incident_brand"].append(
            len(brand_index.get(brand, set())) if brand else 0
        )

        # CPSC product records do not expose model reliably. This strategy
        # remains a diagnostic channel for recalls where a model is available.
        model = normalize_compact(product.get("model"))
        brand_model_candidates = (
            brand_model_index.get((brand, model), set())
            if brand and model
            else set()
        )
        strategies["brand_model"].append(len(brand_model_candidates))

        any_token_candidates: set[str] = set()
        for token in identity_tokens:
            any_token_candidates.update(token_index.get(token, set()))
        strategies["any_identity_token"].append(len(any_token_candidates))

        ranked_tokens = sorted(
            identity_tokens,
            key=lambda token: (token_frequency[token], token),
        )

        rare_one = set(ranked_tokens[:1])
        rare_two = set(ranked_tokens[:2])

        rare_one_candidates = {
            incident_id
            for token in rare_one
            for incident_id in token_index.get(token, set())
        }

        rare_two_candidates: set[str]
        if len(rare_two) < 2:
            rare_two_candidates = rare_one_candidates
        else:
            first_candidates = token_index.get(ranked_tokens[0], set())
            second_candidates = token_index.get(ranked_tokens[1], set())
            rare_two_candidates = first_candidates & second_candidates

        strategies["rarest_cpsc_token"].append(
            len(rare_one_candidates)
        )
        strategies["rarest_two_cpsc_tokens"].append(
            len(rare_two_candidates)
        )

        if len(samples) < 30:
            samples.append(
                {
                    "cpsc_source_record_id": recall_id,
                    "recall_number": recall.get("recall_number"),
                    "title": recall.get("title"),
                    "product_name": product.get("name"),
                    "strategies": {
                        name: values[-1]
                        for name, values in strategies.items()
                    },
                    "rarest_tokens": ranked_tokens[:5],
                    "rare_token_frequencies": {
                        token: token_frequency[token]
                        for token in ranked_tokens[:5]
                    },
                }
            )

    report = {
        "cpsc_recall_count": len(cpsc),
        "saferproducts_incident_count": len(incidents),
        "incident_identity_index_sizes": {
            "upc_keys": len(upc_index),
            "brand_keys": len(brand_index),
            "brand_model_keys": len(brand_model_index),
            "token_keys": len(token_index),
        },
        "strategy_stats": {
            strategy: candidate_count_stats(counts)
            for strategy, counts in strategies.items()
        },
        "samples": samples,
    }

    output = Path("data/benchmark/linkage/blocking_audit.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU CPSC ↔ SaferProducts blocking audit")
    print("-------------------------------------------")
    print(f"CPSC recalls: {len(cpsc)}")
    print(f"SaferProducts incidents: {len(incidents)}")
    print("\nSTRATEGY CANDIDATE COUNTS")
    for strategy, stats in report["strategy_stats"].items():
        print(
            f"{strategy}: "
            f"with_candidates={stats['recalls_with_candidates']} "
            f"median={stats['median']} "
            f"p90={stats['p90']} "
            f"max={stats['max']}"
        )

    print(f"\nAudit: {output}")


if __name__ == "__main__":
    main()
