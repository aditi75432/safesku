from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable


STOPWORDS = {
    "a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or",
    "the", "to", "with", "this", "that", "new", "pack", "set", "model",
    "item", "product", "black", "white", "inch", "inches",
}


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def tokenize(value: str | None) -> list[str]:
    text = normalize_text(value)
    raw_tokens = re.findall(r"[a-z0-9]+", text)

    # Keep short numeric/alphanumeric identifiers such as "12", "5t", or "x1"
    # because model numbers and sizes are useful identity evidence.
    tokens = [
        token
        for token in raw_tokens
        if token not in STOPWORDS and len(token) >= 2
    ]
    return tokens


def token_set(value: str | None) -> set[str]:
    return set(tokenize(value))


def safe_ratio(left: str | None, right: str | None) -> float:
    left = normalize_text(left)
    right = normalize_text(right)
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(None, left, right).ratio(), 6)


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 0.0
    return round(len(a & b) / len(a | b), 6)


def normalized_identifier(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def exact_upc(cpsc_upcs: Iterable[str], amazon_upc: str | None) -> int:
    amazon = normalized_identifier(amazon_upc)
    if not amazon:
        return 0
    return int(any(normalized_identifier(value) == amazon for value in cpsc_upcs))
