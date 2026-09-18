from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analyze_cpsc_saferproducts_linkage import exact_upc_links, load_jsonl


def first_product(recall: dict[str, Any]) -> dict[str, Any]:
    products = recall.get("products") or []
    return products[0] if products else {}


def main() -> None:
    cpsc_path = Path("data/benchmark/cpsc/recalls.jsonl")
    incident_path = Path("data/benchmark/saferproducts/incidents.jsonl")
    output_path = Path("data/benchmark/linkage/exact_upc_review.jsonl")

    recalls = load_jsonl(cpsc_path)
    incidents = load_jsonl(incident_path)

    incidents_by_id = {
        incident["source_record_id"]: incident
        for incident in incidents
    }

    links = exact_upc_links(recalls, incidents)

    recall_by_id = {
        recall["source_record_id"]: recall
        for recall in recalls
    }

    rows: list[dict[str, Any]] = []

    for recall_id, incident_ids in sorted(links.items()):
        recall = recall_by_id[recall_id]
        product = first_product(recall)

        for incident_id in incident_ids:
            incident = incidents_by_id[incident_id]

            row = {
                "cpsc_source_record_id": recall["source_record_id"],
                "cpsc_recall_number": recall.get("recall_number"),
                "cpsc_recall_date": recall.get("recall_date"),
                "cpsc_title": recall.get("title"),
                "cpsc_product_name": product.get("name"),
                "cpsc_product_upcs": recall.get("product_upcs"),
                "saferproducts_source_record_id": incident_id,
                "incident_date": incident.get("incident_date"),
                "publication_date": incident.get("publication_date"),
                "product_brand": incident.get("product_brand"),
                "product_model": incident.get("product_model"),
                "product_description": incident.get("product_description"),
                "product_upc": incident.get("product_upc"),
                "manufacturer_name": incident.get("manufacturer_name"),
                "retailer_name": incident.get("retailer_name"),
                "incident_description": incident.get("incident_description"),
            }
            rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    print("SafeSKU exact-UPC linkage review set")
    print("--------------------------------------")
    print(f"Linked recall count: {len(links)}")
    print(f"Pair count: {len(rows)}")
    print(f"Review file: {output_path}")

    for index, row in enumerate(rows, start=1):
        print(f"\n[{index}]")
        print(
            f"CPSC: {row['cpsc_recall_number']} | "
            f"{row['cpsc_recall_date']} | "
            f"{row['cpsc_product_name']}"
        )
        print(f"Title: {row['cpsc_title']}")
        print(f"CPSC UPC(s): {row['cpsc_product_upcs']}")
        print(
            f"SaferProducts: {row['saferproducts_source_record_id']} | "
            f"incident={row['incident_date']} | "
            f"published={row['publication_date']}"
        )
        print(
            f"Brand={row['product_brand']!r} | "
            f"Model={row['product_model']!r} | "
            f"UPC={row['product_upc']!r}"
        )
        print(f"Manufacturer={row['manufacturer_name']!r}")
        print(f"Retailer={row['retailer_name']!r}")
        print(f"Product: {row['product_description']!r}")
        print(f"Incident: {row['incident_description']!r}")


if __name__ == "__main__":
    main()
