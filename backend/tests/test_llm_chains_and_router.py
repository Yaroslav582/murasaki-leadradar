from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import (
    DEFAULT_TEXT_MODELS_CHAIN,
    DEFAULT_VISION_MODELS_CHAIN,
    settings,
)
from app.services.ai_router import (
    AllProvidersFailedError,
    ask_ai,
    ask_ai_json,
    ask_ai_vision,
    extract_json_payload,
    get_ai_router_stats,
    get_text_models_chain,
    get_vision_models_chain,
    parse_model_chain,
    sort_business_photos,
)


def test_chain_parsing_and_order() -> None:
    """Verifies that model chains are parsed in strict order, correctly handling colons in :free tags."""
    text_chain = get_text_models_chain()
    assert len(text_chain) == 12

    expected_text = [
        ("groq", "openai/gpt-oss-120b"),
        ("groq", "qwen/qwen3.8-27b"),
        ("openrouter", "baidu/ernie-5.5-flash-preview:free"),
        ("openrouter", "nvidia/nemotron-3.5-lightning:free"),
        ("openrouter", "nvidia/nemotron-3-ultra:free"),
        ("openrouter", "cohere/north-mini-code:free"),
        ("groq", "openai/gpt-oss-20b"),
        ("openrouter", "perplexity/decider-v1.3:free"),
        ("gemini", "gemini-3.8-flash"),
        ("gemini", "gemini-3.6-flash"),
        ("gemini", "gemini-4-hydrogen"),
        ("gemini", "gemini-3.5-flash-lite"),
    ]
    assert text_chain == expected_text

    vision_chain = get_vision_models_chain()
    assert len(vision_chain) == 5

    expected_vision = [
        ("openrouter", "nvidia/nemotron-3.5-super-vl:free"),
        ("openrouter", "inclusionai/ling-3.2-flash:free"),
        ("openrouter", "thinkingmachines/inkling-2-small:free"),
        ("gemini", "gemini-3.5-flash-lite"),
        ("gemini", "gemini-3.8-flash"),
    ]
    assert vision_chain == expected_vision


def test_custom_chain_parsing() -> None:
    custom = "groq:model-a,openrouter:vendor/model-b:free,gemini:gemini-custom"
    parsed = parse_model_chain(custom)
    assert parsed == [
        ("groq", "model-a"),
        ("openrouter", "vendor/model-b:free"),
        ("gemini", "gemini-custom"),
    ]


def test_extract_json_payload() -> None:
    # 1. Bare JSON
    assert extract_json_payload('{"key": "value"}') == {"key": "value"}
    # 2. Markdown fenced JSON
    assert extract_json_payload('```json\n{"hero": "https://img.jpg"}\n```') == {"hero": "https://img.jpg"}
    # 3. JSON embedded in prose
    text = "Here is the response:\n{\"status\": \"ok\", \"count\": 42}\nHope this helps!"
    assert extract_json_payload(text) == {"status": "ok", "count": 42}
    # 4. JSON array
    assert extract_json_payload('[1, 2, 3]') == [1, 2, 3]
    # 5. Invalid string
    assert extract_json_payload("not a json at all") is None


@pytest.mark.asyncio
async def test_ask_ai_fallback_on_429_and_timeout() -> None:
    """Verifies that ask_ai tries models sequentially and skips on 429 or timeout without failing."""
    call_log: list[str] = []

    def make_mock_create(model_name: str):
        call_log.append(model_name)
        if model_name == "openai/gpt-oss-120b":
            raise RuntimeError("Error 429: Rate limit exceeded")
        elif model_name == "qwen/qwen3.8-27b":
            raise asyncio.TimeoutError("Request timed out")
        else:
            choice = MagicMock()
            choice.message.content = "Success from Ernie Flash"
            res = MagicMock()
            res.choices = [choice]
            return res

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=lambda **kwargs: make_mock_create(kwargs["model"]))

    with patch("app.services.ai_router.get_openai_client", return_value=mock_client), \
         patch("app.services.ai_router._get_provider_config", return_value={"name": "MockProv", "base_url": "http://mock", "api_key": "test_key", "extra_headers": None}):

        answer = await ask_ai("Напиши заголовок", task_type="text")
        assert answer == "Success from Ernie Flash"

        # First model failed with 429, second timed out, third succeeded
        assert call_log[:3] == [
            "openai/gpt-oss-120b",
            "qwen/qwen3.8-27b",
            "baidu/ernie-5.5-flash-preview:free",
        ]


@pytest.mark.asyncio
async def test_ask_ai_fallback_on_invalid_json() -> None:
    """Verifies that when expect_json=True, non-JSON response triggers fallback to next model."""
    call_log: list[str] = []

    def make_mock_create(model_name: str):
        call_log.append(model_name)
        choice = MagicMock()
        if model_name == "openai/gpt-oss-120b":
            choice.message.content = "Извините, вот ваш ответ текстом без json"
        else:
            choice.message.content = '{"heading": "Красивый заголовок", "cta": "Купить"}'
        res = MagicMock()
        res.choices = [choice]
        return res

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=lambda **kwargs: make_mock_create(kwargs["model"]))

    with patch("app.services.ai_router.get_openai_client", return_value=mock_client), \
         patch("app.services.ai_router._get_provider_config", return_value={"name": "MockProv", "base_url": "http://mock", "api_key": "test_key", "extra_headers": None}):

        data = await ask_ai_json("Сгенерируй JSON оффера", task_type="json")
        assert data["heading"] == "Красивый заголовок"
        assert data["cta"] == "Купить"
        # First model returned invalid JSON, so it tried the second model
        assert call_log[0] == "openai/gpt-oss-120b"
        assert call_log[1] == "qwen/qwen3.8-27b"


@pytest.mark.asyncio
async def test_sort_business_photos_vision() -> None:
    """Tests multimodal photo sorting with Vision AI models and heuristic fallback."""
    photos = [
        "https://example.com/exterior.jpg",
        "https://example.com/interior.jpg",
        "https://example.com/bad_blur.jpg",
        "https://example.com/logo.jpg",
    ]

    # 1. Vision AI succeeds
    mock_vision_json = (
        '{"hero": "https://example.com/exterior.jpg", '
        '"gallery": ["https://example.com/interior.jpg"], '
        '"logo": "https://example.com/logo.jpg", '
        '"rejected": ["https://example.com/bad_blur.jpg"]}'
    )
    with patch("app.services.ai_router.ask_ai_vision", new_callable=AsyncMock) as mock_vis:
        mock_vis.return_value = mock_vision_json
        sorted_res = await sort_business_photos(photos, business_category="Автосервис", business_name="Turbo")
        assert sorted_res["hero"] == "https://example.com/exterior.jpg"
        assert "https://example.com/interior.jpg" in sorted_res["gallery"]
        assert sorted_res["logo"] == "https://example.com/logo.jpg"
        assert "https://example.com/bad_blur.jpg" in sorted_res["rejected"]

    # 2. Vision AI fails (offline/error) -> Heuristic fallback works seamlessly
    with patch("app.services.ai_router.ask_ai_vision", side_effect=Exception("Vision offline")):
        fallback_res = await sort_business_photos(photos, business_category="Автосервис", business_name="Turbo")
        assert fallback_res["hero"] == "https://example.com/exterior.jpg"
        assert len(fallback_res["gallery"]) >= 1


def test_router_stats_endpoint() -> None:
    stats = get_ai_router_stats()
    assert "providers" in stats
    assert "text_models_chain" in stats
    assert "vision_models_chain" in stats
    assert len(stats["text_models_chain"]) == 12
    assert len(stats["vision_models_chain"]) == 5

