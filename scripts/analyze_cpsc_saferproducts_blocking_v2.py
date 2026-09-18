from __future__ import annotations

import json
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
    "unit", "units", "including", "included", "new", "used",
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


def compact(value: Any) -> str:
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


def cpsc_company_names(recall: dict[str, Any]) -> set[str]:
    values: set[str] = set()

    for field in ("manufacturers", "importers", "distributors"):
        for item in recall.get(field) or []:
            if isinstance(item, dict):
                value = item.get("name")
            else:
                value = item

            normalized = normalize_text(value)
            if normalized:
                values.add(normalized)

    return values


def cpsc_product_name(recall: dict[str, Any]) -> str:
    return normalize_text(first_product(recall).get("name"))


def cpsc_product_tokens(recall: dict[str, Any]) -> set[str]:
    return tokens(first_product(recall).get("name"))


def incident_identity_values(incident: dict[str, Any]) -> list[str]:
    return [
        normalize_text(incident.get("product_brand")),
        normalize_text(incident.get("product_model")),
        normalize_text(incident.get("product_description")),
        normalize_text(incident.get("manufacturer_name")),
        normalize_text(incident.get("retailer_name")),
    ]


def incident_identity_text(incident: dict[str, Any]) -> str:
    return " ".join(
        value for value in incident_identity_values(incident) if value
    )


