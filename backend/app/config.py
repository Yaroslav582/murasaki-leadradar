from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LeadRadar"
    debug: bool = False

    database_url: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'parser.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    use_celery: bool = False
    seed_on_start: bool = True

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    public_base_url: str = "http://127.0.0.1:8000"

    google_places_api_key: str | None = None
    twogis_api_key: str | None = None
    yandex_maps_api_key: str | None = None
    vk_access_token: str | None = None
    proxy_url: str | None = None

    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-latest"

    http_timeout: float = 12.0
    enrichment_concurrency: int = 8
    max_parse_limit: int = 500
    user_agents: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36|"
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )

    # Telegram Freelance Radar & Outreach Automation
    telegram_bot_token: str | None = "9286221746:AAFZapvWPAsJS1llwaydBUiyngF3RPlVyRI"
    telegram_bot_username: str | None = "murasaki_radar_1438_bot"
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_phone: str | None = None
    telegram_session_name: str = "leadradar_user"
    telegram_owner_id: int | None = None
    telegram_portfolio_url: str = "https://murasaki-portfolio.vercel.app/"
    telegram_auto_response_delay_min: int = 480  # 8 min
    telegram_auto_response_delay_max: int = 780  # 13 min
    telegram_broadcast_interval_minutes: int = 120  # 2 hours
    telegram_auto_response_enabled: bool = True
    telegram_auto_posting_enabled: bool = True
    telegram_working_hours_enabled: bool = True
    telegram_working_hours_start: str = "09:00"
    telegram_working_hours_end: str = "23:00"
    telegram_keywords: str = (
        "сайт,лендинг,веб-дизайн,дизайн сайта,верстка,tilda,тильда,"
        "разработка сайта,интернет-магазин,landing,frontend,разработчик сайтов,webflow,next.js,react"
    )
    telegram_stop_words: str = "в офис,fulltime,полный день,стажировка,500р,500 руб,1000р,бесплатно"

    @property
    def telegram_keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.telegram_keywords.split(",") if k.strip()]

    @property
    def telegram_stop_words_list(self) -> list[str]:
        return [w.strip().lower() for w in self.telegram_stop_words.split(",") if w.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def user_agent_list(self) -> list[str]:
        return [agent.strip() for agent in self.user_agents.split("|") if agent.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
