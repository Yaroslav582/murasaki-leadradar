from __future__ import annotations

from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.services.telegram_growth import (
    BLOG_TOPICS,
    FALLBACK_BLOG_POSTS,
    generate_ai_blog_post,
    get_published_blog_history,
)


@pytest.mark.asyncio
async def test_fallback_blog_posts_library() -> None:
    """Verify that fallback library has 15 distinct, well-formed posts with no duplicate IDs."""
    assert len(FALLBACK_BLOG_POSTS) >= 15
    assert len(BLOG_TOPICS) >= 15

    ids = [p["id"] for p in FALLBACK_BLOG_POSTS]
    assert len(ids) == len(set(ids)), "All fallback IDs must be unique"

    titles = [p["title"] for p in FALLBACK_BLOG_POSTS]
    assert len(titles) == len(set(titles)), "All fallback titles must be unique"

    for post in FALLBACK_BLOG_POSTS:
        assert len(post["title"]) > 10
        assert len(post["text"]) > 200
        assert "{portfolio}" in post["text"]
        assert "@loves_kyni" in post["text"]


@pytest.mark.asyncio
async def test_anti_duplicate_blog_generation_fallbacks() -> None:
    """When AI is unavailable, consecutive calls must rotate through distinct fallback posts."""
    with patch("app.services.telegram_growth.ask_ai", side_effect=Exception("AI service simulated offline")):
        generated_titles = []
        for _ in range(5):
            title, text = await generate_ai_blog_post()
            assert title
            assert text
            assert "@loves_kyni" in text
            generated_titles.append(title)

        # All 5 generated titles must be completely distinct
        assert len(generated_titles) == len(set(generated_titles)), f"Generated duplicates: {generated_titles}"

        # History should contain at least 5 entries
        history = await get_published_blog_history()
        assert len(history) >= 5


@pytest.mark.asyncio
async def test_anti_duplicate_blog_generation_ai() -> None:
    """When AI is available, generated posts are recorded in history and have titles."""
    counter = 0

    async def mock_ask_ai(*args, **kwargs):
        nonlocal counter
        counter += 1
        return (
            f"**💡 Уникальный AI-пост #{counter}: Секреты конверсии**\n\n"
            f"Практический контент для бизнеса #{counter}.\n\n"
            f"• Пункт 1: Увеличиваем продажи на 30%\n"
            f"• Пункт 2: Автоматизируем заявки\n\n"
            f"Портфолио: https://murasaki-portfolio.vercel.app/\n"
            f"Консультация: @loves_kyni"
        )

    with patch("app.services.telegram_growth.ask_ai", side_effect=mock_ask_ai):
        titles = []
        for _ in range(3):
            title, text = await generate_ai_blog_post()
            assert title
            assert text
            titles.append(title)

        assert len(titles) == len(set(titles))


@pytest.mark.asyncio
async def test_blog_api_endpoints(client: AsyncClient) -> None:
    """Verify /api/growth/blog/status and /api/growth/blog/generate-preview endpoints."""
    # 1. Status
    res = await client.get("/api/growth/blog/status")
    assert res.status_code == 200
    data = res.json()
    assert "channel_id" in data
    assert "topics" in data
    assert len(data["topics"]) >= 15

    # 2. Generate preview (with mocked AI)
    with patch("app.services.telegram_growth.ask_ai", side_effect=Exception("Offline")):
        res = await client.post("/api/growth/blog/generate-preview", json={})
        assert res.status_code == 200
        preview = res.json()
        assert "title" in preview
        assert "text" in preview
        assert len(preview["text"]) > 100
        assert "@loves_kyni" in preview["text"]
