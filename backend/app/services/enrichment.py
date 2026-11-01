from __future__ import annotations

import asyncio
import re
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


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[str, str] | None:
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            return None
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            return None
        return str(response.url), response.text[:600_000]
    except Exception:
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

    page = await _fetch(client, site)
    if page is None:
        page = await _fetch(insecure_client, site)
    if page is None:
        lead.enriched_at = datetime.now(timezone.utc)
        return False

    final_url, html = page
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
