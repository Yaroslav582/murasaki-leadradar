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

    # Enhanced Lead fields
    website_status: str = "no_website"
    lead_score: float = 3.0
    growth_points: list[str] = Field(default_factory=list)
    first_touch_offer: str = ""

    @model_validator(mode="after")
    def _fill_computed_fields(self) -> "LeadOut":
        self.status_label = STATUS_LABELS.get(self.status, self.status)

        # 1. Website status (no_website, only_social, weak_website, has_website)
        socials = self.social_links or {}
        has_social = any(bool(v) for v in socials.values()) if isinstance(socials, dict) else False
        url = (self.website_url or "").strip().lower()

        if not url:
            self.website_status = "only_social" if has_social else "no_website"
        else:
            weak_builders = (
                "tilda.ws", "wixsite.com", "taplink.cc", "ucoz.", "blogspot.",
                "wordpress.com", "sites.google.com", "timeweb.me", "nethouse.ru",
                "setup.ru", "insales.ru", "linktr.ee", "msto.me"
            )
            is_builder = any(b in url for b in weak_builders)
            is_insecure = url.startswith("http://")
            self.website_status = "weak_website" if (is_builder or is_insecure) else "has_website"

        # 2. Lead score (1.0 to 5.0)
        score = 1.0
        if self.website_status == "only_social":
            score += 2.0
        elif self.website_status in ("no_website", "weak_website"):
            score += 1.8
        else:
            score += 0.4

        if self.phone and str(self.phone).strip():
            score += 0.8

        if self.rating:
            if self.rating >= 4.5:
                score += 0.8
            elif self.rating >= 4.0:
                score += 0.5
            elif self.rating >= 3.0:
                score += 0.3

        if self.reviews_count > 10:
            score += 0.4
        elif self.reviews_count > 0:
            score += 0.2

        self.lead_score = min(5.0, round(score, 1))

        # 3. Growth points (Точки роста)
        if self.website_status == "no_website":
            self.growth_points = [
                "Теряют до 60% горячих заявок из поиска Яндекс и Google — клиенты уходят к конкурентам с сайтом.",
                "Нет формы захвата и онлайн-записи 24/7 — клиенты в нерабочее время не могут оставить заявку.",
                "Полная зависимость от одного источника на картах без собственного управляемого канала продаж.",
            ]
        elif self.website_status == "only_social":
            self.growth_points = [
                "Холодный трафик из соцсетей не конвертируется: клиентам тяжело найти каталог услуг и прайс в постах.",
                "Высокий риск блокировок и просадки охватов соцсетей без своего независимого сайта компании.",
                "Менеджеры тратят часы на ручные ответы в чате вместо автоматического приема заказов с сайта.",
            ]
        elif self.website_status == "weak_website":
            self.growth_points = [
                "Сайт на конструкторе или без SSL-сертификата (HTTPS) отпугивает клиентов предупреждением браузера.",
                "Устаревшая или медленная мобильная версия приводит к уходу до 45% посетителей со смартфонов.",
                "Отсутствие современной продающей структуры снижает конверсию переходов в реальные звонки.",
            ]
        else:
            self.growth_points = [
                "Сайт требует обновления мобильной конверсии и прямого подключения к Telegram и WhatsApp.",
                "Возможность увеличить поток заявок с существующего сайта за счет современного редизайна и оффера.",
            ]

        # 4. First touch offer (Первый контакт)
        rating_part = f"с отличным рейтингом {self.rating:.1f}★" if self.rating else "на картах"
        self.first_touch_offer = (
            f"Здравствуйте! Обратил внимание на компанию «{self.name}» в г. {self.city} {rating_part}. "
            f"Заметил, что у вас сильная репутация, но потенциальным клиентам сложно быстро изучить услуги и цены онлайн. "
            f"Мы набросали визуальный концепт современного адаптивного сайта для вас. "
            f"Посмотрите с телефона, как это может выглядеть — если откликнется, сможем запустить за пару дней. "
            f"Прислать ссылку на демо?"
        )
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


class CustomDemoCreate(BaseModel):
    html: str
    message: str | None = None
    title: str | None = None


class OutreachOut(BaseModel):
    message: str
    demo_url: str | None = None
