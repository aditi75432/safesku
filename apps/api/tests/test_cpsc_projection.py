from datetime import date, datetime

from app.models.recall import RecallHazard, RecallProduct, RecallRecord
from app.services.evidence.cpsc import evidence_from_recall, mentions_from_recall


def _record() -> RecallRecord:
    return RecallRecord(
        source_record_id="10989",
        recall_number="26773",
        recall_date=date(2026, 9, 17),
        last_publish_date=datetime(2026, 9, 17, 0, 0),
        title="Example Grill Recall",
        description="Example recall description.",
        url="https://example.com/recall",
        products=[
            RecallProduct(
                name="Example Grill",
                model="GR-100",
                type="Electric Grill",
                category_id="897",
                number_of_units="About 10,000",
            )
        ],
        hazards=[
            RecallHazard(
                name="Electric shock hazard.",
                hazard_type="Shock",
                hazard_type_id="1",
            )
        ],
    )


def test_cpsc_recall_projects_to_product_mention() -> None:
    mentions = mentions_from_recall(_record())
    assert len(mentions) == 1
    assert mentions[0].source_record_id == "10989"
    assert mentions[0].name == "Example Grill"
    assert mentions[0].model == "GR-100"
    assert mentions[0].attributes["reported_number_of_units"] == "About 10,000"


def test_cpsc_recall_projects_to_traceable_evidence() -> None:
    record = _record()
    mention = mentions_from_recall(record)[0]
    evidence = evidence_from_recall(record, mention)

    assert len(evidence) == 2
    assert all(item.source_record_id == "10989" for item in evidence)
    assert all(item.product_mention_id == mention.mention_id for item in evidence)
    assert any(item.text == "Electric shock hazard." for item in evidence)
