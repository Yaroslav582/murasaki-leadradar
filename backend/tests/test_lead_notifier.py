"""
Tests for lead_notifier and Telegram bot interactive actions
"""

import pytest
from app.db import SessionLocal
from app.models import TelegramOrder, utcnow
from app.services.lead_notifier import LeadNotifier, clean_handle


def test_clean_handle():
    assert clean_handle("@ivan_client") == "ivan_client"
    assert clean_handle("https://t.me/ivan_client") == "ivan_client"
    assert clean_handle("t.me/ivan_client") == "ivan_client"
    assert clean_handle(None) == ""


def test_format_order_card_pending():
    notifier = LeadNotifier()
    order = TelegramOrder(
        id="test-order-uuid-1234",
        chat_id="@freelancetavern",
        chat_title="Freelance Tavern",
        source="telegram",
        author_username="test_customer",
        author_name="Алексей",
        raw_text="Нужен лендинг под ключ на React, бюджет 50 000 руб.",
        summary="Лендинг под ключ",
        category="Веб-сайт",
        budget="50 000 ₽",
        response_text="Здравствуйте! Готов выполнить проект...",
        status="pending",
    )

    text, markup = notifier.format_order_card(order)

    # 1. Check HTML text elements
    assert "🔥 <b>НОВЫЙ ЗАКАЗ НА РАДАРЕ</b>" in text
    assert "Веб-сайт" in text
    assert "50 000 ₽" in text
    assert "@test_customer" in text
    assert "Нужен лендинг под ключ" in text
    assert "Здравствуйте! Готов выполнить" in text

    # 2. Check inline buttons
    inline_keyboard = markup["inline_keyboard"]
    all_buttons = [btn for row in inline_keyboard for btn in row]
    btn_texts = [btn["text"] for btn in all_buttons]

    # Must contain Generation button
    assert any("Сгенерировать" in t or "Перегенерировать" in t for t in btn_texts)
    gen_btn = next(b for b in all_buttons if "gen_offer:" in b.get("callback_data", ""))
    assert gen_btn["callback_data"] == f"gen_offer:{order.id}"

    # Must contain Direct Link to PM
    pm_btn = next(b for b in all_buttons if "💬 Перейти в ЛС" in b["text"])
    assert pm_btn["url"] == "https://t.me/test_customer"

    # Must contain Auto-Reply from Account button
    reply_btn = next(b for b in all_buttons if "🚀 Автоотклик с аккаунта" in b["text"])
    assert reply_btn["callback_data"] == f"auto_reply:{order.id}"

    # Must contain Skip button
    skip_btn = next(b for b in all_buttons if "❌ Пропустить" in b["text"])
    assert skip_btn["callback_data"] == f"skip_order:{order.id}"

    # Must contain Mini App button
    mini_app_btn = next(b for b in all_buttons if "Mini App" in b["text"])
    assert "web_app" in mini_app_btn


def test_format_order_card_sent():
    notifier = LeadNotifier()
    order = TelegramOrder(
        id="test-order-sent-456",
        chat_id="@freelancetavern",
        source="telegram",
        author_username="test_customer",
        raw_text="Лендинг",
        status="sent",
    )

    text, markup = notifier.format_order_card(order, is_sent=True)
    assert "✅ <b>ОТКЛИК ОТПРАВЛЕН В ЛС</b>" in text

    all_buttons = [btn for row in markup["inline_keyboard"] for btn in row]
    btn_callbacks = [b.get("callback_data") for b in all_buttons if b.get("callback_data")]
    # Action buttons should be removed after response is sent
    assert not any("auto_reply:" in str(cb) for cb in btn_callbacks)
    assert not any("gen_offer:" in str(cb) for cb in btn_callbacks)


@pytest.mark.asyncio
async def test_subscriber_registration():
    notifier = LeadNotifier()
    test_chat_id = 987654321
    await notifier.add_subscriber(test_chat_id)

    recipients = await notifier.get_recipients()
    assert test_chat_id in recipients
