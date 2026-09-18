from __future__ import annotations

import gzip
import json
from pathlib import Path

from scripts.normalize_amazon_metadata import normalize


def test_normalize_extracts_common_identity_fields():
    record = {
        "parent_asin": "B123",
        "title": "Example Product",
        "main_category": "Appliances",
        "details": {
            "Brand": "Example",
            "Manufacturer": "Example Inc.",
            "Model": "X-1",
            "UPC": "123456789012",
        },
        "features": ["one"],
        "description": ["two"],
    }

    result = normalize(record, "Appliances")

    assert result["parent_asin"] == "B123"
    assert result["brand"] == "Example"
    assert result["manufacturer"] == "Example Inc."
    assert result["model"] == "X-1"
    assert result["upc"] == "123456789012"
    assert result["source_category"] == "Appliances"


def test_normalize_handles_missing_details():
    result = normalize(
        {"parent_asin": "B123", "title": "Example Product", "details": None},
        "Appliances",
    )
    assert result["brand"] == ""
    assert result["upc"] == ""
