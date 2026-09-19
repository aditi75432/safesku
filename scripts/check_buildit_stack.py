from __future__ import annotations

import os
import urllib.request


def check_http(name: str, url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            print(f"[OK] {name}: HTTP {response.status} {url}")
            return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def main() -> int:
    ok = True
    ok &= check_http("OpenSearch", os.getenv("SAFE_SKU_OPENSEARCH_URL", "http://127.0.0.1:9200"))
    ok &= check_http("Ollama", os.getenv("SAFE_SKU_OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/tags")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
