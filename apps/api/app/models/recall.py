from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

class RecallProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    description: str | None = None
    model: str | None = None
    type: str | None = None
    category_id: str | None = None
    number_of_units: str | int | None = None

class RecallFirm(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    company_id: str | None = None

class RecallHazard(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    hazard_type: str | None = None
    hazard_type_id: str | None = None

class RecallRemedy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None

class RecallRemedyOption(BaseModel):
    model_config = ConfigDict(extra="ignore")
    option: str | None = None

class RecallRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source: str = "cpsc"
    source_record_id: str
    recall_number: str | None = None
    recall_date: date | None = None
    last_publish_date: datetime | None = None
    title: str | None = None
    description: str | None = None
    url: str | None = None
    consumer_contact: str | None = None
    products: list[RecallProduct] = Field(default_factory=list)
    injuries: list[str] = Field(default_factory=list)
    manufacturers: list[RecallFirm] = Field(default_factory=list)
    retailers: list[RecallFirm] = Field(default_factory=list)
    importers: list[RecallFirm] = Field(default_factory=list)
    distributors: list[RecallFirm] = Field(default_factory=list)
    manufacturer_countries: list[str] = Field(default_factory=list)
    product_upcs: list[str] = Field(default_factory=list)
    hazards: list[RecallHazard] = Field(default_factory=list)
    remedies: list[RecallRemedy] = Field(default_factory=list)
    remedy_options: list[RecallRemedyOption] = Field(default_factory=list)
