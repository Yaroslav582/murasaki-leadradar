from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Lead
from app.providers.base import sample_user_agents

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_TEL_RE = re.compile(r"tel:([+0-9()\-\s]{7,24})", re.I)
INSTAGRAM_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{2,30})", re.I
)
TELEGRAM_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([A-Za-z0-9_+\-]{3,40})", re.I
)
WHATSAPP_RE = re.compile(
    r"(?:https?://)?(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{7,16})", re.I
)

INSTAGRAM_BLOCKLIST = {
    "p", "reel", "reels", "explore", "accounts", "stories", "tv", "share",
    "direct", "developer", "about", "legal", "privacy", "terms", "emails",
}
TELEGRAM_BLOCKLIST = {
    "joinchat", "share", "addstickers", "proxy", "s", "iv", "login", "setlanguage",
}

STUB_DOMAINS = (
    "taplink.cc", "vk.com", "vk.link", "t.me", "telegram.me", "instagram.com",
    "dikidi.net", "dikidi.ru", "yclients.com", "2gis.ru", "tilda.ws",
    "wixsite.com", "nethouse.ru", "linktr.ee", "msto.me", "ok.ru",
    "sites.google.com", "ucoz.", "blogspot.", "setup.ru",
)
VIEWPORT_RE = re.compile(r'<meta[^>]+name=["\']viewport["\']', re.I)


