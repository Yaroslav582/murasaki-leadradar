"""Brand accent color extraction from Telegram avatars (in-memory) and niche fallbacks."""
from __future__ import annotations

import colorsys
import io
import logging
from typing import Any

import httpx
from PIL import Image

from app.services.media_collector import detect_subniche

logger = logging.getLogger(__name__)

SUBNICHE_BRAND_COLORS: dict[str, str] = {
    "coffee": "#8B3A2B",
    "restaurant": "#8B3A2B",
    "auto": "#D32F2F",
    "hair": "#2E6F65",
    "nails": "#2E6F65",
    "beauty": "#2E6F65",
    "flowers": "#2E6F65",
    "barber": "#8A5620",
    "dental": "#1976D2",
    "clinic": "#1976D2",
    "fitness": "#D32F2F",
    "office": "#2563EB",
}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    cleaned = (hex_color or "").strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(c * 2 for c in cleaned)
    if len(cleaned) != 6:
        return (37, 99, 235)
    try:
        return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))
    except ValueError:
        return (37, 99, 235)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )


def relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.1 relative luminance in [0.0, 1.0]."""
    r, g, b = _hex_to_rgb(hex_color)

    def _lin(ch: int) -> float:
        s = ch / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def darken_hex(hex_color: str, factor: float = 0.74) -> str:
    """Darken a HEX color by multiplying RGB channels by factor."""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(round(r * factor), round(g * factor), round(b * factor))


def ensure_contrast_brand_color(hex_color: str) -> str:
    """Darken bright accent colors by 20-30% passes until crisp for white CTA text."""
    candidate = _rgb_to_hex(*_hex_to_rgb(hex_color))
    for _ in range(4):
        if relative_luminance(candidate) <= 0.26:
            break
        candidate = darken_hex(candidate, factor=0.74)
    return candidate


def extract_brand_color_from_bytes(image_bytes: bytes) -> str | None:
    """Extract dominant saturated non-neutral brand HEX color from image bytes in RAM.

    Ignores near-white, near-black, and low-saturation grayscale pixels.
    Returns None if image is monochrome, invalid, or has no colorful accent.
    """
    if not image_bytes:
        return None
    try:
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            img = raw_img.convert("RGB")
            img.thumbnail((64, 64), Image.Resampling.BILINEAR)
            quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT).convert("RGB")
            colors = quantized.getcolors(maxcolors=64) or []
    except Exception:
        return None

    best_score = 0.0
    best_rgb: tuple[int, int, int] | None = None

    for count, (r, g, b) in colors:
        # Ignore near-white and near-black extremes
        if r > 235 and g > 235 and b > 235:
            continue
        if r < 22 and g < 22 and b < 22:
            continue

        _, sat, val = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        if val < 0.14:
            continue
        if sat < 0.20:
            continue
        if val > 0.94 and sat < 0.28:
            continue

        lum = 0.2126 * (r / 255.0) + 0.7152 * (g / 255.0) + 0.0722 * (b / 255.0)
        if lum > 0.88:
            continue

        score = float(count) * (0.4 + sat)
        if score > best_score:
            best_score = score
            best_rgb = (r, g, b)

    if best_rgb is None:
        return None

    return ensure_contrast_brand_color(_rgb_to_hex(*best_rgb))


def fallback_brand_color(
    category: str | None,
    business_name: str | None = None,
    services: list[Any] | None = None,
) -> str:
    """Return curated niche fallback accent HEX when no avatar color is available."""
    sub = detect_subniche(category, business_name=business_name, services=services)
    return SUBNICHE_BRAND_COLORS.get(sub, "#2563EB")


def build_brand_css_tokens(brand_color: str) -> dict[str, str]:
    """Build --brand-accent, --brand-accent-hover, --brand-accent-soft and foreground tokens."""
    norm = _rgb_to_hex(*_hex_to_rgb(brand_color))
    r, g, b = _hex_to_rgb(norm)
    hover = darken_hex(norm, factor=0.84)
    soft = f"rgba({r}, {g}, {b}, 0.12)"
    accent_fg = "#09090B" if relative_luminance(norm) > 0.45 else "#FFFFFF"
    return {
        "brand_accent": norm,
        "brand_accent_hover": hover,
        "brand_accent_soft": soft,
        "accent_fg": accent_fg,
    }


async def resolve_lead_brand_color(
    *,
    client: Any = None,
    peer_entity: Any = None,
    avatar_url: str | None = None,
    category: str | None = None,
    business_name: str | None = None,
    services: list[Any] | None = None,
) -> tuple[str | None, str]:
    """Download Telegram avatar in RAM (BytesIO) and extract brand HEX, with niche fallback.

    Returns ``(extracted_color_or_none, effective_brand_color)``.
    """
    img_bytes: bytes | None = None

    if client is not None and peer_entity is not None:
        try:
            buf = io.BytesIO()
            res = await client.download_profile_photo(peer_entity, file=buf)
            if res is not None and buf.tell() > 0:
                img_bytes = buf.getvalue()
        except Exception as exc:
            logger.debug("Telethon avatar RAM download skipped: %s", exc)

    if not img_bytes and avatar_url and str(avatar_url).startswith("http"):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0), follow_redirects=True) as http_client:
                resp = await http_client.get(str(avatar_url))
                if resp.status_code == 200 and resp.content:
                    ctype = (resp.headers.get("content-type") or "").lower()
                    if "image" in ctype or len(resp.content) > 512:
                        img_bytes = resp.content
        except Exception as exc:
            logger.debug("HTTP avatar RAM download skipped (%s): %s", avatar_url, exc)

    extracted = extract_brand_color_from_bytes(img_bytes) if img_bytes else None
    if extracted:
        return extracted, extracted

    return None, fallback_brand_color(category, business_name=business_name, services=services)
