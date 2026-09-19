from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class WorkspaceStore:
    """SQLite persistence for local SafeSKU development and demos.

    The API is intentionally small. The same repository layer can later be backed by
    S3/DynamoDB/OpenSearch in AWS without changing the web contract.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=60)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    fingerprint TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    accepted_count INTEGER NOT NULL DEFAULT 0,
                    rejected_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    uploaded_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS recalls (
                    recall_number TEXT PRIMARY KEY,
                    source_record_id TEXT NOT NULL,
                    recall_date TEXT,
                    product_name TEXT,
                    title TEXT,
                    hazards TEXT,
                    description TEXT,
                    url TEXT,
                    brand TEXT,
                    model TEXT,
                    upc TEXT,
                    category TEXT,
                    dataset_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_recalls_upc ON recalls(upc);

                CREATE TABLE IF NOT EXISTS incidents (
                    source_record_id TEXT PRIMARY KEY,
                    incident_date TEXT,
                    publication_date TEXT,
                    brand TEXT,
                    model TEXT,
                    upc TEXT,
                    product_description TEXT,
                    description TEXT,
                    manufacturer TEXT,
                    retailer TEXT,
                    recall_number TEXT,
                    dataset_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_recall ON incidents(recall_number);
                CREATE INDEX IF NOT EXISTS idx_incidents_upc ON incidents(upc);

                CREATE TABLE IF NOT EXISTS marketplace_products (
                    parent_asin TEXT PRIMARY KEY,
                    title TEXT,
                    brand TEXT,
                    model TEXT,
                    upc TEXT,
                    manufacturer TEXT,
                    category TEXT,
                    dataset_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_products_upc ON marketplace_products(upc);
                CREATE INDEX IF NOT EXISTS idx_products_category ON marketplace_products(category);

                CREATE TABLE IF NOT EXISTS marketplace_reviews (
                    review_id TEXT PRIMARY KEY,
                    asin TEXT,
                    parent_asin TEXT,
                    rating REAL,
                    review_title TEXT,
                    review_text TEXT,
                    review_date TEXT,
                    verified_purchase TEXT,
                    dataset_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_reviews_asin ON marketplace_reviews(asin);
                CREATE INDEX IF NOT EXISTS idx_reviews_parent_asin ON marketplace_reviews(parent_asin);

                CREATE TABLE IF NOT EXISTS linkage_candidates (
                    recall_number TEXT NOT NULL,
                    parent_asin TEXT NOT NULL,
                    title TEXT,
                    brand TEXT,
                    model TEXT,
                    upc TEXT,
                    exact_upc INTEGER NOT NULL DEFAULT 0,
                    shared_product_token_count INTEGER NOT NULL DEFAULT 0,
                    product_token_jaccard REAL NOT NULL DEFAULT 0,
                    product_name_sequence_similarity REAL NOT NULL DEFAULT 0,
                    brand_relation TEXT,
                    blocking_sources TEXT,
                    review_label TEXT,
                    dataset_id TEXT NOT NULL,
                    PRIMARY KEY (recall_number, parent_asin)
                );

                CREATE TABLE IF NOT EXISTS human_reviews (
                    recall_number TEXT NOT NULL,
                    parent_asin TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT NOT NULL,
                    PRIMARY KEY (recall_number, parent_asin)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS recall_search USING fts5(
                    recall_number UNINDEXED,
                    product_name,
                    title,
                    description,
                    hazards,
                    brand,
                    model,
                    category
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS incident_search USING fts5(
                    source_record_id UNINDEXED,
                    product_description,
                    description,
                    brand,
                    model,
                    retailer,
                    manufacturer
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS product_search USING fts5(
                    parent_asin UNINDEXED,
                    title,
                    brand,
                    model,
                    manufacturer,
                    category
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS review_search USING fts5(
                    review_id UNINDEXED,
                    asin UNINDEXED,
                    parent_asin UNINDEXED,
                    review_title,
                    review_text
                );

                CREATE TABLE IF NOT EXISTS bundles (
                    bundle_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    workspace_name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    imported_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bundle_datasets (
                    bundle_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    member_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    PRIMARY KEY(bundle_id, dataset_id)
                );

                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    processed INTEGER NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                );
                """
            )

    def add_bundle(self, bundle_id: str, file_name: str, workspace_name: str = "", description: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bundles(bundle_id,file_name,workspace_name,description,imported_at) VALUES(?,?,?,?,?)",
                (bundle_id, file_name, workspace_name, description, datetime.now(timezone.utc).isoformat()),
            )

    def add_bundle_dataset(self, bundle_id: str, dataset_id: str, member_path: str, source_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bundle_datasets(bundle_id,dataset_id,member_path,source_type) VALUES(?,?,?,?)",
                (bundle_id, dataset_id, member_path, source_type),
            )

    def list_bundles(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT b.*, COUNT(bd.dataset_id) AS dataset_count FROM bundles b LEFT JOIN bundle_datasets bd ON bd.bundle_id=b.bundle_id GROUP BY b.bundle_id ORDER BY b.imported_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_dataset(self, dataset_id: str, source_type: str, file_name: str, file_path: str, fingerprint: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO datasets(dataset_id, source_type, file_name, file_path, fingerprint, status, uploaded_at) VALUES(?,?,?,?,?,?,?)",
                (dataset_id, source_type, file_name, file_path, fingerprint, "queued", now),
            )
        return self.get_dataset(dataset_id) or {}

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)).fetchone()
        return dict(row) if row else None

    def find_dataset_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM datasets WHERE fingerprint=?", (fingerprint,)).fetchone()
        return dict(row) if row else None

    def list_datasets(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM datasets ORDER BY uploaded_at DESC").fetchall()
        return [dict(row) for row in rows]

    def set_dataset_status(self, dataset_id: str, status: str, *, row_count: int | None = None, accepted: int | None = None, rejected: int | None = None, error: str | None = None, completed: bool = False) -> None:
        updates = ["status=?"]
        params: list[Any] = [status]
        if row_count is not None:
            updates.append("row_count=?")
            params.append(row_count)
        if accepted is not None:
            updates.append("accepted_count=?")
            params.append(accepted)
        if rejected is not None:
            updates.append("rejected_count=?")
            params.append(rejected)
        if error is not None:
            updates.append("error_message=?")
            params.append(error)
        if completed:
            updates.append("completed_at=?")
            params.append(datetime.now(timezone.utc).isoformat())
        params.append(dataset_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE datasets SET {', '.join(updates)} WHERE dataset_id=?", params)

    def insert_rows(self, source_type: str, dataset_id: str, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
        """Persist one canonical batch with one SQLite transaction.

        The original implementation executed several SQL statements per row and
        maintained FTS row-by-row. That is unnecessarily expensive on Windows
        when the workspace runs inside a Docker-backed SAM Local container.
        The fast path below uses executemany plus set-based FTS refreshes. If a
        batch-level SQLite error ever occurs, we fall back to the row-by-row path
        so one malformed record cannot discard an otherwise healthy batch.
        """
        rows = list(rows)
        if not rows:
            return 0, 0

        try:
            with self._connect() as conn:
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA cache_size=-65536")
                cur = conn.cursor()

                if source_type == "cpsc":
                    values = [
                        (
                            row["recall_number"], row["source_record_id"], row["recall_date"],
                            row["product_name"], row["title"], json.dumps(row["hazards"], default=str),
                            row["description"], row["url"], row["brand"], row["model"],
                            row["upc"], row["category"], dataset_id,
                        )
                        for row in rows
                    ]
                    ids = [row["recall_number"] for row in rows]
                    placeholders = ",".join("?" for _ in ids)
                    cur.executemany("""
                        INSERT OR REPLACE INTO recalls(
                            recall_number, source_record_id, recall_date, product_name, title,
                            hazards, description, url, brand, model, upc, category, dataset_id
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, values)
                    cur.execute(f"DELETE FROM recall_search WHERE recall_number IN ({placeholders})", ids)
                    cur.execute(f"""
                        INSERT INTO recall_search(
                            rowid, recall_number, product_name, title, description, hazards, brand, model, category
                        )
                        SELECT rowid, recall_number, product_name, title, description, hazards, brand, model, category
                        FROM recalls
                        WHERE recall_number IN ({placeholders})
                    """, ids)

                elif source_type == "saferproducts":
                    values = [
                        (
                            row["source_record_id"], row["incident_date"], row["publication_date"],
                            row["brand"], row["model"], row["upc"], row["product_description"],
                            row["description"], row["manufacturer"], row["retailer"],
                            row["recall_number"], dataset_id,
                        )
                        for row in rows
                    ]
                    ids = [row["source_record_id"] for row in rows]
                    placeholders = ",".join("?" for _ in ids)
                    cur.executemany("""
                        INSERT OR REPLACE INTO incidents(
                            source_record_id, incident_date, publication_date, brand, model, upc,
                            product_description, description, manufacturer, retailer, recall_number, dataset_id
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """, values)
                    cur.execute(f"DELETE FROM incident_search WHERE source_record_id IN ({placeholders})", ids)
                    cur.execute(f"""
                        INSERT INTO incident_search(
                            rowid, source_record_id, product_description, description, brand, model, retailer, manufacturer
                        )
                        SELECT rowid, source_record_id, product_description, description, brand, model, retailer, manufacturer
                        FROM incidents
                        WHERE source_record_id IN ({placeholders})
                    """, ids)

                elif source_type == "amazon_products":
                    values = [
                        (
                            row["parent_asin"], row["title"], row["brand"], row["model"],
                            row["upc"], row["manufacturer"], row["category"], dataset_id,
                        )
                        for row in rows
                    ]
                    ids = [row["parent_asin"] for row in rows]
                    placeholders = ",".join("?" for _ in ids)
                    cur.executemany("""
                        INSERT OR REPLACE INTO marketplace_products(
                            parent_asin, title, brand, model, upc, manufacturer, category, dataset_id
                        ) VALUES(?,?,?,?,?,?,?,?)
                    """, values)
                    cur.execute(f"DELETE FROM product_search WHERE parent_asin IN ({placeholders})", ids)
                    cur.execute(f"""
                        INSERT INTO product_search(
                            rowid, parent_asin, title, brand, model, manufacturer, category
                        )
                        SELECT rowid, parent_asin, title, brand, model, manufacturer, category
                        FROM marketplace_products
                        WHERE parent_asin IN ({placeholders})
                    """, ids)

                elif source_type == "amazon_reviews":
                    values = []
                    ids = []
                    for row in rows:
                        rating = None
                        try:
                            rating = float(row["rating"]) if row["rating"] else None
                        except (TypeError, ValueError):
                            pass
                        values.append(
                            (
                                row["review_id"], row["asin"], row["parent_asin"], rating,
                                row["review_title"], row["review_text"], row["review_date"],
                                row["verified_purchase"], dataset_id,
                            )
                        )
                        ids.append(row["review_id"])
                    placeholders = ",".join("?" for _ in ids)
                    cur.executemany("""
                        INSERT OR REPLACE INTO marketplace_reviews(
                            review_id, asin, parent_asin, rating, review_title, review_text,
                            review_date, verified_purchase, dataset_id
                        ) VALUES(?,?,?,?,?,?,?,?,?)
                    """, values)
                    cur.execute(f"DELETE FROM review_search WHERE review_id IN ({placeholders})", ids)
                    cur.execute(f"""
                        INSERT INTO review_search(
                            rowid, review_id, asin, parent_asin, review_title, review_text
                        )
                        SELECT rowid, review_id, asin, parent_asin, review_title, review_text
                        FROM marketplace_reviews
                        WHERE review_id IN ({placeholders})
                    """, ids)

                elif source_type == "linkage":
                    values = [
                        (
                            row["recall_number"], row["parent_asin"], row["title"], row["brand"], row["model"],
                            row["upc"], row["exact_upc"], row["shared_product_token_count"],
                            row["product_token_jaccard"], row["product_name_sequence_similarity"],
                            row["brand_relation"], row["blocking_sources"], row["review_label"], dataset_id,
                        )
                        for row in rows
                    ]
                    cur.executemany("""
                        INSERT OR REPLACE INTO linkage_candidates(
                            recall_number, parent_asin, title, brand, model, upc, exact_upc,
                            shared_product_token_count, product_token_jaccard,
                            product_name_sequence_similarity, brand_relation, blocking_sources,
                            review_label, dataset_id
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, values)

                else:
                    raise ValueError(f"Unsupported source type: {source_type}")

            return len(rows), 0
        except (sqlite3.Error, KeyError, ValueError, TypeError):
            # Safe fallback: preserve the previous row-level behavior so a single
            # problematic record can be counted as rejected instead of losing the
            # entire batch.
            return self._insert_rows_fallback(source_type, dataset_id, rows)

    def _insert_rows_fallback(self, source_type: str, dataset_id: str, rows: list[dict[str, Any]]) -> tuple[int, int]:
        accepted = rejected = 0
        with self._connect() as conn:
            cur = conn.cursor()
            for row in rows:
                try:
                    if source_type == "cpsc":
                        cur.execute("""INSERT OR REPLACE INTO recalls VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                            row["recall_number"], row["source_record_id"], row["recall_date"], row["product_name"],
                            row["title"], json.dumps(row["hazards"], default=str), row["description"], row["url"],
                            row["brand"], row["model"], row["upc"], row["category"], dataset_id,
                        ))
                        cur.execute("DELETE FROM recall_search WHERE recall_number=?", (row["recall_number"],))
                        rr = cur.execute("SELECT rowid FROM recalls WHERE recall_number=?", (row["recall_number"],)).fetchone()
                        cur.execute("INSERT INTO recall_search(rowid, recall_number, product_name, title, description, hazards, brand, model, category) VALUES(?,?,?,?,?,?,?,?,?)", (
                            rr[0], row["recall_number"], row["product_name"], row["title"], row["description"],
                            json.dumps(row["hazards"], default=str), row["brand"], row["model"], row["category"],
                        ))
                    elif source_type == "saferproducts":
                        cur.execute("""INSERT OR REPLACE INTO incidents VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                            row["source_record_id"], row["incident_date"], row["publication_date"], row["brand"],
                            row["model"], row["upc"], row["product_description"], row["description"],
                            row["manufacturer"], row["retailer"], row["recall_number"], dataset_id,
                        ))
                        cur.execute("DELETE FROM incident_search WHERE source_record_id=?", (row["source_record_id"],))
                        rr = cur.execute("SELECT rowid FROM incidents WHERE source_record_id=?", (row["source_record_id"],)).fetchone()
                        cur.execute("INSERT INTO incident_search(rowid, source_record_id, product_description, description, brand, model, retailer, manufacturer) VALUES(?,?,?,?,?,?,?,?)", (
                            rr[0], row["source_record_id"], row["product_description"], row["description"], row["brand"],
                            row["model"], row["retailer"], row["manufacturer"],
                        ))
                    elif source_type == "amazon_products":
                        cur.execute("""INSERT OR REPLACE INTO marketplace_products VALUES(?,?,?,?,?,?,?,?)""", (
                            row["parent_asin"], row["title"], row["brand"], row["model"], row["upc"],
                            row["manufacturer"], row["category"], dataset_id,
                        ))
                        cur.execute("DELETE FROM product_search WHERE parent_asin=?", (row["parent_asin"],))
                        rr = cur.execute("SELECT rowid FROM marketplace_products WHERE parent_asin=?", (row["parent_asin"],)).fetchone()
                        cur.execute("INSERT INTO product_search(rowid, parent_asin, title, brand, model, manufacturer, category) VALUES(?,?,?,?,?,?,?)", (
                            rr[0], row["parent_asin"], row["title"], row["brand"], row["model"], row["manufacturer"], row["category"],
                        ))
                    elif source_type == "amazon_reviews":
                        rating = None
                        try:
                            rating = float(row["rating"]) if row["rating"] else None
                        except (TypeError, ValueError):
                            pass
                        cur.execute("""INSERT OR REPLACE INTO marketplace_reviews VALUES(?,?,?,?,?,?,?,?,?)""", (
                            row["review_id"], row["asin"], row["parent_asin"], rating, row["review_title"], row["review_text"],
                            row["review_date"], row["verified_purchase"], dataset_id,
                        ))
                        cur.execute("DELETE FROM review_search WHERE review_id=?", (row["review_id"],))
                        rr = cur.execute("SELECT rowid FROM marketplace_reviews WHERE review_id=?", (row["review_id"],)).fetchone()
                        cur.execute("INSERT INTO review_search(rowid, review_id, asin, parent_asin, review_title, review_text) VALUES(?,?,?,?,?,?)", (
                            rr[0], row["review_id"], row["asin"], row["parent_asin"], row["review_title"], row["review_text"],
                        ))
                    elif source_type == "linkage":
                        cur.execute("""INSERT OR REPLACE INTO linkage_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                            row["recall_number"], row["parent_asin"], row["title"], row["brand"], row["model"], row["upc"],
                            row["exact_upc"], row["shared_product_token_count"], row["product_token_jaccard"],
                            row["product_name_sequence_similarity"], row["brand_relation"], row["blocking_sources"],
                            row["review_label"], dataset_id,
                        ))
                    else:
                        raise ValueError(f"Unsupported source type: {source_type}")
                    accepted += 1
                except (KeyError, ValueError, sqlite3.Error, TypeError):
                    rejected += 1
        return accepted, rejected

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            queries = {
                "recalls": "SELECT COUNT(*) FROM recalls",
                "incidents": "SELECT COUNT(*) FROM incidents",
                "marketplace_products": "SELECT COUNT(*) FROM marketplace_products",
                "marketplace_reviews": "SELECT COUNT(*) FROM marketplace_reviews",
                "linkage_candidates": "SELECT COUNT(*) FROM linkage_candidates",
            }
            return {name: int(conn.execute(sql).fetchone()[0]) for name, sql in queries.items()}

    def list_recalls(self, query: str = "", limit: int = 25) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if query.strip():
                match = " OR ".join(token.replace('"', "") for token in query.lower().split() if token)
                try:
                    rows = conn.execute(
                        """SELECT r.*, bm25(recall_search) AS rank FROM recall_search s JOIN recalls r ON r.rowid=s.rowid WHERE recall_search MATCH ? ORDER BY rank LIMIT ?""",
                        (match, limit),
                    ).fetchall()
                except sqlite3.Error:
                    rows = conn.execute(
                        """SELECT * FROM recalls WHERE recall_number LIKE ? OR product_name LIKE ? OR title LIKE ? LIMIT ?""",
                        (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                    ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM recalls ORDER BY recall_date DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_recall(self, recall_number: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM recalls WHERE recall_number=?", (recall_number,)).fetchone()
        return dict(row) if row else None

    def get_incidents_for_recall(self, recall_number: str, recall_name: str, limit: int = 40) -> list[dict[str, Any]]:
        with self._connect() as conn:
            direct = conn.execute("SELECT * FROM incidents WHERE recall_number=? ORDER BY publication_date LIMIT ?", (recall_number, limit)).fetchall()
            if direct:
                return [dict(r) for r in direct]
            terms = [t for t in recall_name.lower().replace("/", " ").replace("-", " ").split() if len(t) >= 3]
            if not terms:
                return []
            match = " OR ".join(f'"{t.replace(chr(34), "")}"' for t in terms[:12])
            try:
                rows = conn.execute(
                    """SELECT i.*, bm25(incident_search) AS rank FROM incident_search s JOIN incidents i ON i.rowid=s.rowid WHERE incident_search MATCH ? ORDER BY rank LIMIT ?""",
                    (match, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.Error:
                return []


    def save_generated_candidates(self, recall_number: str, candidates: Iterable[dict[str, Any]]) -> None:
        rows = list(candidates)
        if not rows:
            return
        with self._connect() as conn:
            for row in rows:
                conn.execute(
                    """INSERT OR REPLACE INTO linkage_candidates(
                        recall_number, parent_asin, title, brand, model, upc, exact_upc,
                        shared_product_token_count, product_token_jaccard, product_name_sequence_similarity,
                        brand_relation, blocking_sources, review_label, dataset_id
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        recall_number, row.get("parent_asin", ""), row.get("title", ""), row.get("brand", ""),
                        row.get("model", ""), row.get("upc", ""), int(row.get("exact_upc", 0) or 0),
                        int(row.get("shared_token_count", row.get("shared_product_token_count", 0)) or 0),
                        float(row.get("jaccard", row.get("product_token_jaccard", 0)) or 0),
                        float(row.get("title_similarity", row.get("product_name_sequence_similarity", 0)) or 0),
                        "brand_match" if row.get("brand_match") else "", "runtime_generated",
                        row.get("review_label", ""), "SYSTEM_GENERATED",
                    ),
                )

    def get_candidates(self, recall_number: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM linkage_candidates WHERE recall_number=?", (recall_number,)).fetchall()
        return [dict(r) for r in rows]

    def get_products_by_upc(self, upc: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM marketplace_products WHERE upc=? LIMIT ?", (upc, limit)).fetchall()
        return [dict(r) for r in rows]

    def search_products(self, query: str, limit: int = 200) -> list[dict[str, Any]]:
        terms = [t for t in query.lower().replace("/", " ").replace("-", " ").split() if len(t) >= 2]
        if not terms:
            return []
        match = " OR ".join(f'"{t.replace(chr(34), "")}"' for t in terms[:16])
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """SELECT p.*, bm25(product_search) AS rank FROM product_search s JOIN marketplace_products p ON p.rowid=s.rowid WHERE product_search MATCH ? ORDER BY rank LIMIT ?""",
                    (match, limit),
                ).fetchall()
            except sqlite3.Error:
                rows = []
        return [dict(r) for r in rows]

    def get_reviews_for_product(self, parent_asin: str, query: str = "", limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if query.strip():
                match = " OR ".join(token for token in query.lower().split() if token)
                try:
                    rows = conn.execute(
                        """SELECT r.*, bm25(review_search) AS rank FROM review_search s JOIN marketplace_reviews r ON r.rowid=s.rowid WHERE (review_search MATCH ?) AND (r.parent_asin=? OR r.asin=?) ORDER BY rank LIMIT ?""",
                        (match, parent_asin, parent_asin, limit),
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
            else:
                rows = conn.execute(
                    "SELECT * FROM marketplace_reviews WHERE parent_asin=? OR asin=? ORDER BY review_date DESC LIMIT ?",
                    (parent_asin, parent_asin, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def save_review(self, recall_number: str, parent_asin: str, decision: str, note: str) -> dict[str, Any]:
        reviewed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO human_reviews VALUES(?,?,?,?,?)",
                (recall_number, parent_asin, decision, note, reviewed_at),
            )
        return {
            "recall_number": recall_number,
            "parent_asin": parent_asin,
            "decision": decision,
            "note": note,
            "reviewed_at": reviewed_at,
        }

    def get_reviews(self, recall_number: str) -> dict[str, dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM human_reviews WHERE recall_number=?", (recall_number,)).fetchall()
        return {str(r["parent_asin"]): dict(r) for r in rows}

    def list_review_queue(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT lc.recall_number, lc.parent_asin, lc.title, lc.review_label,
                          lc.product_name_sequence_similarity, lc.product_token_jaccard,
                          hr.decision, hr.note, hr.reviewed_at
                   FROM linkage_candidates lc
                   LEFT JOIN human_reviews hr
                     ON hr.recall_number=lc.recall_number AND hr.parent_asin=lc.parent_asin
                   WHERE COALESCE(hr.decision, '') != 'MATCH'
                   ORDER BY COALESCE(lc.exact_upc, 0) DESC, lc.product_name_sequence_similarity DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def new_job(self, job_id: str, total: int, message: str = "Queued") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO analysis_jobs(job_id,status,total,message,started_at) VALUES(?,?,?,?,?)",
                (job_id, "queued", total, message, datetime.now(timezone.utc).isoformat()),
            )

    def update_job(self, job_id: str, *, status: str | None = None, processed: int | None = None, total: int | None = None, message: str | None = None, complete: bool = False) -> None:
        fields: list[str] = []
        params: list[Any] = []
        if status is not None:
            fields.append("status=?"); params.append(status)
        if processed is not None:
            fields.append("processed=?"); params.append(processed)
        if total is not None:
            fields.append("total=?"); params.append(total)
        if message is not None:
            fields.append("message=?"); params.append(message)
        if complete:
            fields.append("completed_at=?"); params.append(datetime.now(timezone.utc).isoformat())
        if not fields:
            return
        params.append(job_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE analysis_jobs SET {', '.join(fields)} WHERE job_id=?", params)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM analysis_jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def delete_dataset(self, dataset_id: str) -> bool:
        with self._connect() as conn:
            found = conn.execute("SELECT 1 FROM datasets WHERE dataset_id=?", (dataset_id,)).fetchone()
            if not found:
                return False
            conn.execute("DELETE FROM recalls WHERE dataset_id=?", (dataset_id,))
            conn.execute("DELETE FROM incidents WHERE dataset_id=?", (dataset_id,))
            conn.execute("DELETE FROM marketplace_products WHERE dataset_id=?", (dataset_id,))
            conn.execute("DELETE FROM marketplace_reviews WHERE dataset_id=?", (dataset_id,))
            conn.execute("DELETE FROM linkage_candidates WHERE dataset_id=?", (dataset_id,))
            conn.execute("DELETE FROM datasets WHERE dataset_id=?", (dataset_id,))
        return True
