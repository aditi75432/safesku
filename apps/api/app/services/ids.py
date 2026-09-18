from hashlib import sha256


def stable_id(prefix: str, *parts: str) -> str:
    """Create a deterministic ID from immutable source identifiers."""

    canonical = "::".join(part.strip() for part in parts)
    digest = sha256(canonical.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
