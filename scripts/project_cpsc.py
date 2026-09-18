from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.models.recall import RecallRecord
from app.services.evidence.cpsc import evidence_from_recall, mentions_from_recall


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project normalized CPSC recalls into SafeSKU mentions and evidence."
    )
    parser.add_argument(
        "--input",
        default="data/processed/cpsc/recalls.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/cpsc",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()

    input_path = PROJECT_ROOT / args.input
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[RecallRecord] = []

    with input_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                records.append(
                    RecallRecord.model_validate(json.loads(line))
                )
            except Exception as exc:
                raise ValueError(
                    f"Invalid normalized record at line {line_number}: {exc}"
                ) from exc

    all_mentions = []
    all_evidence = []

    for record in records:
        mentions = mentions_from_recall(record)
        all_mentions.extend(mentions)

        for mention in mentions:
            all_evidence.extend(
                evidence_from_recall(record, mention)
            )

    mentions_path = output_dir / "product_mentions.jsonl"
    evidence_path = output_dir / "evidence.jsonl"
    manifest_path = output_dir / "manifest.json"

    with mentions_path.open("w", encoding="utf-8") as file:
        for mention in all_mentions:
            file.write(
                json.dumps(
                    mention.model_dump(mode="json"),
                    ensure_ascii=False,
                )
                + "\n"
            )

    with evidence_path.open("w", encoding="utf-8") as file:
        for evidence in all_evidence:
            file.write(
                json.dumps(
                    evidence.model_dump(mode="json"),
                    ensure_ascii=False,
                )
                + "\n"
            )

    recall_dates = [
        record.recall_date.isoformat()
        for record in records
        if record.recall_date is not None
    ]

    manifest = {
        "pipeline": "cpsc_projection_v1",
        "source": "cpsc",
        "input": args.input.replace("\\", "/"),
        "input_sha256": sha256_file(input_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recall_records": len(records),
        "product_mentions": len(all_mentions),
        "evidence_records": len(all_evidence),
        "recall_date_min": min(recall_dates) if recall_dates else None,
        "recall_date_max": max(recall_dates) if recall_dates else None,
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("SafeSKU CPSC projection")
    print("-----------------------")
    print(f"Recall records: {len(records)}")
    print(f"Product mentions: {len(all_mentions)}")
    print(f"Evidence records: {len(all_evidence)}")
    print(f"Input SHA-256: {manifest['input_sha256']}")
    print(f"Mentions: {mentions_path.relative_to(PROJECT_ROOT)}")
    print(f"Evidence: {evidence_path.relative_to(PROJECT_ROOT)}")
    print(f"Manifest: {manifest_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
