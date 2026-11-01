from __future__ import annotations

from app.services.enrichment import _contact_links, extract_contacts

HTML = """
<html><body>
  <a href="https://www.instagram.com/aurora_studio/?hl=ru">Instagram</a>
  <a href="https://t.me/aurora_beauty">Telegram</a>
  <a href="https://wa.me/79991234567">WhatsApp</a>
  <a href="mailto:Hello@Aurora.ru">Почта</a>
  <a href="tel:+7 (999) 123-45-67">Позвонить</a>
  <a href="/contacts">Контакты</a>
</body></html>
"""


def test_extract_contacts() -> None:
    contacts = extract_contacts(HTML, "https://aurora.ru")
    assert contacts["social_links"]["instagram"] == "https://instagram.com/aurora_studio"
    assert contacts["social_links"]["telegram"] == "https://t.me/aurora_beauty"
    assert contacts["social_links"]["whatsapp"] == "https://wa.me/79991234567"
    assert contacts["emails"] == ["hello@aurora.ru"]
    assert contacts["phone"] == "+7 (999) 123-45-67"


def test_instagram_service_links_are_ignored() -> None:
    html = '<a href="https://instagram.com/p/Cx12/">post</a><a href="https://instagram.com/real_brand/">brand</a>'
    contacts = extract_contacts(html)
    assert contacts["social_links"]["instagram"] == "https://instagram.com/real_brand"


def test_telegram_service_links_are_ignored() -> None:
    html = '<a href="https://t.me/share/url?url=x">share</a><a href="https://t.me/my_channel">go</a>'
    contacts = extract_contacts(html)
    assert contacts["social_links"]["telegram"] == "https://t.me/my_channel"


def test_contact_links_are_absolutized() -> None:
    links = _contact_links('<a href="/contacts">Контакты</a>', "https://aurora.ru")
    assert links == ["https://aurora.ru/contacts"]
