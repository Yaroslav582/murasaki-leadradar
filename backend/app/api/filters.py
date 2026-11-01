from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fastapi import Query
from sqlalchemy import Select, String, cast, func, or_

from app.models import Lead


@dataclass
class LeadFilters:
    search: str | None = None
    cities: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    only_no_website: bool = False
    only_social: bool = False
    only_phone: bool = False
    min_rating: float | None = None
    min_reviews: int | None = None
    sort: Literal["new", "rating", "reviews", "name"] = "new"


def lead_filters(
    search: str | None = Query(default=None),
    city: list[str] | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    source: list[str] | None = Query(default=None),
    only_no_website: bool = Query(default=False),
    only_social: bool = Query(default=False),
    only_phone: bool = Query(default=False),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    min_reviews: int | None = Query(default=None, ge=0),
    sort: Literal["new", "rating", "reviews", "name"] = Query(default="new"),
) -> LeadFilters:
    return LeadFilters(
        search=search,
        cities=city or [],
        categories=category or [],
        statuses=status or [],
        sources=source or [],
        only_no_website=only_no_website,
        only_social=only_social,
        only_phone=only_phone,
        min_rating=min_rating,
        min_reviews=min_reviews,
        sort=sort,
    )


def apply_lead_filters(stmt: Select, filters: LeadFilters) -> Select:
    conditions = []

    if filters.search:
        pattern = f"%{filters.search.strip()}%"
        conditions.append(
            or_(
                Lead.name.ilike(pattern),
                Lead.address.ilike(pattern),
                Lead.phone.ilike(pattern),
                Lead.category.ilike(pattern),
            )
        )
    if filters.cities:
        conditions.append(Lead.city.in_(filters.cities))
    if filters.categories:
        conditions.append(Lead.category.in_(filters.categories))
    if filters.statuses:
        conditions.append(Lead.status.in_(filters.statuses))
    if filters.sources:
        conditions.append(Lead.source.in_(filters.sources))
    if filters.only_no_website:
        conditions.append(Lead.has_website.is_(False))
    if filters.only_social:
        conditions.append(func.length(cast(Lead.social_links, String)) > 2)
    if filters.only_phone:
        conditions.append(Lead.phone.isnot(None))
        conditions.append(Lead.phone != "")
    if filters.min_rating is not None:
        conditions.append(Lead.rating >= filters.min_rating)
    if filters.min_reviews is not None:
        conditions.append(Lead.reviews_count >= filters.min_reviews)

    if conditions:
        stmt = stmt.where(*conditions)

    match filters.sort:
        case "rating":
            stmt = stmt.order_by(func.coalesce(Lead.rating, 0).desc(), Lead.reviews_count.desc())
        case "reviews":
            stmt = stmt.order_by(Lead.reviews_count.desc(), func.coalesce(Lead.rating, 0).desc())
        case "name":
            stmt = stmt.order_by(Lead.name.asc())
        case _:
            stmt = stmt.order_by(Lead.created_at.desc(), Lead.name.asc())

    return stmt
