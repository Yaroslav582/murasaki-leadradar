from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Proxy, TgAccount, utcnow
from app.services.account_pool import account_pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Accounts & Proxies"])


# Pydantic Schemas
class AccountCreate(BaseModel):
    phone: str
    session_string: Optional[str] = None
    device_model: str = "Samsung Galaxy S21"
    system_version: str = "SDK 30"
    app_version: str = "8.4.1"
    proxy_id: Optional[str] = None
    warmup_preset: str = "optimal"
    auto_warmup: bool = False


class AccountUpdate(BaseModel):
    proxy_id: Optional[str] = None
    status: Optional[str] = None
    warmup_preset: Optional[str] = None
    auto_warmup: Optional[bool] = None


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
async def list_accounts(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    stmt = select(TgAccount).order_by(TgAccount.created_at.desc())
    res = await session.execute(stmt)
    accounts = res.scalars().all()

    result = []
    for acc in accounts:
        proxy = await session.get(Proxy, acc.proxy_id) if acc.proxy_id else None
        result.append({
            "id": acc.id,
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
            "created_at": acc.created_at.isoformat(),
        })
    return result


@router.post("/accounts")
async def create_account(
    payload: AccountCreate, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    acc = TgAccount(
        phone=payload.phone.strip(),
        session_string=payload.session_string.strip() if payload.session_string else None,
        device_model=payload.device_model,
        system_version=payload.system_version,
        app_version=payload.app_version,
        proxy_id=payload.proxy_id,
        warmup_preset=payload.warmup_preset,
        auto_warmup=payload.auto_warmup,
        status="active" if payload.session_string else "warming",
    )
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return {"id": acc.id, "phone": acc.phone, "status": acc.status}


@router.get("/accounts/{account_id}")
async def get_account(account_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    acc = await session.get(TgAccount, account_id)
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
        "proxy_id": acc.proxy_id,
        "daily_actions_count": acc.daily_actions_count,
        "created_at": acc.created_at.isoformat(),
    }


@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: str, payload: AccountUpdate, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    acc = await session.get(TgAccount, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    if payload.proxy_id is not None:
        acc.proxy_id = payload.proxy_id if payload.proxy_id != "" else None
    if payload.status is not None:
        acc.status = payload.status
    if payload.warmup_preset is not None:
        acc.warmup_preset = payload.warmup_preset
    if payload.auto_warmup is not None:
        acc.auto_warmup = payload.auto_warmup

    acc.updated_at = utcnow()
    await session.commit()
    return {
        "id": acc.id,
        "phone": acc.phone,
        "status": acc.status,
        "warmup_level": acc.warmup_level,
        "auto_warmup": acc.auto_warmup,
        "warmup_preset": acc.warmup_preset,
    }


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    acc = await session.get(TgAccount, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    await session.delete(acc)
    await session.commit()
    return {"status": "deleted", "id": account_id}


@router.post("/accounts/{account_id}/check")
async def check_account_health(
    account_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    acc = await session.get(TgAccount, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

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
    payload: VerifyCodeRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    try:
        res = await account_pool.verify_code(
            phone=payload.phone.strip(),
            code=payload.code.strip(),
            password=payload.password,
            session=session,
        )
        return res
    except Exception as e:
        logger.error("Verification failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Ошибка подтверждения: {str(e)}")


@router.post("/accounts/import-archive")
async def import_accounts_archive(
    file: UploadFile = File(...),
    proxy_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")

    try:
        imported = await account_pool.import_from_zip(
            zip_bytes=content, proxy_id=proxy_id, session=session
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
