from __future__ import annotations

from app.providers.demo import DemoProvider


async def test_demo_provider_is_deterministic() -> None:
    provider = DemoProvider()
    first = await provider.search(
        city="Москва", categories=["Бьюти", "Рестораны"], query=None, limit=10
    )
    second = await provider.search(
        city="Москва", categories=["Бьюти", "Рестораны"], query=None, limit=10
    )
    assert len(first) == 10
    assert [item.name for item in first] == [item.name for item in second]
    assert all(item.city == "Москва" for item in first)
    assert all(item.source_id for item in first)
    assert any(item.website_url for item in first)
    assert any(not item.website_url for item in first)
