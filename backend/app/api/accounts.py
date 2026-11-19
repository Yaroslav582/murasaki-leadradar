from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Proxy, TgAccount, utcnow
from app.services.account_pool import account_pool
from app.services.billing import get_or_create_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Accounts & Proxies"])


def parse_int_user_id(val: Any) -> Optional[int]:
    """Safely extracts integer Telegram user ID from string or int."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


async def resolve_owner_user_id(request: Request, session: AsyncSession) -> Optional[int]:
    """Resolves owner Telegram user ID as BigInteger / int from headers or query parameters."""
    tg_user_id = (
        request.headers.get("x-telegram-user-id")
        or request.headers.get("x-user-id")
        or request.query_params.get("user_id")
    )
    parsed = parse_int_user_id(tg_user_id)
    if parsed is not None:
        try:
            user = await get_or_create_user(session, telegram_id=parsed)
            return user.telegram_id or parsed
        except Exception as e:
            logger.warning("Error resolving user from ID %s: %s", parsed, e)
            return parsed
    return None


async def find_account(session: AsyncSession, account_id: str) -> Optional[TgAccount]:
    """Finds account by UUID primary key or by phone number (preventing 'Not Found' errors)."""
    if not account_id:
        return None
    clean_target = str(account_id).strip()

    # 1. Try by primary key UUID
    try:
        acc = await session.get(TgAccount, clean_target)
        if acc:
            return acc
    except Exception:
        pass

    # 2. Try by phone variants (+7..., 7..., etc.)
    clean_digits = "".join(ch for ch in clean_target if ch.isdigit() or ch == "+")
    stmt = select(TgAccount).where(
        (TgAccount.id == clean_target)
        | (TgAccount.phone == clean_target)
        | (TgAccount.phone == clean_digits)
        | (TgAccount.phone == ("+" + clean_digits.lstrip("+")))
        | (TgAccount.phone == clean_digits.lstrip("+"))
    )
    res = await session.execute(stmt)
    return res.scalars().first()


# Pydantic Schemas
class AccountCreate(BaseModel):
    phone: str
    user_id: Optional[int] = None
    session_string: Optional[str] = None
    device_model: str = "Samsung Galaxy S21"
    system_version: str = "SDK 30"
    app_version: str = "8.4.1"
    proxy_id: Optional[str] = None
    warmup_preset: str = "optimal"
    auto_warmup: bool = False
    auto_warmup_enabled: Optional[bool] = None


class AccountUpdate(BaseModel):
    proxy_id: Optional[str] = None
    status: Optional[str] = None
    warmup_preset: Optional[str] = None
    auto_warmup: Optional[bool] = None
    auto_warmup_enabled: Optional[bool] = None


class ProxyCreate(BaseModel):
    protocol: str = "socks5"
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class SendCodeRequest(BaseModel):
    phone: str
    proxy_id: Optional[str] = None
    device_model: str = "Samsung Galaxy S21"


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None
    proxy_id: Optional[str] = None


# == TG Accounts Endpoints ==
@router.get("/accounts")
async def list_accounts(
    request: Request,
    user_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    owner_id = await resolve_owner_user_id(request, session)
    if owner_id is None and user_id:
        owner_id = parse_int_user_id(user_id)

    stmt = select(TgAccount).order_by(TgAccount.created_at.desc())
    if owner_id is not None:
        stmt = stmt.where(
            (TgAccount.user_id == owner_id) | (TgAccount.user_id.is_(None))
        )
    res = await session.execute(stmt)
    accounts = res.scalars().all()

    result = []
    for acc in accounts:
        proxy = await session.get(Proxy, acc.proxy_id) if acc.proxy_id else None
        result.append({
            "id": acc.id,
            "user_id": acc.user_id,
            "phone": acc.phone,
            "username": acc.username,
            "device_model": acc.device_model,
            "system_version": acc.system_version,
            "app_version": acc.app_version,
            "proxy_id": acc.proxy_id,
            "proxy_info": f"{proxy.protocol}://{proxy.host}:{proxy.port}" if proxy else None,
            "status": acc.status,
            "flood_until": acc.flood_until.isoformat() if acc.flood_until else None,
            "daily_actions_count": acc.daily_actions_count,
            "warmup_level": acc.warmup_level,
            "warmup_preset": acc.warmup_preset,
            "auto_warmup": acc.auto_warmup,
            "auto_warmup_enabled": acc.auto_warmup,
            "created_at": acc.created_at.isoformat(),
        })
    return result


@router.post("/accounts")
async def create_account(
    payload: AccountCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    owner_id = await resolve_owner_user_id(request, session) or payload.user_id
    clean_phone = payload.phone.strip()

    stmt = select(TgAccount).where(
        (TgAccount.phone == clean_phone)
        | (TgAccount.phone == ("+" + clean_phone.lstrip("+")))
        | (TgAccount.phone == clean_phone.lstrip("+"))
    )
    res = await session.execute(stmt)
    acc = res.scalars().first()

    if acc:
        if owner_id is not None:
            acc.user_id = owner_id
        if payload.session_string:
            acc.session_string = payload.session_string.strip()
            acc.status = "active"
        if payload.device_model:
            acc.device_model = payload.device_model
        if payload.proxy_id:
            acc.proxy_id = payload.proxy_id
        acc.warmup_preset = payload.warmup_preset
        warmup_val = payload.auto_warmup if payload.auto_warmup_enabled is None else payload.auto_warmup_enabled
        acc.auto_warmup = warmup_val
        acc.updated_at = utcnow()
    else:
        warmup_val = payload.auto_warmup if payload.auto_warmup_enabled is None else payload.auto_warmup_enabled
        acc = TgAccount(
            user_id=owner_id,
            phone=clean_phone,
            session_string=payload.session_string.strip() if payload.session_string else None,
            device_model=payload.device_model,
            system_version=payload.system_version,
            app_version=payload.app_version,
            proxy_id=payload.proxy_id,
            warmup_preset=payload.warmup_preset,
            auto_warmup=warmup_val,
            status="active" if payload.session_string else "warming",
        )
        session.add(acc)

    await session.commit()
    await session.refresh(acc)

    if acc.session_string:
        try:
            await account_pool.register_client_from_account(acc, session)
        except Exception as e:
            logger.warning("Failed to register client in pool: %s", e)

    return {"id": acc.id, "phone": acc.phone, "status": acc.status, "user_id": acc.user_id}


@router.get("/accounts/warmup/status")
async def get_warmup_status(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Returns global and per-account auto-warmup status from Supabase."""
    stmt = select(TgAccount).order_by(TgAccount.created_at.desc())
    res = await session.execute(stmt)
    accounts = res.scalars().all()
    active_count = sum(1 for a in accounts if a.auto_warmup)
    return {
        "active_warmup_count": active_count,
        "total_accounts": len(accounts),
        "accounts": [
            {
                "id": a.id,
                "phone": a.phone,
                "status": a.status,
                "auto_warmup": a.auto_warmup,
                "auto_warmup_enabled": a.auto_warmup,
                "warmup_level": a.warmup_level,
                "warmup_preset": a.warmup_preset,
            }
            for a in accounts
        ],
    }


