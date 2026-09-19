from __future__ import annotations

import os
from pathlib import Path

from apps.api.app.local_search import LocalOpenSearch


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("SAFE_SKU_WORKSPACE_DB", str(ROOT / "data" / "runtime" / "safesku.db")))


def main() -> None:
    search = LocalOpenSearch()
    count = search.sync_sqlite(DB_PATH)
    print(f"Indexed {count:,} SafeSKU documents into {search.host}")


if __name__ == "__main__":
    main()
