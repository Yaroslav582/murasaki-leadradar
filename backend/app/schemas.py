from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LeadStatus = Literal["new", "database", "sent", "rejected", "deal"]

STATUS_LABELS: dict[str, str] = {
    "new": "Новый",
    "database": "В базе",
    "sent": "Отправлено",
    "rejected": "Отказ",
    "deal": "Сделка",
}

SOURCE_LABELS: dict[str, str] = {
    "demo": "Demo-база",
    "google": "Google Places",
    "twogis": "2GIS",
    "yandex": "Яндекс Карты",
    "yandex_web": "Яндекс Карты (web)",
    "osm": "OpenStreetMap",
    "scraper": "Maps Scraper",
    "vk": "ВКонтакте",
    "zoon": "Zoon.ru",
}


class SocialLinks(BaseModel):
    instagram: str | None = None
    telegram: str | None = None
    whatsapp: str | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    city: str
    address: str
    phone: str | None = None
    website_url: str | None = None
    has_website: bool = False
    rating: float | None = None
    reviews_count: int = 0
    latitude: float | None = None
    longitude: float | None = None
    social_links: dict = Field(default_factory=dict)
    emails: list = Field(default_factory=list)
    opening_hours: list = Field(default_factory=list)
    price_level: int | None = None
    source: str = "demo"
    source_id: str | None = None
    status: str = "new"
    status_label: str = "Новый"
    notes: str | None = None
    demo_id: str | None = None
    enriched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _fill_status_label(self) -> "LeadOut":
        self.status_label = STATUS_LABELS.get(self.status, self.status)
        return self


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    notes: str | None = None
    phone: str | None = None
    website_url: str | None = None


class BulkStatusUpdate(BaseModel):
    ids: list[str]
    status: LeadStatus


class LeadsPage(BaseModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int
    pages: int


class FacetValue(BaseModel):
    value: str
    count: int


class MetaOut(BaseModel):
    cities: list[FacetValue]
    categories: list[FacetValue]
    statuses: list[FacetValue]
    sources: list[FacetValue]
    total: int
    no_website: int
    with_social: int
    with_phone: int


class StatsOut(BaseModel):
    total: int
    no_website: int
    with_social: int
    with_phone: int
    demos: int
    by_status: dict[str, int]
    latest_job: "ParseJobOut | None" = None


class ParseRequest(BaseModel):
    source: Literal[
        "demo",
        "google",
        "twogis",
        "yandex",
        "yandex_web",
        "osm",
        "scraper",
        "vk",
        "zoon",
    ] = "demo"
    city: str = "Москва"
    categories: list[str] = Field(default_factory=list)
    query: str | None = None
    limit: int = 30
    only_no_website: bool = False
    enrich: bool = False
    radius: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class ParseJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    status: str
    params: dict = Field(default_factory=dict)
    total_found: int = 0
    total_saved: int = 0
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class DemoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    title: str
    html: str
    message: str
    published: bool
    public_url: str = ""
    created_at: datetime
    updated_at: datetime


class DemoUpdate(BaseModel):
    html: str | None = None
    message: str | None = None
    published: bool | None = None


class OutreachOut(BaseModel):
    message: str
    demo_url: str | None = None
