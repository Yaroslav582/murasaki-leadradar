from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_secret_fallback(key: str, default: str | None = None) -> str | None:
    """Reads a configuration key from environment, or from Render Secret Files (/etc/secrets/<key>)."""
    import os
    val = os.getenv(key)
    if val and str(val).strip():
        return str(val).strip()
    for folder in [Path("/etc/secrets"), BASE_DIR, DATA_DIR, Path("/var/secrets")]:
        candidate = folder / key
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    return content
            except Exception:
                pass
    return default


DEFAULT_TEXT_MODELS_CHAIN = (
    "groq:openai/gpt-oss-120b,"
    "groq:qwen/qwen3.8-27b,"
    "openrouter:baidu/ernie-5.5-flash-preview:free,"
    "openrouter:nvidia/nemotron-3.5-lightning:free,"
    "openrouter:nvidia/nemotron-3-ultra:free,"
    "openrouter:cohere/north-mini-code:free,"
    "groq:openai/gpt-oss-20b,"
    "openrouter:perplexity/decider-v1.3:free,"
    "gemini:gemini-3.8-flash,"
    "gemini:gemini-3.6-flash,"
    "gemini:gemini-4-hydrogen,"
    "gemini:gemini-3.5-flash-lite"
)

DEFAULT_VISION_MODELS_CHAIN = (
    "openrouter:nvidia/nemotron-3.5-super-vl:free,"
    "openrouter:inclusionai/ling-3.2-flash:free,"
    "openrouter:thinkingmachines/inkling-2-small:free,"
    "gemini:gemini-3.5-flash-lite,"
    "gemini:gemini-3.8-flash"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LeadRadar"
    debug: bool = False

    database_url: str | None = None
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_db_password: str | None = None
    supabase_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    use_celery: bool = False
    seed_on_start: bool = True

    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "https://frontend-mocha-three-gfa8fzsldf.vercel.app,"
        "https://murasaki-portfolio.vercel.app,"
        "https://web.telegram.org"
    )
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

    # AI Multi-Provider Router (.env)
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    mxr_api_key: str | None = None
    mxr_base_url: str | None = "https://mxr.one/v1"
    ai_proxy_url: str | None = None
    max_daily_llm_calls: int = 400
    text_models_chain: str = DEFAULT_TEXT_MODELS_CHAIN
    vision_models_chain: str = DEFAULT_VISION_MODELS_CHAIN

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
    tgstat_token: str | None = None
    telegram_bot_token: str | None = "9286221746:AAFZapvWPAsJS1llwaydBUiyngF3RPlVyRI"
    telegram_bot_username: str | None = "murasaki_radar_1438_bot"
    web_app_url: str = "https://frontend-mocha-three-gfa8fzsldf.vercel.app"
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_phone: str | None = None
    telegram_session_string: str | None = None
    telegram_session_name: str = "leadradar_user"
    telegram_owner_id: int | None = 7585665607
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

    # Credits pricing
    credits_per_demo: int = 5
    credits_per_parse_50: int = 2
    credits_per_outreach: int = 1
    credits_per_warmup_day: int = 2
    default_credits: int = 50
    referral_bonus_percent: int = 15

    # Warmup & Outreach settings
    warmup_trusted_channels: str = "@telegram,@durov,@thebell_io,@rbc_news,@ria_novosti"
    warmup_max_daily_actions: int = 50
    outreach_enabled: bool = False
    outreach_session_string: str | None = None
    outreach_work_hours_start: int = 11
    outreach_work_hours_end: int = 18
    outreach_daily_limit: int = 15
    outreach_min_delay_min: int = 15
    outreach_max_delay_min: int = 40
    outreach_target_queries: str = "Салон красоты Новороссийск,Автосервис Новороссийск,Кофейня Краснодар"
    outreach_min_delay: int = 180
    outreach_max_delay: int = 600
    # Cold DMs a single account may send per day (up to 15/day).
    outreach_account_daily_limit: int = 15
    # Flat short cooldown (minutes) after temporary PEER_FLOOD when @SpamBot is clean.
    outreach_peer_flood_cooldown_min: int = 15
    # How often a genuinely blocked account is re-checked via @SpamBot.
    outreach_peer_flood_probe_hours: int = 6

    # AI Auto-Blogger for Telegram Channel
    channel_blog_enabled: bool = True
    channel_blog_chat_id: str = "@Murasaki_website"
    channel_blog_interval_hours: int = 24
    channel_blog_last_post_at: str | None = None
    channel_blog_next_post_at: str | None = None

    def model_post_init(self, __context: object) -> None:
        super().model_post_init(__context)
        if not self.gemini_api_key:
            self.gemini_api_key = read_secret_fallback("GEMINI_API_KEY")
        if not self.groq_api_key:
            self.groq_api_key = read_secret_fallback("GROQ_API_KEY")
        if not self.openrouter_api_key:
            self.openrouter_api_key = read_secret_fallback("OPENROUTER_API_KEY")
        if not self.mxr_api_key:
            self.mxr_api_key = read_secret_fallback("MXR_API_KEY")
        if not self.text_models_chain:
            self.text_models_chain = read_secret_fallback("TEXT_MODELS_CHAIN", DEFAULT_TEXT_MODELS_CHAIN)
        if not self.vision_models_chain:
            self.vision_models_chain = read_secret_fallback("VISION_MODELS_CHAIN", DEFAULT_VISION_MODELS_CHAIN)
        if not self.database_url:
            self.database_url = read_secret_fallback("DATABASE_URL")
        max_calls = read_secret_fallback("MAX_DAILY_LLM_CALLS")
        if max_calls and str(max_calls).strip().isdigit():
            self.max_daily_llm_calls = int(str(max_calls).strip())
        base_url = read_secret_fallback("PUBLIC_BASE_URL", self.public_base_url)
        if base_url and str(base_url).strip():
            url_str = str(base_url).strip().rstrip("/")
            if not url_str.startswith(("http://", "https://")):
                url_str = f"https://{url_str}"
            self.public_base_url = url_str
        else:
            self.public_base_url = "http://127.0.0.1:8000"

    @property
    def telegram_keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.telegram_keywords.split(",") if k.strip()]

    @property
    def telegram_stop_words_list(self) -> list[str]:
        return [w.strip().lower() for w in self.telegram_stop_words.split(",") if w.strip()]

    @property
    def warmup_channels_list(self) -> list[str]:
        return [c.strip() for c in self.warmup_trusted_channels.split(",") if c.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def user_agent_list(self) -> list[str]:
        return [agent.strip() for agent in self.user_agents.split("|") if agent.strip()]

    def get_database_url(self) -> str:
        import os

        # 1. Direct DATABASE_URL or SUPABASE_DATABASE_URL
        raw = (
            self.database_url
            or self.supabase_database_url
            or os.getenv("DATABASE_URL")
            or os.getenv("SUPABASE_DATABASE_URL")
        )
        if raw and str(raw).strip():
            return str(raw).strip()

        # 2. Derive from SUPABASE_URL + password if provided
        s_url = self.supabase_url or os.getenv("SUPABASE_URL")
        s_pwd = (
            self.supabase_db_password
            or os.getenv("SUPABASE_DB_PASSWORD")
            or os.getenv("SUPABASE_PASSWORD")
        )
        if s_url and s_pwd:
            # Extract ref, e.g. https://xyz.supabase.co -> xyz
            ref = s_url.replace("https://", "").replace("http://", "").split(".")[0].strip()
            region = os.getenv("SUPABASE_REGION", "eu-west-1")
            return f"postgresql+asyncpg://postgres.{ref}:{s_pwd.strip()}@aws-0-{region}.pooler.supabase.com:6543/postgres?sslmode=require"

        # 3. Check production
        is_prod = bool(os.getenv("RENDER") or os.getenv("ENVIRONMENT") == "production")
        if is_prod:
            import logging
            logging.getLogger("app.config").warning(
                "DATABASE_URL not set in Render Environment. Using SQLite fallback until Supabase URL is added."
            )

        # 4. Fallback database
        return f"sqlite+aiosqlite:///{(DATA_DIR / 'parser.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