@router.get("/accounts/{account_id}")
async def get_account(account_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    acc = await find_account(session, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return {
        "id": acc.id,
        "phone": acc.phone,
        "username": acc.username,
        "status": acc.status,
        "warmup_level": acc.warmup_level,
        "warmup_preset": acc.warmup_preset,
        "auto_warmup": acc.auto_warmup,
        "auto_warmup_enabled": acc.auto_warmup,
        "proxy_id": acc.proxy_id,
        "daily_actions_count": acc.daily_actions_count,
        "created_at": acc.created_at.isoformat(),
    }


@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: str, payload: AccountUpdate, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    acc = await find_account(session, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    if payload.proxy_id is not None:
        acc.proxy_id = payload.proxy_id if payload.proxy_id != "" else None
    if payload.status is not None:
        acc.status = payload.status
    if payload.warmup_preset is not None:
        acc.warmup_preset = payload.warmup_preset
    if payload.auto_warmup is not None or payload.auto_warmup_enabled is not None:
        val = payload.auto_warmup if payload.auto_warmup is not None else payload.auto_warmup_enabled
        acc.auto_warmup = bool(val)
        try:
            from app.models import AppSetting
            st = await session.get(AppSetting, f"account_warmup_{acc.id}")
            if st:
                st.value = {"auto_warmup_enabled": acc.auto_warmup, "phone": acc.phone}
            else:
                session.add(AppSetting(key=f"account_warmup_{acc.id}", value={"auto_warmup_enabled": acc.auto_warmup, "phone": acc.phone}))
        except Exception as e:
            logger.debug("Failed saving account warmup to AppSetting: %s", e)

    acc.updated_at = utcnow()
    await session.commit()
    return {
        "id": acc.id,
        "phone": acc.phone,
        "status": acc.status,
        "warmup_level": acc.warmup_level,
        "auto_warmup": acc.auto_warmup,
        "auto_warmup_enabled": acc.auto_warmup,
        "warmup_preset": acc.warmup_preset,
    }


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    acc = await find_account(session, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    real_id = acc.id
    await session.delete(acc)
    await session.commit()
    return {"status": "deleted", "id": real_id}


@router.post("/accounts/{account_id}/check")
async def check_account_health(
    account_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    acc = await find_account(session, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    if not acc.session_string:
        return {
            "status": acc.status or "warming",
            "info": "Сессия Telethon еще не подключена (требуется вход по коду)",
            "user": acc.username or acc.phone,
        }

    res = await account_pool.check_account_health(session, acc)
    return res


# == Interactive Phone & 2FA Auth ==
@router.post("/accounts/auth/send-code")
async def send_auth_code(
    payload: SendCodeRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    try:
        res = await account_pool.request_sms_code(
            phone=payload.phone.strip(),
            proxy_id=payload.proxy_id,
            device_model=payload.device_model,
            session=session,
        )
        return res
    except Exception as e:
        logger.error("Failed to send code: %s", e)
        raise HTTPException(status_code=400, detail=f"Ошибка отправки кода: {str(e)}")


@router.post("/accounts/auth/verify")
async def verify_auth_code(
    payload: VerifyCodeRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        owner_id = await resolve_owner_user_id(request, session)
        res = await account_pool.verify_code(
            phone=payload.phone.strip(),
            code=payload.code.strip(),
            password=payload.password,
            session=session,
            user_id=owner_id,
        )
        return res
    except Exception as e:
        logger.error("Verification failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Ошибка подтверждения: {str(e)}")


@router.post("/accounts/import-archive")
async def import_accounts_archive(
    request: Request,
    file: UploadFile = File(...),
    proxy_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")

    try:
        owner_id = await resolve_owner_user_id(request, session)
        imported = await account_pool.import_from_zip(
            zip_bytes=content, proxy_id=proxy_id, session=session, user_id=owner_id
        )
        return {"status": "ok", "imported_count": len(imported), "accounts": imported}
    except Exception as e:
        logger.error("Import archive failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Не удалось распаковать архив: {str(e)}")


# == Proxies Endpoints ==
@router.get("/proxies")
async def list_proxies(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    stmt = select(Proxy).order_by(Proxy.created_at.desc())
    res = await session.execute(stmt)
    proxies = res.scalars().all()
    return [
        {
            "id": p.id,
            "protocol": p.protocol,
            "host": p.host,
            "port": p.port,
            "username": p.username,
            "is_alive": p.is_alive,
            "last_check": p.last_check.isoformat() if p.last_check else None,
        }
        for p in proxies
    ]


@router.post("/proxies")
async def create_proxy(
    payload: ProxyCreate, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    proxy = Proxy(
        protocol=payload.protocol.lower(),
        host=payload.host.strip(),
        port=payload.port,
        username=payload.username.strip() if payload.username else None,
        password=payload.password.strip() if payload.password else None,
    )
    session.add(proxy)
    await session.commit()
    await session.refresh(proxy)
    return {"id": proxy.id, "host": proxy.host, "port": proxy.port, "is_alive": proxy.is_alive}


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(proxy_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    proxy = await session.get(Proxy, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="Прокси не найден")
    await session.delete(proxy)
    await session.commit()
    return {"status": "deleted", "id": proxy_id}


@router.post("/proxies/{proxy_id}/check")
async def check_proxy(proxy_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    proxy = await session.get(Proxy, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="Прокси не найден")
    is_alive = await account_pool.check_proxy_health(proxy)
    await session.commit()
    return {"id": proxy.id, "is_alive": is_alive, "last_check": proxy.last_check.isoformat() if proxy.last_check else None}
