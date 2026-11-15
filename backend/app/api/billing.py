from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Transaction, User
from app.services.billing import deposit_credits, get_or_create_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Billing"])


class DepositRequest(BaseModel):
    amount: int
    payment_method: str = "stars"  # stars | sbp | crypto


@router.get("/billing/balance")
async def get_balance(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    user = await get_or_create_user(session)
    return {
        "user_id": user.id,
        "credits_balance": user.credits_balance,
        "username": user.username,
        "referral_code": user.referral_code,
    }


@router.get("/billing/transactions")
async def list_transactions(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    user = await get_or_create_user(session)
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
    )
    res = await session.execute(stmt)
    txs = res.scalars().all()
    return [
        {
            "id": tx.id,
            "amount": tx.amount,
            "type": tx.type,
            "module_name": tx.module_name,
            "description": tx.description,
            "created_at": tx.created_at.isoformat(),
        }
        for tx in txs
    ]


@router.post("/billing/deposit")
async def deposit(
    payload: DepositRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма пополнения должна быть больше 0")

    user = await get_or_create_user(session)
    user, bonus = await deposit_credits(
        session=session,
        user_id=user.id,
        amount=payload.amount,
        payment_method=payload.payment_method,
    )
    return {
        "status": "success",
        "credits_balance": user.credits_balance,
        "deposited": payload.amount,
        "referral_bonus_to_partner": bonus,
    }


@router.get("/billing/referral")
async def get_referral_info(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user = await get_or_create_user(session)

    # Count invited users
    stmt_count = select(func.count()).select_from(User).where(User.referrer_id == user.id)
    invited_count = (await session.execute(stmt_count)).scalar() or 0

    # Sum earned referral bonuses
    stmt_bonus = (
        select(func.sum(Transaction.amount))
        .where(Transaction.user_id == user.id, Transaction.type == "referral_bonus")
    )
    earned_credits = (await session.execute(stmt_bonus)).scalar() or 0

    bot_username = "murasaki_radar_1438_bot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}"

    return {
        "referral_code": user.referral_code,
        "referral_link": ref_link,
        "invited_count": invited_count,
        "earned_credits": int(earned_credits),
        "bonus_percent": 15,
    }
