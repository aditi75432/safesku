from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHUNK_SIZE = 1024 * 1024
USER_AGENT = "SafeSKU/0.1 (research ingestion)"
BASE_URL = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_with_resume(url: str, destination: Path, retries: int = 3) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")

    for attempt in range(1, retries + 1):
        existing = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if existing:
            headers["Range"] = f"bytes={existing}-"

        request = Request(url, headers=headers)

        try:
            with urlopen(request, timeout=60) as response:
                status = getattr(response, "status", None)
                # If the server ignores Range, restart cleanly.
                if existing and status != 206:
                    existing = 0
                    partial.unlink(missing_ok=True)
                    request = Request(url, headers={"User-Agent": USER_AGENT})
                    with urlopen(request, timeout=60) as response2:
                        total = response2.headers.get("Content-Length")
                        total = int(total) if total else None
                        return _stream(response2, partial, 0, total, destination)

                total = response.headers.get("Content-Length")
                total = int(total) + existing if total else None
                return _stream(response, partial, existing, total, destination)

        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            print(f"Download attempt {attempt}/{retries} failed: {exc}")
            if attempt == retries:
                raise
            time.sleep(attempt * 2)

    raise RuntimeError("Unreachable")


def _stream(response, partial: Path, existing: int, total: int | None, destination: Path) -> dict:
    downloaded = existing
    last_report = time.monotonic()
    with partial.open("ab") as handle:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)

            now = time.monotonic()
            if now - last_report >= 2:
                pct = f"{downloaded / total * 100:.1f}%" if total else "unknown%"
                print(f"  {destination.name}: {downloaded / (1024**2):.1f} MB ({pct})")
                last_report = now

    partial.replace(destination)
    return {
        "bytes": downloaded,
        "sha256": sha256_file(destination),
        "url": response.geturl(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Amazon Reviews'23 item metadata.")
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Category to download. Repeat the flag. Defaults to Appliances and Baby_Products.",
    )
    parser.add_argument(
        "--all-configured",
        action="store_true",
        help="Download every category in config/amazon_categories.json. This is several GB.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/amazon/raw/metadata"),
    )
    args = parser.parse_args()

    categories = args.categories or ["Appliances", "Baby_Products"]
    if args.all_configured:
        config = json.loads(Path("config/amazon_categories.json").read_text(encoding="utf-8"))
        categories = [item["name"] for item in config["categories"]]

    manifest_path = args.output_dir / "download_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source": "Amazon Reviews'23",
        "base_url": BASE_URL,
        "categories": {},
    }

    for category in categories:
        if not category.replace("_", "").isalnum():
            raise ValueError(f"Unexpected category name: {category}")

        filename = f"meta_{category}.jsonl.gz"
        url = f"{BASE_URL}/{filename}"
        destination = args.output_dir / filename

        print(f"\nDownloading {category}")
        print(url)

        if destination.exists():
            print(f"Already exists: {destination}")
            manifest["categories"][category] = {
                "url": url,
                "path": str(destination),
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
                "status": "already_present",
            }
            continue

        info = download_with_resume(url, destination)
        manifest["categories"][category] = {
            **info,
            "path": str(destination),
            "status": "downloaded",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Saved: {destination}")

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    main()