def incident_identity_tokens(incident: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for value in incident_identity_values(incident):
        result.update(tokens(value))
    return result


def build_token_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        incident_id = incident["source_record_id"]
        for token in incident_identity_tokens(incident):
            index[token].add(incident_id)

    return dict(index)


def build_company_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        company = normalize_text(incident.get("manufacturer_name"))
        if company:
            index[company].add(incident["source_record_id"])

    return dict(index)


def build_upc_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        value = compact(incident.get("product_upc"))
        if value:
            index[value].add(incident["source_record_id"])

    return dict(index)


def build_incident_text_map(
    incidents: list[dict[str, Any]],
) -> dict[str, str]:
    return {
        incident["source_record_id"]: incident_identity_text(incident)
        for incident in incidents
    }


def stats(values: list[int]) -> dict[str, Any]:
    ordered = sorted(values)

    if not ordered:
        return {
            "with_candidates": 0,
            "min": 0,
            "median": 0,
            "p90": 0,
            "max": 0,
        }

    p90_index = min(len(ordered) - 1, max(0, int(0.9 * len(ordered)) - 1))

    return {
        "with_candidates": sum(value > 0 for value in ordered),
        "min": ordered[0],
        "median": ordered[len(ordered) // 2],
        "p90": ordered[p90_index],
        "max": ordered[-1],
    }


def main() -> None:
    recalls = load_jsonl(Path("data/benchmark/cpsc/recalls.jsonl"))
    incidents = load_jsonl(
        Path("data/benchmark/saferproducts/incidents.jsonl")
    )

    incidents_by_id = {
        incident["source_record_id"]: incident
        for incident in incidents
    }
    incident_text = build_incident_text_map(incidents)

    token_index = build_token_index(incidents)
    company_index = build_company_index(incidents)
    upc_index = build_upc_index(incidents)

    strategy_counts: dict[str, list[int]] = defaultdict(list)

    # Candidate sets are calculated from independent blocking channels.
    candidate_sets: dict[str, dict[str, set[str]]] = {
        "upc": {},
        "product_phrase": {},
        "product_2_tokens": {},
        "product_3_tokens": {},
        "company_to_manufacturer": {},
        "union": {},
    }

    for recall in recalls:
        recall_id = recall["source_record_id"]

        upc_candidates: set[str] = set()
        for value in recall.get("product_upcs") or []:
            key = compact(value)
            if key:
                upc_candidates.update(upc_index.get(key, set()))

        product_name = cpsc_product_name(recall)
        product_name_tokens = cpsc_product_tokens(recall)

        phrase_candidates = {
            incident_id
            for incident_id, text in incident_text.items()
            if product_name and product_name in text
        }

        token_overlap_counts: Counter[str] = Counter()
        for token in product_name_tokens:
            for incident_id in token_index.get(token, set()):
                token_overlap_counts[incident_id] += 1

        two_token_candidates = {
            incident_id
            for incident_id, overlap in token_overlap_counts.items()
            if overlap >= 2
        }

        three_token_candidates = {
            incident_id
            for incident_id, overlap in token_overlap_counts.items()
            if overlap >= 3
        }

        company_candidates: set[str] = set()
        for company in cpsc_company_names(recall):
            company_candidates.update(company_index.get(company, set()))

        union_candidates = (
            upc_candidates
            | phrase_candidates
            | two_token_candidates
            | three_token_candidates
            | company_candidates
        )

        sets = {
            "upc": upc_candidates,
            "product_phrase": phrase_candidates,
            "product_2_tokens": two_token_candidates,
            "product_3_tokens": three_token_candidates,
            "company_to_manufacturer": company_candidates,
            "union": union_candidates,
        }

        for strategy, candidates in sets.items():
            candidate_sets[strategy][recall_id] = candidates
            strategy_counts[strategy].append(len(candidates))

    # The 13 exact-UPC pairs are high-confidence identity seeds.
    # We use them to measure whether a non-UPC blocking channel can recover
    # a known linked incident. This is not a full ground-truth evaluation.
    seed_links: dict[str, set[str]] = defaultdict(set)

    for recall in recalls:
        recall_id = recall["source_record_id"]
        recall_upcs = {
            compact(value)
            for value in recall.get("product_upcs") or []
            if compact(value)
        }

        if not recall_upcs:
            continue

        for incident in incidents:
            incident_upc = compact(incident.get("product_upc"))
            if incident_upc and incident_upc in recall_upcs:
                seed_links[recall_id].add(incident["source_record_id"])

    seed_recovery: dict[str, dict[str, int]] = {}

    for strategy, per_recall in candidate_sets.items():
        linked_recalls = 0
        recovered_pairs = 0
        total_pairs = 0

        for recall_id, true_ids in seed_links.items():
            total_pairs += len(true_ids)
            candidates = per_recall[recall_id]

            if candidates & true_ids:
                linked_recalls += 1

            recovered_pairs += len(candidates & true_ids)

        seed_recovery[strategy] = {
            "seed_recalls": len(seed_links),
            "seed_pairs": total_pairs,
            "recalls_with_recovery": linked_recalls,
            "recovered_pairs": recovered_pairs,
        }

    report = {
        "cpsc_recall_count": len(recalls),
        "saferproducts_incident_count": len(incidents),
        "strategy_stats": {
            strategy: stats(counts)
            for strategy, counts in strategy_counts.items()
        },
        "seed_recovery_from_exact_upc_pairs": seed_recovery,
        "note": (
            "The 13 exact-UPC pairs are high-confidence identity seeds, "
            "not a complete ground-truth set. Seed recovery measures whether "
            "candidate blocking can rediscover known linked incidents without "
            "using UPC."
        ),
    }

    output = Path("data/benchmark/linkage/blocking_audit_v2.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU CPSC ↔ SaferProducts blocking audit v2")
    print("------------------------------------------------")
    print(f"CPSC recalls: {len(recalls)}")
    print(f"SaferProducts incidents: {len(incidents)}")
    print("\nCANDIDATE COUNTS")
    for strategy, values in strategy_counts.items():
        s = stats(values)
        print(
            f"{strategy}: "
            f"with_candidates={s['with_candidates']} "
            f"median={s['median']} "
            f"p90={s['p90']} "
            f"max={s['max']}"
        )

    print("\nSEED RECOVERY")
    for strategy, result in seed_recovery.items():
        print(
            f"{strategy}: "
            f"{result['recovered_pairs']}/{result['seed_pairs']} pairs "
            f"across {result['recalls_with_recovery']}/"
            f"{result['seed_recalls']} linked recalls"
        )

    print(f"\nAudit: {output}")


if __name__ == "__main__":
    main()
