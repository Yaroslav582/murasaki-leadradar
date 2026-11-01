from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.api.filters import LeadFilters, apply_lead_filters, lead_filters
from app.db import get_session
from app.models import Lead
from app.schemas import STATUS_LABELS

router = APIRouter(prefix="/export", tags=["export"])

HEADERS = [
    "Название",
    "Категория",
    "Город",
    "Адрес",
    "Телефон",
    "Сайт",
    "Есть сайт",
    "Instagram",
    "Telegram",
    "WhatsApp",
    "Email",
    "Рейтинг",
    "Отзывы",
    "Статус",
    "Источник",
    "Заметки",
    "Создан",
]


def _row(lead: Lead) -> list:
    socials = lead.social_links or {}
    return [
        lead.name,
        lead.category,
        lead.city,
        lead.address,
        lead.phone or "",
        lead.website_url or "",
        "Да" if lead.has_website else "Нет",
        socials.get("instagram", ""),
        socials.get("telegram", ""),
        socials.get("whatsapp", ""),
        ", ".join(lead.emails or []),
        lead.rating or "",
        lead.reviews_count or 0,
        STATUS_LABELS.get(lead.status, lead.status),
        lead.source,
        lead.notes or "",
        lead.created_at.strftime("%d.%m.%Y %H:%M") if lead.created_at else "",
    ]


async def _fetch(session: AsyncSession, filters: LeadFilters) -> list[Lead]:
    stmt = apply_lead_filters(select(Lead), filters).limit(10_000)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("")
async def export_leads(
    fmt: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    filters: LeadFilters = Depends(lead_filters),
    session: AsyncSession = Depends(get_session),
) -> Response:
    leads = await _fetch(session, filters)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")

    if fmt == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Лиды"
        sheet.append(HEADERS)
        for lead in leads:
            sheet.append(_row(lead))
        header_fill = PatternFill("solid", fgColor="1F2937")
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
        widths = [34, 16, 16, 40, 18, 30, 10, 30, 30, 30, 26, 10, 10, 14, 12, 30, 16]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
        sheet.freeze_panes = "A2"

        buffer = io.BytesIO()
        workbook.save(buffer)
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="leads-{stamp}.xlsx"',
            },
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(HEADERS)
    for lead in leads:
        writer.writerow(_row(lead))

    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="leads-{stamp}.csv"'},
    )
