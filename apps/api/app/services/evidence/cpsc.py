from __future__ import annotations

from datetime import datetime, time, timezone

from app.models.enums import DataSource, EvidenceType
from app.models.evidence import EvidenceRecord
from app.models.product import ProductIdentifier, ProductMention
from app.models.recall import RecallRecord
from app.services.ids import stable_id


def _recall_datetime(record: RecallRecord) -> datetime | None:
    if record.recall_date is None:
        return None

    return datetime.combine(
        record.recall_date,
        time.min,
        tzinfo=timezone.utc,
    )


def mentions_from_recall(record: RecallRecord) -> list[ProductMention]:
    """Project CPSC product entries into source-specific product mentions."""

    observed_at = _recall_datetime(record)
    mentions: list[ProductMention] = []

    for index, product in enumerate(record.products):
        mention_id = stable_id(
            "pm",
            DataSource.CPSC,
            record.source_record_id,
            str(index),
            product.name or "",
            product.model or "",
        )

        identifiers = [
            ProductIdentifier(
                kind="cpsc_recall_id",
                value=record.source_record_id,
            )
        ]

        for upc in record.product_upcs:
            identifiers.append(
                ProductIdentifier(
                    kind="upc",
                    value=upc,
                )
            )

        mentions.append(
            ProductMention(
                mention_id=mention_id,
                source=DataSource.CPSC,
                source_record_id=record.source_record_id,
                name=product.name,
                model=product.model,
                category=product.type,
                description=product.description,
                observed_at=observed_at,
                source_url=record.url,
                attributes={
                    "cpsc_category_id": product.category_id or "",
                    "reported_number_of_units": (
                        str(product.number_of_units)
                        if product.number_of_units is not None
                        else ""
                    ),
                },
                identifiers=identifiers,
            )
        )

    return mentions


def evidence_from_recall(
    record: RecallRecord,
    mention: ProductMention,
) -> list[EvidenceRecord]:
    """Create traceable evidence records for one CPSC product mention."""

    observed_at = _recall_datetime(record)
    evidence: list[EvidenceRecord] = []

    recall_text = "\n\n".join(
        part
        for part in (record.title, record.description)
        if part
    )

    if recall_text:
        evidence.append(
            EvidenceRecord(
                evidence_id=stable_id(
                    "ev",
                    DataSource.CPSC,
                    record.source_record_id,
                    mention.mention_id,
                    EvidenceType.RECALL,
                ),
                source=DataSource.CPSC,
                source_record_id=record.source_record_id,
                evidence_type=EvidenceType.RECALL,
                product_mention_id=mention.mention_id,
                text=recall_text,
                observed_at=observed_at,
                published_at=record.last_publish_date,
                source_url=record.url,
            )
        )

    for index, hazard in enumerate(record.hazards):
        if not hazard.name:
            continue

        evidence.append(
            EvidenceRecord(
                evidence_id=stable_id(
                    "ev",
                    DataSource.CPSC,
                    record.source_record_id,
                    mention.mention_id,
                    EvidenceType.HAZARD_STATEMENT,
                    str(index),
                ),
                source=DataSource.CPSC,
                source_record_id=record.source_record_id,
                evidence_type=EvidenceType.HAZARD_STATEMENT,
                product_mention_id=mention.mention_id,
                text=hazard.name,
                observed_at=observed_at,
                published_at=record.last_publish_date,
                source_url=record.url,
                metadata={
                    "hazard_type": hazard.hazard_type or "",
                    "hazard_type_id": hazard.hazard_type_id or "",
                },
            )
        )

    for index, injury in enumerate(record.injuries):
        if not injury:
            continue

        evidence.append(
            EvidenceRecord(
                evidence_id=stable_id(
                    "ev",
                    DataSource.CPSC,
                    record.source_record_id,
                    mention.mention_id,
                    EvidenceType.INJURY_STATEMENT,
                    str(index),
                ),
                source=DataSource.CPSC,
                source_record_id=record.source_record_id,
                evidence_type=EvidenceType.INJURY_STATEMENT,
                product_mention_id=mention.mention_id,
                text=injury,
                observed_at=observed_at,
                published_at=record.last_publish_date,
                source_url=record.url,
            )
        )

    for index, remedy in enumerate(record.remedies):
        if not remedy.name:
            continue

        evidence.append(
            EvidenceRecord(
                evidence_id=stable_id(
                    "ev",
                    DataSource.CPSC,
                    record.source_record_id,
                    mention.mention_id,
                    EvidenceType.REMEDY_STATEMENT,
                    str(index),
                ),
                source=DataSource.CPSC,
                source_record_id=record.source_record_id,
                evidence_type=EvidenceType.REMEDY_STATEMENT,
                product_mention_id=mention.mention_id,
                text=remedy.name,
                observed_at=observed_at,
                published_at=record.last_publish_date,
                source_url=record.url,
            )
        )

    return evidence
