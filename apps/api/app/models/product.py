from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataSource


class ProductIdentifier(BaseModel):
    """A source-specific identifier that can help resolve product identity."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    value: str


class ProductMention(BaseModel):
    """One source's description of a product.

    A mention is not yet a claim that this is a unique real-world product.
    That decision belongs to the entity-resolution layer.
    """

    model_config = ConfigDict(extra="forbid")

    mention_id: str
    source: DataSource
    source_record_id: str

    name: str | None = None
    brand: str | None = None
    model: str | None = None
    variant: str | None = None

    identifiers: list[ProductIdentifier] = Field(default_factory=list)

    category: str | None = None
    description: str | None = None

    observed_at: datetime | None = None
    source_url: str | None = None

    attributes: dict[str, str] = Field(default_factory=dict)


class ProductEntity(BaseModel):
    """Our internal hypothesis that multiple product mentions refer to one entity."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    canonical_name: str
    brand: str | None = None
    model: str | None = None
    category: str | None = None
    identifiers: list[ProductIdentifier] = Field(default_factory=list)
    mention_ids: list[str] = Field(default_factory=list)
