from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataSource, EvidenceType


class EvidenceRecord(BaseModel):
    """A traceable piece of source evidence.

    The text is source-derived. Any inference belongs in a separate model.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source: DataSource
    source_record_id: str
    evidence_type: EvidenceType
    product_mention_id: str | None = None
    text: str
    observed_at: datetime | None = None
    published_at: datetime | None = None
    source_url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
