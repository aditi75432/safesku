from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, confloat

from app.models.enums import MatchDecision, MatchMethod


class ProductMatch(BaseModel):
    """A scored relationship between two product mentions."""

    model_config = ConfigDict(extra="forbid")

    match_id: str
    left_mention_id: str
    right_mention_id: str
    method: MatchMethod
    decision: MatchDecision
    confidence: confloat(ge=0.0, le=1.0)
    signals: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
