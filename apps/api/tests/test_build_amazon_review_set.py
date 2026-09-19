from __future__ import annotations

from scripts.build_amazon_review_set import candidate_size_band, similarity_band


def test_similarity_bands():
    assert similarity_band({"product_token_jaccard": 0.10}) == "low"
    assert similarity_band({"product_token_jaccard": 0.20}) == "medium"
    assert similarity_band({"product_token_jaccard": 0.50}) == "high"


def test_candidate_bucket_bands():
    assert candidate_size_band(1) == "small_bucket"
    assert candidate_size_band(10) == "medium_bucket"
    assert candidate_size_band(51) == "large_bucket"
