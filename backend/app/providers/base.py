from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class PlaceResult:
    name: str
    category: str = ""
    city: str = ""
    address: str = ""
    phone: str | None = None
    website_url: str | None = None
    rating: float | None = None
    reviews_count: int = 0
    latitude: float | None = None
    longitude: float | None = None
    social_links: dict[str, str] = field(default_factory=dict)
    emails: list[str] = field(default_factory=list)
    opening_hours: list[str] = field(default_factory=list)
    price_level: int | None = None
    source: str = "demo"
    source_id: str | None = None

    @property
    def has_website(self) -> bool:
        return bool(self.website_url)


class BaseProvider:
    source: str = "base"

    async def search(
        self,
        *,
        city: str,
        categories: list[str],
        query: str | None,
        limit: int,
        latitude: float | None = None,
        longitude: float | None = None,
        radius: int | None = None,
    ) -> list[PlaceResult]:
        raise NotImplementedError


class ProviderError(RuntimeError):
    pass


def sample_user_agents(agents: list[str]) -> str:
    return random.choice(agents) if agents else "Mozilla/5.0"
