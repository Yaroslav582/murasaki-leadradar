from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Transaction, User

logger = logging.getLogger(__name__)


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: Optional[int] = None,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    referrer_code: Optional[str] = None,
) -> User:
    """Finds existing user by telegram_id or creates a new one."""
    if telegram_id:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if user:
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            await session.commit()
            return user

    # Find first user in system if no telegram_id supplied
    stmt = select(User).limit(1)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if user:
        return user

    # Resolve referrer if provided
    referrer_id = None
    if referrer_code:
        ref_stmt = select(User).where(User.referral_code == referrer_code)
        ref_res = await session.execute(ref_stmt)
        referrer = ref_res.scalar_one_or_none()
        if referrer:
            referrer_id = referrer.id

    # Create new user
    new_user = User(
        telegram_id=telegram_id,
        username=username or "murasaki_user",
        first_name=first_name or "Murasaki LeadRadar User",
        credits_balance=settings.default_credits,
        referrer_id=referrer_id,
        referral_code=uuid.uuid4().hex[:8],
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    # Initial bonus transaction
    initial_tx = Transaction(
        user_id=new_user.id,
        amount=settings.default_credits,
        type="deposit",
        module_name="welcome_bonus",
        description="Приветственный бонус за регистрацию",
    )
    session.add(initial_tx)
    await session.commit()

    return new_user


async def check_and_spend(
    session: AsyncSession,
    user_id: str,
    amount: int,
    module_name: str,
    description: str,
) -> User:
    """Checks user credit balance and spends credits.
    Raises HTTPException(402) if balance is insufficient.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.credits_balance < amount:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Недостаточно кредитов ({user.credits_balance} cr). "
                f"Требуется: {amount} cr. Пополните баланс в разделе 'Тариф'."
            ),
        )

    user.credits_balance -= amount
    tx = Transaction(
        user_id=user.id,
        amount=-amount,
        type="spend",
        module_name=module_name,
        description=description,
    )
    session.add(tx)
    await session.commit()
    await session.refresh(user)
    logger.info("Spent %d credits for user %s (%s)", amount, user_id, module_name)
    return user


async def deposit_credits(
    session: AsyncSession,
    user_id: str,
    amount: int,
    payment_method: str = "stars",
    description: Optional[str] = None,
) -> tuple[User, int]:
    """Deposits credits and awards 15% referral bonus if user has a referrer."""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.credits_balance += amount
    desc = description or f"Пополнение через {payment_method.upper()}"
    tx = Transaction(
        user_id=user.id,
        amount=amount,
        type="deposit",
        module_name=payment_method,
        description=desc,
    )
    session.add(tx)

    bonus_awarded = 0
    if user.referrer_id:
        referrer = await session.get(User, user.referrer_id)
        if referrer:
            bonus = max(1, int(amount * (settings.referral_bonus_percent / 100.0)))
            referrer.credits_balance += bonus
            bonus_tx = Transaction(
                user_id=referrer.id,
                amount=bonus,
                type="referral_bonus",
                module_name="referral",
                description=f"Реферальный бонус 15% за пополнение от {user.username or user.first_name}",
            )
            session.add(bonus_tx)
            bonus_awarded = bonus
            logger.info("Awarded %d referral credits to %s", bonus, referrer.id)

    await session.commit()
    await session.refresh(user)
    return user, bonus_awarded
