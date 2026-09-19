from __future__ import annotations

import json
from typing import Any, Iterator
import sqlite3


def _text(*values: Any) -> str:
    return " ".join(str(value) for value in values if value not in (None, ""))


def iter_workspace_documents(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    """Convert canonical workspace rows into compact OpenSearch documents."""
    for row in conn.execute("SELECT * FROM recalls"):
        item = dict(row)
        yield {
            "_id": f"recall:{item['recall_number']}",
            "doc_type": "recall",
            "source": "CPSC",
            "record_id": item.get("source_record_id"),
            "recall_number": item.get("recall_number"),
            "title": item.get("title"),
            "product_name": item.get("product_name"),
            "text": _text(item.get("description"), item.get("hazards")),
            "date": item.get("recall_date"),
        }

    for row in conn.execute("SELECT * FROM incidents"):
        item = dict(row)
        yield {
            "_id": f"incident:{item['source_record_id']}",
            "doc_type": "incident",
            "source": "SaferProducts.gov",
            "record_id": item.get("source_record_id"),
            "recall_number": item.get("recall_number"),
            "title": item.get("product_description"),
            "product_name": item.get("product_description"),
            "brand": item.get("product_brand"),
            "model": item.get("product_model"),
            "text": _text(item.get("incident_description"), item.get("manufacturer_comments")),
            "date": item.get("publication_date") or item.get("incident_date"),
        }

    for row in conn.execute("SELECT * FROM marketplace_products"):
        item = dict(row)
        yield {
            "_id": f"product:{item['parent_asin']}",
            "doc_type": "marketplace_product",
            "source": "Amazon Reviews 2023 metadata",
            "record_id": item.get("parent_asin"),
            "parent_asin": item.get("parent_asin"),
            "title": item.get("title"),
            "product_name": item.get("title"),
            "brand": item.get("brand"),
            "model": item.get("model"),
            "text": _text(item.get("manufacturer"), item.get("category")),
        }

    for row in conn.execute("SELECT * FROM marketplace_reviews"):
        item = dict(row)
        yield {
            "_id": f"review:{item['review_id']}",
            "doc_type": "marketplace_review",
            "source": "Amazon Reviews 2023",
            "record_id": item.get("review_id"),
            "parent_asin": item.get("parent_asin"),
            "title": item.get("review_title"),
            "text": _text(item.get("review_title"), item.get("review_text")),
            "date": item.get("review_date"),
        }

    for row in conn.execute("SELECT * FROM linkage_candidates"):
        item = dict(row)
        yield {
            "_id": f"candidate:{item['recall_number']}:{item['parent_asin']}",
            "doc_type": "identity_candidate",
            "source": "SafeSKU linkage",
            "record_id": item.get("parent_asin"),
            "recall_number": item.get("recall_number"),
            "parent_asin": item.get("parent_asin"),
            "title": item.get("title"),
            "product_name": item.get("title"),
            "brand": item.get("brand"),
            "model": item.get("model"),
            "text": json.dumps({
                "exact_upc": item.get("exact_upc"),
                "token_jaccard": item.get("product_token_jaccard"),
                "sequence_similarity": item.get("product_name_sequence_similarity"),
                "blocking_sources": item.get("blocking_sources"),
            }),
        }
