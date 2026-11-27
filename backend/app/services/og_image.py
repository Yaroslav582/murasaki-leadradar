"""Dynamic 1200x630 OpenGraph preview card generator for demo landings."""
from __future__ import annotations

import hashlib
import io
import os
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.services.brand_color import _hex_to_rgb, fallback_brand_color

FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"
OG_CACHE_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "og"

# Bounded in-memory LRU cache to avoid redrawing identical previews on Telegram bot scrapes
_OG_MEMORY_CACHE: OrderedDict[str, bytes] = OrderedDict()
_MAX_MEMORY_CACHE = 200


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[Path] = []
    if bold:
        candidates.extend([
            FONTS_DIR / "DejaVuSans-Bold.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
        ])
    else:
        candidates.extend([
            FONTS_DIR / "DejaVuSans.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeui.ttf"),
        ])
    for cand in candidates:
        try:
            if cand.is_file():
                return ImageFont.truetype(str(cand), size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int = 3,
) -> tuple[list[str], bool]:
    """Word-wrap text by rendered pixel width. Returns (lines, fits_completely)."""
    words = [w for w in (text or "").split() if w]
    if not words:
        return ["Демо-сайт"], True

    lines: list[str] = []
    current = ""
    for idx, word in enumerate(words):
        candidate = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), candidate, font=font)
        w_px = bbox[2] - bbox[0]
        if w_px <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
                current = word
            else:
                # Single very long word -> clip with ellipsis
                trimmed = word
                while len(trimmed) > 3 and draw.textbbox((0, 0), trimmed + "…", font=font)[2] > max_width:
                    trimmed = trimmed[:-1]
                lines.append(trimmed + "…")
                current = ""
            if len(lines) >= max_lines:
                remaining = bool(current or idx < len(words) - 1)
                return lines[:max_lines], not remaining

    if current:
        lines.append(current)
    return lines[:max_lines], len(lines) <= max_lines


def generate_demo_og_png(
    business_name: str,
    city: str = "",
    brand_color: str | None = None,
    category: str = "",
) -> bytes:
    """Render a 1200x630 dark minimalist OG preview card with brand_color glow."""
    width, height = 1200, 630
    accent_hex = (brand_color or "").strip() or fallback_brand_color(category, business_name=business_name)
    r, g, b = _hex_to_rgb(accent_hex)

    base = Image.new("RGBA", (width, height), (15, 15, 18, 255))

    # Soft radial gradient glows in brand_color (top-right and bottom-left)
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    g_draw.ellipse((680, -180, 1340, 480), fill=(r, g, b, 115))
    g_draw.ellipse((-180, 320, 440, 820), fill=(r, g, b, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=95))
    base = Image.alpha_composite(base, glow)

    # Subtle outer frame & accent bar
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(
        (28, 28, width - 28, height - 28),
        radius=28,
        outline=(r, g, b, 85),
        width=2,
    )
    draw.rounded_rectangle((84, 545, 220, 552), radius=4, fill=(r, g, b, 240))

    # Badge: Murasaki Lab
    badge_font = _load_font(22, bold=True)
    badge_text = "Murasaki Lab"
    b_box = draw.textbbox((0, 0), badge_text, font=badge_font)
    b_w = b_box[2] - b_box[0]
    b_h = b_box[3] - b_box[1]
    pill_x, pill_y = 84, 78
    pill_pad_x, pill_pad_y = 22, 12
    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + b_w + pill_pad_x * 2, pill_y + b_h + pill_pad_y * 2 + 4),
        radius=999,
        fill=(r, g, b, 48),
        outline=(r, g, b, 165),
        width=2,
    )
    draw.text((pill_x + pill_pad_x, pill_y + pill_pad_y - 2), badge_text, font=badge_font, fill=(248, 250, 252, 255))

    # Title: business_name (+ city), dynamically scaled so it never overflows
    clean_name = (business_name or "Ваш бизнес").strip()
    clean_city = (city or "").strip()
    full_title = f"{clean_name} — {clean_city}" if clean_city else clean_name

    max_text_width = width - 168
    chosen_font = _load_font(56, bold=True)
    chosen_lines: list[str] = [full_title]
    for size in (62, 54, 46, 38):
        font_try = _load_font(size, bold=True)
        lines, fits = _wrap_text_to_width(draw, full_title, font_try, max_text_width, max_lines=3)
        chosen_font = font_try
        chosen_lines = lines
        if fits:
            break

    y_cursor = 185
    line_gap = 14
    for line in chosen_lines:
        bbox = draw.textbbox((0, 0), line, font=chosen_font)
        line_h = max(36, bbox[3] - bbox[1])
        draw.text((84, y_cursor), line, font=chosen_font, fill=(255, 255, 255, 255))
        y_cursor += line_h + line_gap

    # Subtitle
    sub_font = _load_font(30, bold=False)
    subtitle_y = max(y_cursor + 18, 455)
    if subtitle_y > 490:
        subtitle_y = 485
    draw.text((84, subtitle_y), "Персональный демо-концепт сайта", font=sub_font, fill=(203, 213, 225, 255))

    # Bottom right domain/tag
    footer_font = _load_font(20, bold=False)
    draw.text((width - 280, 535), "Адаптивный лендинг", font=footer_font, fill=(148, 163, 184, 220))

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def get_cached_demo_og_png(
    demo_id: str,
    business_name: str,
    city: str = "",
    brand_color: str | None = None,
    category: str = "",
) -> bytes:
    """Return cached 1200x630 OG PNG from memory or disk, generating if needed."""
    raw_key = f"{demo_id}|{business_name}|{city}|{brand_color or ''}|{category}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

    if digest in _OG_MEMORY_CACHE:
        _OG_MEMORY_CACHE.move_to_end(digest)
        return _OG_MEMORY_CACHE[digest]

    cache_file = OG_CACHE_DIR / f"{digest}.png"
    if cache_file.is_file() and cache_file.stat().st_size > 1000:
        try:
            data = cache_file.read_bytes()
            _OG_MEMORY_CACHE[digest] = data
            if len(_OG_MEMORY_CACHE) > _MAX_MEMORY_CACHE:
                _OG_MEMORY_CACHE.popitem(last=False)
            return data
        except Exception:
            pass

    png_bytes = generate_demo_og_png(
        business_name=business_name,
        city=city,
        brand_color=brand_color,
        category=category,
    )
    _OG_MEMORY_CACHE[digest] = png_bytes
    if len(_OG_MEMORY_CACHE) > _MAX_MEMORY_CACHE:
        _OG_MEMORY_CACHE.popitem(last=False)

    if not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            OG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(png_bytes)
        except Exception:
            pass

    return png_bytes
