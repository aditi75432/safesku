from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class SafetyIncident(BaseModel):
    """Canonical representation of a public SaferProducts.gov incident."""

    model_config = ConfigDict(extra="ignore")

    source: str = "saferproducts"
    source_record_id: str

    incident_date: date | None = None
    publication_date: date | None = None

    incident_description: str | None = None
    incident_location: str | None = None
    locale: str | None = None

    product_brand: str | None = None
    product_model: str | None = None
    product_description: str | None = None
    product_category: str | None = None
    product_upc: str | None = None
    product_serial_number: str | None = None

    product_manufactured_date: date | None = None
    product_purchased_date: date | None = None

    manufacturer_name: str | None = None
    manufacturer_location: str | None = None
    manufacturer_notification_date: date | None = None
    manufacturer_comments: str | None = None

    retailer_name: str | None = None
    retailer_location: str | None = None
