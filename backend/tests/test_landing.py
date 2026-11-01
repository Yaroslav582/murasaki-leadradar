from __future__ import annotations

from app.services.landing import (
    _extract_html,
    build_fallback_landing,
    build_outreach,
)

LEAD = {
    "name": "Студия красоты <Aurora>",
    "category": "Бьюти",
    "city": "Москва",
    "address": "Москва, ул. Тверская, 10",
    "phone": "+7 (999) 123-45-67",
    "rating": 4.8,
    "reviews_count": 124,
    "has_website": False,
    "social_links": {
        "telegram": "https://t.me/aurora",
        "whatsapp": "https://wa.me/79991234567",
    },
    "opening_hours": ["Ежедневно 10:00–21:00"],
}


def test_fallback_landing_is_complete() -> None:
    html = build_fallback_landing(LEAD)
    assert html.startswith("<!DOCTYPE html>")
    assert html.rstrip().endswith("</html>")
    assert "Услуги и цены" in html
    assert "wa.me/79991234567" in html
    assert "t.me/aurora" in html
    assert "Студия красоты &lt;Aurora&gt;" in html
    assert "<Aurora>" not in html
    assert "tailwindcss.com" in html


def test_outreach_contains_demo_link() -> None:
    message = build_outreach(LEAD, "https://example.com/demo/123")
    assert "https://example.com/demo/123" in message
    assert "в Москве" in message
    assert "студия красоты" in message
    assert "Aurora" in message


def test_extract_html_strips_markdown_and_scripts() -> None:
    raw = """```html
<!DOCTYPE html><html><head>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://evil.example/x.js"></script>
</head><body onclick="alert(1)">Привет</body><p>""" + ("Контент " * 150) + """</p></html>
```"""
    parsed = _extract_html(raw)
    assert parsed is not None
    assert "cdn.tailwindcss.com" in parsed
    assert "evil.example" not in parsed
    assert "onclick" not in parsed
    assert "```" not in parsed


def test_extract_html_rejects_garbage() -> None:
    assert _extract_html("Вот ваш сайт: пока не готов") is None
