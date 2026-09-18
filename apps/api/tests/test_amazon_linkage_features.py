from __future__ import annotations

from apps.api.app.services.linkage.amazon_features import (
    exact_upc,
    jaccard,
    safe_ratio,
    tokenize,
)


def test_tokenize_keeps_short_numeric_and_alphanumeric_identity_tokens():
    assert tokenize("The Example Product 12-Inch") == ["example", "12"]


def test_jaccard():
    assert abs(jaccard(["a", "b"], ["b", "c"]) - 1 / 3) < 1e-6


def test_safe_ratio_is_zero_for_empty_values():
    assert safe_ratio("", "product") == 0.0


def test_exact_upc_normalizes_punctuation():
    assert exact_upc(["0-123-456-789"], "0123456789") == 1
    assert exact_upc(["0123456789"], "9999999999") == 0