def audit_website(
    site_url: str,
    html: str | None = None,
    final_url: str | None = None,
    status_code: int | None = None,
    ssl_valid: bool = True,
    response_ms: int | None = None,
) -> dict:
    """Audit target website health, mobile readiness, SSL and stub/builder usage."""
    target = (final_url or site_url or "").strip().lower()
    parsed = urlparse(target if target.startswith(("http://", "https://")) else f"https://{target}")
    host = parsed.netloc.lower()

    stub_match = next((d for d in STUB_DOMAINS if d in host), None)
    is_stub = stub_match is not None
    is_https = (final_url or site_url or "").strip().lower().startswith("https://")
    is_alive = html is not None and (status_code is None or status_code < 400)
    has_viewport = bool(VIEWPORT_RE.search(html)) if html else None

    issues: list[str] = []
    if not is_alive:
        code_txt = f" (код {status_code})" if status_code else " (таймаут или ошибка соединения)"
        issues.append(f"Сайт не открывается{code_txt} — клиенты видят ошибку.")
    if is_stub:
        issues.append(f"Вместо полноценного сайта используется заглушка ({stub_match}).")
    if not is_https or not ssl_valid:
        issues.append("Отсутствует или недействителен SSL-сертификат (HTTPS) — браузер пугает клиентов.")
    if is_alive and has_viewport is False:
        issues.append("Нет мобильной адаптации (отсутствует meta viewport) — сайт неудобен на смартфоне.")
    if response_ms is not None and response_ms > 3500:
        issues.append(f"Медленная загрузка сайта ({response_ms / 1000:.1f} сек) — потеря до 40% трафика.")

    return {
        "is_alive": is_alive,
        "status_code": status_code,
        "ssl_valid": ssl_valid,
        "is_https": is_https,
        "is_stub": is_stub,
        "stub_domain": stub_match,
        "has_viewport": has_viewport,
        "response_ms": response_ms,
        "issues": issues,
        "audited_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_contacts(html: str, page_url: str = "") -> dict:
    """Extract social links, e-mails and phone numbers from a raw HTML page."""
    socials: dict[str, str] = {}
    emails: list[str] = []
    phone: str | None = None

    for handle in INSTAGRAM_RE.findall(html):
        handle = handle.strip(".")
        if handle.lower() not in INSTAGRAM_BLOCKLIST:
            socials["instagram"] = f"https://instagram.com/{handle}"
            break

    for handle in TELEGRAM_RE.findall(html):
        if handle.lower() not in TELEGRAM_BLOCKLIST:
            socials["telegram"] = f"https://t.me/{handle}"
            break

    for phone_digits in WHATSAPP_RE.findall(html):
        digits = re.sub(r"\D", "", phone_digits)
        if len(digits) >= 10:
            socials["whatsapp"] = f"https://wa.me/{digits}"
            break

    for email in EMAIL_RE.findall(html):
        email = email.strip(".").lower()
        if email.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")):
            continue
        if email not in emails:
            emails.append(email)
        if len(emails) >= 5:
            break

    tel_match = PHONE_TEL_RE.search(html)
    if tel_match:
        phone = re.sub(r"\s+", " ", tel_match.group(1)).strip()
    if not socials.get("instagram"):
        socials.pop("instagram", None)
    return {"social_links": socials, "emails": emails, "phone": phone}


def _normalize_site(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return url


def _contact_links(html: str, base_url: str) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = match.group(1)
        lowered = href.lower()
        if "contact" in lowered or "контакт" in lowered:
            absolute = urljoin(base_url, href)
            if absolute.startswith(("http://", "https://")) and absolute not in links:
                links.append(absolute)
        if len(links) >= 2:
            break
    return links


async def _fetch_with_meta(
    client: httpx.AsyncClient, url: str
) -> tuple[str | None, str | None, int | None, int]:
    t0 = time.monotonic()
    try:
        response = await client.get(url, follow_redirects=True)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if response.status_code >= 400:
            return str(response.url), None, response.status_code, elapsed_ms
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            return str(response.url), None, response.status_code, elapsed_ms
        return str(response.url), response.text[:600_000], response.status_code, elapsed_ms
    except Exception:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return None, None, None, elapsed_ms


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[str, str] | None:
    final_url, html, _status, _ms = await _fetch_with_meta(client, url)
    if final_url and html is not None:
        return final_url, html
    return None


async def enrich_lead(
    session: AsyncSession,
    lead: Lead,
    client: httpx.AsyncClient,
    insecure_client: httpx.AsyncClient,
) -> bool:
    site = _normalize_site(lead.website_url)
    if not site:
        return False

    ssl_valid = True
    final_url, html, status_code, response_ms = await _fetch_with_meta(client, site)
    if html is None:
        ssl_valid = False
        final_url_ins, html_ins, status_ins, ms_ins = await _fetch_with_meta(insecure_client, site)
        if html_ins is not None:
            final_url, html, status_code, response_ms = final_url_ins, html_ins, status_ins, ms_ins
        elif status_ins is not None:
            status_code = status_ins
            response_ms = ms_ins

    lead.site_audit = audit_website(
        site_url=site,
        html=html,
        final_url=final_url,
        status_code=status_code,
        ssl_valid=ssl_valid,
        response_ms=response_ms,
    )

    if html is None or final_url is None:
        lead.enriched_at = datetime.now(timezone.utc)
        session.add(lead)
        return False

    contacts = extract_contacts(html, final_url)

    extra_html = ""
    for link in _contact_links(html, final_url):
        child = await _fetch(client, link) or await _fetch(insecure_client, link)
        if child:
            extra_html += child[1]
            if len(extra_html) > 800_000:
                break
    if extra_html:
        extra = extract_contacts(extra_html, final_url)
        contacts["social_links"] = {**extra["social_links"], **contacts["social_links"]}
        contacts["emails"] = list(dict.fromkeys(contacts["emails"] + extra["emails"]))[:5]
        contacts["phone"] = contacts["phone"] or extra["phone"]

    socials = dict(lead.social_links or {})
    socials.update({k: v for k, v in contacts["social_links"].items() if v})
    lead.social_links = socials
    if contacts["emails"]:
        lead.emails = list(dict.fromkeys(list(lead.emails or []) + contacts["emails"]))[:5]
    if not lead.phone and contacts["phone"]:
        lead.phone = contacts["phone"]

    # Enrich photos and logo from public Telegram channel if available
    tg_url = (lead.social_links or {}).get("telegram")
    if tg_url:
        try:
            from app.services.telegram_channel_scraper import scrape_telegram_channel
            tg_data = await scrape_telegram_channel(tg_url)
            if tg_data.get("avatar_url") and not lead.logo_url:
                lead.logo_url = tg_data["avatar_url"]
            if tg_data.get("photos"):
                current_photos = list(lead.photos or [])
                for ph in tg_data["photos"]:
                    if ph not in current_photos:
                        current_photos.append(ph)
                lead.photos = current_photos[:10]
        except Exception:
            pass

    lead.enriched_at = datetime.now(timezone.utc)
    session.add(lead)
    return True


async def enrich_leads(session: AsyncSession, leads: list[Lead]) -> int:
    targets = [lead for lead in leads if _normalize_site(lead.website_url)]
    if not targets:
        return 0

    semaphore = asyncio.Semaphore(settings.enrichment_concurrency)
    headers = {"User-Agent": sample_user_agents(settings.user_agent_list)}
    proxy = settings.proxy_url or None
    enriched = 0

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout),
        headers=headers,
        proxy=proxy,
        follow_redirects=True,
    ) as client, httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout),
        headers=headers,
        proxy=proxy,
        verify=False,
        follow_redirects=True,
    ) as insecure_client:
        async def worker(lead: Lead) -> None:
            nonlocal enriched
            async with semaphore:
                try:
                    if await enrich_lead(session, lead, client, insecure_client):
                        enriched += 1
                except Exception:
                    lead.enriched_at = datetime.now(timezone.utc)
        await asyncio.gather(*(worker(lead) for lead in targets))

    await session.commit()
    return enriched
