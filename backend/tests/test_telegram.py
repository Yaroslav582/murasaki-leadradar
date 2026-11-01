from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_telegram_api_flow(client) -> None:
    # 1. Status check
    res = await client.get("/api/telegram/status")
    assert res.status_code == 200
    status_data = res.json()
    assert "is_connected" in status_data
    assert "keywords" in status_data

    # 2. List chats (seeds defaults on first call)
    res = await client.get("/api/telegram/chats")
    assert res.status_code == 200
    chats = res.json()
    assert len(chats) >= 3

    # 3. Simulate incoming freelance order
    res = await client.post("/api/telegram/orders/simulate")
    assert res.status_code == 200
    order = res.json()
    assert order["id"]
    assert order["status"] == "pending"
    assert order["response_text"]
    assert "примеров работ" in order["response_text"] or "работ" in order["response_text"]

    # 4. Trigger response to the order
    res = await client.post(f"/api/telegram/orders/{order['id']}/respond")
    assert res.status_code == 200
    assert res.json()["status"] == "sent"

    # 5. Trigger promo broadcast
    res = await client.post("/api/telegram/broadcasts/trigger")
    assert res.status_code == 200
    broadcast = res.json()
    assert broadcast["id"]
    assert broadcast["status"] == "sent"
    assert "портфолио" in broadcast["message_text"].lower() or "http" in broadcast["message_text"].lower()

    # 6. Update settings
    res = await client.post(
        "/api/telegram/settings",
        json={"portfolio_url": "https://murasaki-portfolio.vercel.app/", "auto_response_enabled": True},
    )
    assert res.status_code == 200

    # 7. Test LLM config endpoints
    res = await client.get("/api/llm/config")
    assert res.status_code == 200
    llm_data = res.json()
    assert "presets" in llm_data
    assert "model" in llm_data

    # Update LLM model
    res = await client.post(
        "/api/llm/config",
        json={"provider": "openai", "model": "gpt-6.1-sol", "base_url": "https://mxr.one/v1"},
    )
    assert res.status_code == 200
    assert res.json()["model"] == "gpt-6.1-sol"

    # Reset back to gpt-6-sol
    await client.post(
        "/api/llm/config",
        json={"provider": "openai", "model": "gpt-6-sol", "base_url": "https://mxr.one/v1"},
    )

    # 8. Test chat update & post now
    chat_id = chats[0]["id"]
    res = await client.patch(
        f"/api/telegram/chats/{chat_id}",
        json={"cooldown_minutes": 60, "custom_text": "Тестовый пост с портфолио {portfolio}"},
    )
    assert res.status_code == 200
    assert res.json()["cooldown_minutes"] == 60

    res = await client.post(f"/api/telegram/chats/{chat_id}/post-now")
    assert res.status_code == 200
    assert res.json()["status"] == "sent"
