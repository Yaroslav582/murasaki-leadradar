from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True, default="")
    city: Mapped[str] = mapped_column(String(120), index=True, default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str | None] = mapped_column(String(64), index=True)
    website_url: Mapped[str | None] = mapped_column(String(500))
    has_website: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    rating: Mapped[float | None] = mapped_column(Float)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    emails: Mapped[list] = mapped_column(JSON, default=list)
    opening_hours: Mapped[list] = mapped_column(JSON, default=list)
    price_level: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40), default="demo", index=True)
    source_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    demo_id: Mapped[str | None] = mapped_column(String(36))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class DemoSite(Base):
    __tablename__ = "demo_sites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="")
    html: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(40), default="demo")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    total_saved: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TelegramChatTarget(Base):
    __tablename__ = "telegram_chat_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    chat_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(24), default="both")  # orders, promo, both
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=120)
    custom_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_post_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelegramOrder(Base):
    __tablename__ = "telegram_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    chat_id: Mapped[str] = mapped_column(String(120), index=True)
    chat_title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(32), default="telegram", index=True)  # telegram, kwork, fl
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    message_id: Mapped[int] = mapped_column(Integer, default=0)
    author_id: Mapped[str | None] = mapped_column(String(120))
    author_username: Mapped[str | None] = mapped_column(String(120))
    author_name: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(100), default="Веб-сайт")
    budget: Mapped[str | None] = mapped_column(String(120))
    response_text: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)  # pending, sent, skipped, failed
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelegramBroadcast(Base):
    __tablename__ = "telegram_broadcasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    chat_id: Mapped[str] = mapped_column(String(120), index=True)
    chat_title: Mapped[str] = mapped_column(String(255), default="")
    message_text: Mapped[str] = mapped_column(Text)
    portfolio_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="sent")  # sent, failed
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelegramCommentTarget(Base):
    """Channels targeted for AI neuro-commenting under new posts."""
    __tablename__ = "telegram_comment_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tone: Mapped[str] = mapped_column(String(64), default="expert")  # expert, friendly, witty, supportive
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    last_comment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelegramCommentLog(Base):
    """History of AI-generated comments published in channels."""
    __tablename__ = "telegram_comment_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(String(120), index=True)
    channel_title: Mapped[str] = mapped_column(String(255), default="")
    post_id: Mapped[int] = mapped_column(Integer, default=0)
    post_text: Mapped[str] = mapped_column(Text)
    comment_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="sent")  # sent, failed, simulated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelegramParsedUser(Base):
    """Parsed Telegram users for audience building & stories masslooking."""
    __tablename__ = "telegram_parsed_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    telegram_id: Mapped[int] = mapped_column(Integer, index=True)
    username: Mapped[str | None] = mapped_column(String(120), index=True)
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    source_chat: Mapped[str] = mapped_column(String(120), index=True)
    has_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_status: Mapped[str | None] = mapped_column(String(64))  # online, recently, last_week, other
    stories_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stories_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    telegram_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(120))
    first_name: Mapped[str | None] = mapped_column(String(255))
    credits_balance: Mapped[int] = mapped_column(Integer, default=50)
    referrer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    referral_code: Mapped[str | None] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    protocol: Mapped[str] = mapped_column(String(10), default="socks5")  # socks5 | http
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str | None] = mapped_column(String(255))
    password: Mapped[str | None] = mapped_column(String(255))
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TgAccount(Base):
    __tablename__ = "tg_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    username: Mapped[str | None] = mapped_column(String(120))
    session_string: Mapped[str | None] = mapped_column(Text)  # Telethon StringSession
    device_model: Mapped[str] = mapped_column(String(120), default="Samsung Galaxy S21")
    system_version: Mapped[str] = mapped_column(String(60), default="SDK 30")
    app_version: Mapped[str] = mapped_column(String(60), default="8.4.1")
    proxy_id: Mapped[str | None] = mapped_column(
        ForeignKey("proxies.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)  # active | warming | spamblock | floodwait | banned
    flood_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_actions_count: Mapped[int] = mapped_column(Integer, default=0)
    daily_actions_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warmup_level: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    warmup_preset: Mapped[str] = mapped_column(String(24), default="optimal")  # light | optimal | active
    auto_warmup: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Dialog(Base):
    __tablename__ = "dialogs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("tg_accounts.id", ondelete="CASCADE"), index=True
    )
    peer_id: Mapped[str] = mapped_column(String(120), index=True)  # telegram user/chat id
    peer_username: Mapped[str | None] = mapped_column(String(120))
    peer_name: Mapped[str | None] = mapped_column(String(255))
    lead_id: Mapped[str | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)  # new | ai_handling | manual | deal
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dialog_id: Mapped[str] = mapped_column(
        ForeignKey("dialogs.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    direction: Mapped[str] = mapped_column(String(8))  # "in" | "out"
    text: Mapped[str] = mapped_column(Text)
    tg_message_id: Mapped[int | None] = mapped_column(Integer)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # кредиты (+/-)
    type: Mapped[str] = mapped_column(String(24))  # deposit | spend | referral_bonus
    module_name: Mapped[str | None] = mapped_column(String(64))  # ai_demo | parse_leads | outreach | warmup
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

