from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable


INDEX_NAME = "safesku-evidence"


class LocalOpenSearch:
    """Small OpenSearch adapter used by the Build It local stack."""

    def __init__(self, host: str | None = None):
        self.host = (host or os.getenv("SAFE_SKU_OPENSEARCH_URL", "http://127.0.0.1:9200")).rstrip("/")
        self.client = None
        try:
            from opensearchpy import OpenSearch
            self.client = OpenSearch(hosts=[self.host], use_ssl=self.host.startswith("https://"), verify_certs=False)
        except Exception:
            self.client = None

    @property
    def available(self) -> bool:
        if self.client is None:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def ensure_index(self) -> None:
        if self.client is None:
            raise RuntimeError("opensearch-py is not installed")
        if self.client.indices.exists(index=INDEX_NAME):
            return
        self.client.indices.create(
            index=INDEX_NAME,
            body={
                "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
                "mappings": {
                    "properties": {
                        "doc_type": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "record_id": {"type": "keyword"},
                        "recall_number": {"type": "keyword"},
                        "parent_asin": {"type": "keyword"},
                        "title": {"type": "text"},
                        "product_name": {"type": "text"},
                        "brand": {"type": "text"},
                        "model": {"type": "text"},
                        "text": {"type": "text"},
                        "date": {"type": "date", "format": "strict_date_optional_time||yyyy-MM-dd"},
                    }
                },
            },
        )

    def bulk_index(self, documents: Iterable[dict[str, Any]], chunk_size: int = 1000) -> int:
        if self.client is None:
            raise RuntimeError("opensearch-py is not installed")
        self.ensure_index()
        from opensearchpy.helpers import bulk

        actions = (
            {
                "_index": INDEX_NAME,
                "_id": doc["_id"],
                "_source": {k: v for k, v in doc.items() if k != "_id"},
            }
            for doc in documents
        )
        success, _ = bulk(self.client, actions, chunk_size=chunk_size, request_timeout=60, stats_only=True)
        self.client.indices.refresh(index=INDEX_NAME)
        return int(success)


    def sync_sqlite(self, db_path: str | Path) -> int:
        """Index the canonical workspace tables without changing their source rows."""
        path = Path(db_path)
        if not path.exists():
            raise RuntimeError(f"Workspace database not found: {path}")
        if not self.available:
            raise RuntimeError("OpenSearch is not reachable")

        from .search_index_rows import iter_workspace_documents

        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            return self.bulk_index(iter_workspace_documents(conn))

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search OpenSearch when ready; return empty on an unindexed workspace.

        The application layer intentionally falls back to the canonical SQLite
        workspace when OpenSearch is unavailable or has not been built yet.
        This keeps local tests and first-run workspaces deterministic while
        still allowing OpenSearch to become the fast retrieval layer once the
        analysis/indexing job has completed.
        """
        if self.client is None or not query.strip():
            return []
        body = {
            "size": limit,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "recall_number^8",
                        "parent_asin^6",
                        "product_name^5",
                        "title^5",
                        "brand^3",
                        "model^3",
                        "text",
                    ],
                    "type": "best_fields",
                }
            },
        }
        try:
            response = self.client.search(index=INDEX_NAME, body=body)
        except Exception as exc:
            # A missing index is a normal state before the first analysis run.
            # Do not turn that into a 500; let the canonical workspace answer.
            try:
                from opensearchpy import NotFoundError
                if isinstance(exc, NotFoundError):
                    return []
            except Exception:
                pass
            return []
        return [
            {"score": hit.get("_score"), **hit.get("_source", {})}
            for hit in response.get("hits", {}).get("hits", [])
        ]
