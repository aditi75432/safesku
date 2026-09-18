from __future__ import annotations

import json

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


def main() -> None:
    settings = ProbeSettings()
    client = SaferProductsClient(
        base_url="https://www.saferproducts.gov/WebApi/Cpsc.Cpsrms.Web.Api.svc",
        application_key=settings.saferproducts_api_key,
    )

    first = client.fetch_page(top=1, skip=0)
    second = client.fetch_page(top=1, skip=1)

    print("SafeSKU SaferProducts.gov API probe")
    print("-----------------------------------")
    print(f"First page records: {len(first.records)}")
    print(f"Second page records: {len(second.records)}")

    first_record = first.records[0] if first.records else None
    second_record = second.records[0] if second.records else None
    first_id = None

    if first_record:
        first_id = first_record.get("IncidentReportNumber")
        print(f"First incident ID: {first_id}")
        print(f"Raw IncidentDate: {first_record.get('IncidentDate')!r}")
        print(
            "Raw IncidentReportPublicationDate: "
            f"{first_record.get('IncidentReportPublicationDate')!r}"
        )

        incident = normalize_incident(first_record)

        print(f"Normalized incident date: {incident.incident_date}")
        print(f"Normalized publication date: {incident.publication_date}")
        print(f"Product brand: {incident.product_brand}")
        print(f"Product model: {incident.product_model}")
        print(f"Product category: {incident.product_category}")
        print(f"Product UPC: {incident.product_upc}")
        print(f"Manufacturer: {incident.manufacturer_name}")
        print(f"Retailer: {incident.retailer_name}")
        print(
            "Product description present: "
            f"{bool(incident.product_description)}"
        )
        print(
            "Incident description present: "
            f"{bool(incident.incident_description)}"
        )

        print("Returned property names:")
        print(json.dumps(sorted(first_record.keys()), indent=2))

    if second_record:
        second_id = second_record.get("IncidentReportNumber")
        print(f"Second incident ID: {second_id}")
        print(f"Skip=1 returned a different record: {second_id != first_id}")


if __name__ == "__main__":
    main()
