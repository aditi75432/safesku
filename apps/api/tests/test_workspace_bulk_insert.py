from pathlib import Path

from app.workspace.store import WorkspaceStore


def test_bulk_amazon_product_insert_refreshes_fts(tmp_path: Path) -> None:
    store = WorkspaceStore(tmp_path / "db.sqlite")
    rows = [
        {
            "parent_asin": "BULK001",
            "title": "Royal Portable Air Conditioner",
            "brand": "Royal",
            "model": "RA-100",
            "upc": "123456789012",
            "manufacturer": "Royal",
            "category": "Appliances",
        },
        {
            "parent_asin": "BULK002",
            "title": "Portable Air Conditioner Filter",
            "brand": "Royal",
            "model": "RF-200",
            "upc": "",
            "manufacturer": "Royal",
            "category": "Appliances",
        },
    ]
    accepted, rejected = store.insert_rows("amazon_products", "DS-BULK", rows)
    assert (accepted, rejected) == (2, 0)
    assert store.counts()["marketplace_products"] == 2
    matches = store.search_products("Royal Portable Air Conditioner", 10)
    assert {row["parent_asin"] for row in matches} == {"BULK001", "BULK002"}
