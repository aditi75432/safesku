from __future__ import annotations

from scripts.build_linkage_review_set import (
    choose_review_rows,
    temporal_status,
)


def make_row(
    rid: str,
    iid: str,
    *,
    seed: bool = False,
    similarity: float = 0.2,
    jaccard: float = 0.1,
    shared: int = 2,
    incident_date: str = "2021-01-01",
    publication_date: str = "2021-01-10",
    recall_date: str = "2022-01-01",
) -> dict:
    return {
        "cpsc_source_record_id": rid,
        "saferproducts_source_record_id": iid,
        "cpsc_recall_date": recall_date,
        "incident_date": incident_date,
        "publication_date": publication_date,
        "product_name_sequence_similarity": similarity,
        "product_token_jaccard": jaccard,
        "shared_product_token_count": shared,
        "initial_label": "positive_seed" if seed else "unlabeled",
    }


def test_temporal_status_pre_recall_public() -> None:
    row = make_row("R1", "I1")
    assert temporal_status(row) == "pre_recall_public"


def test_temporal_status_published_after_recall() -> None:
    row = make_row(
        "R1",
        "I1",
        incident_date="2021-01-01",
        publication_date="2022-02-01",
        recall_date="2022-01-01",
    )
    assert temporal_status(row) == "pre_incident_published_after_recall"


def test_temporal_status_incident_on_or_after_recall() -> None:
    row = make_row(
        "R1",
        "I1",
        incident_date="2022-01-01",
        publication_date="2022-02-10",
        recall_date="2022-01-01",
    )
    assert temporal_status(row) == "incident_on_or_after_recall"


def test_all_upc_seeds_are_retained() -> None:
    rows = [
        make_row("R1", "I1", seed=True),
        make_row("R2", "I2", seed=True),
    ]
    rows.extend(
        make_row(f"R{i}", f"I{i}", similarity=0.8, jaccard=0.4)
        for i in range(3, 20)
    )

    selected = choose_review_rows(rows, sample_size=10, per_recall_cap=2, seed=7)
    ids = {(row["cpsc_source_record_id"], row["saferproducts_source_record_id"]) for row in selected}

    assert {("R1", "I1"), ("R2", "I2")} <= ids
    assert len(selected) == 10


def test_per_recall_cap_is_respected_for_non_seed_rows() -> None:
    rows = [
        make_row("R1", f"I{i}", similarity=0.8, jaccard=0.4)
        for i in range(20)
    ]
    selected = choose_review_rows(rows, sample_size=6, per_recall_cap=2, seed=8)
    assert len(selected) == 2
