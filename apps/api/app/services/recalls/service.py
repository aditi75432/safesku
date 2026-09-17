from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.models.recall import RecallRecord
from app.services.recalls.client import CPSCClient
from app.services.recalls.normalizer import normalize_recall


class RecallIngestionService:
    """Fetch, snapshot, normalize, and persist CPSC recalls."""

    def __init__(self, client: CPSCClient) -> None:
        self.client = client

    def ingest(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        raw_output: Path,
        processed_output: Path,
    ) -> tuple[int, int, int]:
        raw_records = self.client.search_recalls(
            start_date=start_date,
            end_date=end_date,
        )

        raw_output.parent.mkdir(parents=True, exist_ok=True)
        processed_output.parent.mkdir(parents=True, exist_ok=True)

        raw_output.write_text(
            json.dumps(
                raw_records,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        normalized: list[RecallRecord] = []
        rejected: list[dict[str, object]] = []

        for raw_record in raw_records:
            try:
                normalized.append(normalize_recall(raw_record))
            except (ValueError, ValidationError) as exc:
                rejected.append(
                    {
                        "source_record_id": raw_record.get("RecallID"),
                        "recall_number": raw_record.get("RecallNumber"),
                        "error": str(exc),
                    }
                )

        with processed_output.open("w", encoding="utf-8") as file:
            for record in normalized:
                file.write(
                    json.dumps(
                        record.model_dump(mode="json"),
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        rejection_output = processed_output.with_name(
            "recall_rejections.jsonl"
        )

        with rejection_output.open("w", encoding="utf-8") as file:
            for rejection in rejected:
                file.write(
                    json.dumps(
                        rejection,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        return len(raw_records), len(normalized), len(rejected)