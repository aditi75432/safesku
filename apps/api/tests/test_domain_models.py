from datetime import datetime, timezone

from app.models.enums import DataSource, EvidenceType, MatchDecision, MatchMethod
from app.models.evidence import EvidenceRecord
from app.models.match import ProductMatch
from app.models.product import ProductEntity, ProductIdentifier, ProductMention


def test_product_mention_keeps_source_identity_separate() -> None:
    mention = ProductMention(
        mention_id="pm_123",
        source=DataSource.CPSC,
        source_record_id="10989",
        name="Example Grill",
        model="GR-100",
        identifiers=[ProductIdentifier(kind="cpsc_recall_id", value="10989")],
    )
    assert mention.source == DataSource.CPSC
    assert mention.source_record_id == "10989"
    assert mention.identifiers[0].kind == "cpsc_recall_id"


def test_product_entity_can_link_multiple_mentions() -> None:
    entity = ProductEntity(
        entity_id="pe_123",
        canonical_name="Example Grill",
        mention_ids=["pm_cpsc_1", "pm_amazon_1"],
    )
    assert len(entity.mention_ids) == 2


def test_evidence_record_is_traceable() -> None:
    evidence = EvidenceRecord(
        evidence_id="ev_123",
        source=DataSource.CPSC,
        source_record_id="10989",
        evidence_type=EvidenceType.HAZARD_STATEMENT,
        product_mention_id="pm_123",
        text="Electrical shock hazard.",
    )
    assert evidence.source_record_id == "10989"
    assert evidence.product_mention_id == "pm_123"


def test_product_match_requires_bounded_confidence() -> None:
    match = ProductMatch(
        match_id="match_123",
        left_mention_id="pm_a",
        right_mention_id="pm_b",
        method=MatchMethod.HYBRID,
        decision=MatchDecision.POSSIBLE_MATCH,
        confidence=0.87,
        signals={"brand": 1.0, "model": 0.7},
        reasons=["Brand matches."],
        conflicts=["Variant is not explicitly stated."],
        created_at=datetime.now(timezone.utc),
    )
    assert 0.0 <= match.confidence <= 1.0
