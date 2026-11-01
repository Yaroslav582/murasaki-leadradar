from __future__ import annotations

import pytest

from app.providers import get_provider
from app.providers.base import ProviderError
from app.providers.vk import VKProvider, _clean_site
from app.providers.zoon import ZoonProvider


def test_get_new_providers() -> None:
    vk = get_provider("vk")
    assert isinstance(vk, VKProvider)

    zoon = get_provider("zoon")
    assert isinstance(zoon, ZoonProvider)


def test_clean_site() -> None:
    assert _clean_site(None) is None
    assert _clean_site("") is None
    assert _clean_site("https://vk.com/myclub") is None
    assert _clean_site("https://t.me/channel") is None
    assert _clean_site("example.com") == "https://example.com"
    assert _clean_site("https://myshop.ru") == "https://myshop.ru"


@pytest.mark.asyncio
async def test_vk_missing_token_raises() -> None:
    provider = VKProvider(access_token="")
    with pytest.raises(ProviderError) as exc_info:
        await provider.search(city="Москва", categories=["Бьюти"], query=None, limit=5)
    assert "VK_ACCESS_TOKEN" in str(exc_info.value)
