from __future__ import annotations

import argparse
import json
from datetime import date

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.saferproducts.client import SaferProductsClient
from app.services.saferproducts.normalizer import normalize_incident


class ProbeSettings(BaseSettings):
    saferproducts_api_key: str

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


def odata_datetime(value: date) -> str:
    return f"datetime'{value.isoformat()}T00:00:00'"


def build_filter(start_date: date, end_date: date) -> str:
    return (
        f"IncidentDate ge {odata_datetime(start_date)} "
        f"and IncidentDate lt {odata_datetime(end_date)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe a date-filtered SaferProducts.gov OData window."
    )
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    if end_date <= start_date:
        raise SystemExit("--end-date must be after --start-date.")

    settings = ProbeSettings()
    client = SaferProductsClient(
        base_url="https://www.saferproducts.gov/WebApi/Cpsc.Cpsrms.Web.Api.svc",
        application_key=settings.saferproducts_api_key,
    )

    filter_expression = build_filter(start_date, end_date)

    page = client.fetch_page(
        top=5,
        skip=0,
        filter_expression=filter_expression,
        order_by="IncidentDate asc",
        inline_count=True,
    )

    print("SafeSKU SaferProducts.gov filtered-window probe")
    print("------------------------------------------------")
    print(f"Window: {start_date} -> {end_date}")
    print(f"Filter: {filter_expression}")
    print(f"Records returned: {len(page.records)}")
    print(f"Inline total count: {page.total_count}")
    print(f"Next page available: {page.next_url is not None}")

    if not page.records:
        print("\nNo records matched the filter.")
        return

    normalized = [normalize_incident(record) for record in page.records]

    print("\nFirst returned incidents:")
    for incident in normalized:
        print(
            f"{incident.source_record_id} | "
            f"incident={incident.incident_date} | "
            f"published={incident.publication_date} | "
            f"brand={incident.product_brand!r} | "
            f"model={incident.product_model!r}"
        )

    out = {
        "filter": filter_expression,
        "records_returned": len(page.records),
        "inline_total_count": page.total_count,
        "next_page_available": page.next_url is not None,
        "first_record_ids": [
            incident.source_record_id for incident in normalized
        ],
    }

    print("\nProbe summary:")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
