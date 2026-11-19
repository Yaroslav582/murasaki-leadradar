from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Dialog, Message, TgAccount, utcnow
from app.services.account_pool import account_pool
from app.services.inbox_service import inbox_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dialogs (Inbox)"])


class SendMessageRequest(BaseModel):
    text: str


class DialogUpdate(BaseModel):
    status: Optional[str] = None
    ai_auto_reply_enabled: Optional[bool] = None


@router.get("/dialogs")
async def list_dialogs(
    account_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(Dialog)
    if account_id:
        stmt = stmt.where(Dialog.account_id == account_id)
    stmt = stmt.order_by(Dialog.last_message_at.desc().nullslast(), Dialog.created_at.desc())
    res = await session.execute(stmt)
    dialogs = res.scalars().all()

    result = []
    for d in dialogs:
        # Fetch last message preview
        m_stmt = (
            select(Message)
            .where(Message.dialog_id == d.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        m_res = await session.execute(m_stmt)
        last_msg = m_res.scalar_one_or_none()

        acc = await session.get(TgAccount, d.account_id)

        result.append({
            "id": d.id,
            "account_id": d.account_id,
            "account_phone": acc.phone if acc else None,
            "account_username": acc.username if acc else None,
            "peer_id": d.peer_id,
            "peer_username": d.peer_username,
            "peer_name": d.peer_name or d.peer_username or d.peer_id,
            "lead_id": d.lead_id,
            "status": d.status,
            "ai_auto_reply_enabled": getattr(d, "ai_auto_reply_enabled", False),
            "unread_count": d.unread_count,
            "last_message_at": d.last_message_at.isoformat() if d.last_message_at else None,
            "last_message_preview": last_msg.text[:80] + "..." if last_msg and len(last_msg.text) > 80 else (last_msg.text if last_msg else "Нет сообщений"),
            "last_message_direction": last_msg.direction if last_msg else None,
        })
    return result


@router.get("/dialogs/{dialog_id}")
async def get_dialog(dialog_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    dialog = await session.get(Dialog, dialog_id)
    if not dialog:
        raise HTTPException(status_code=404, detail="Диалог не найден")

    acc = await session.get(TgAccount, dialog.account_id)
    return {
        "id": dialog.id,
        "account_id": dialog.account_id,
        "account_phone": acc.phone if acc else None,
        "account_username": acc.username if acc else None,
        "peer_id": dialog.peer_id,
        "peer_username": dialog.peer_username,
        "peer_name": dialog.peer_name,
        "lead_id": dialog.lead_id,
        "status": dialog.status,
        "ai_auto_reply_enabled": getattr(dialog, "ai_auto_reply_enabled", False),
        "unread_count": dialog.unread_count,
        "last_message_at": dialog.last_message_at.isoformat() if dialog.last_message_at else None,
    }


@router.get("/dialogs/{dialog_id}/messages")
async def get_dialog_messages(
    dialog_id: str, session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    dialog = await session.get(Dialog, dialog_id)
    if not dialog:
        raise HTTPException(status_code=404, detail="Диалог не найден")

    stmt = (
        select(Message)
        .where(Message.dialog_id == dialog_id)
        .order_by(Message.created_at.asc())
    )
    res = await session.execute(stmt)
    msgs = res.scalars().all()

    # Mark unread as read
    if dialog.unread_count > 0:
        dialog.unread_count = 0
        await session.commit()

    return [
        {
            "id": m.id,
            "dialog_id": m.dialog_id,
            "direction": m.direction,
            "text": m.text,
            "is_ai_generated": m.is_ai_generated,
            "created_at": m.created_at.isoformat(),
        }
        for m in msgs
    ]


@router.post("/dialogs/{dialog_id}/messages")
async def send_message(
    dialog_id: str,
    payload: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    dialog = await session.get(Dialog, dialog_id)
    if not dialog:
        raise HTTPException(status_code=404, detail="Диалог не найден")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым")

    # Save outgoing message
    msg = Message(
        dialog_id=dialog.id,
        account_id=dialog.account_id,
        direction="out",
        text=text,
        is_ai_generated=False,
        created_at=utcnow(),
    )
    session.add(msg)
    dialog.last_message_at = utcnow()
    dialog.status = "manual"
    await session.commit()
    await session.refresh(msg)

    # Send to Telegram via account
    try:
        acc = await session.get(TgAccount, dialog.account_id)
        if acc:
            client = await account_pool.get_client_for_account(acc)
            await client.connect()
            if await client.is_user_authorized():
                peer_val = dialog.peer_username or int(dialog.peer_id) if dialog.peer_id.isdigit() else dialog.peer_id
                entity = await client.get_entity(peer_val)
                sent = await client.send_message(entity, text, parse_mode="md", link_preview=False)
                msg.tg_message_id = getattr(sent, "id", None)
                await session.commit()
    except Exception as e:
        logger.warning("Could not dispatch message to Telegram directly: %s", e)

    return {
        "id": msg.id,
        "dialog_id": msg.dialog_id,
        "direction": msg.direction,
        "text": msg.text,
        "is_ai_generated": msg.is_ai_generated,
        "created_at": msg.created_at.isoformat(),
    }


@router.patch("/dialogs/{dialog_id}")
async def update_dialog(
    dialog_id: str,
    payload: DialogUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    dialog = await session.get(Dialog, dialog_id)
    if not dialog:
        raise HTTPException(status_code=404, detail="Диалог не найден")

    if payload.status:
        dialog.status = payload.status
    if payload.ai_auto_reply_enabled is not None:
        dialog.ai_auto_reply_enabled = payload.ai_auto_reply_enabled
    dialog.updated_at = utcnow()
    await session.commit()

    return {
        "id": dialog.id,
        "status": dialog.status,
        "ai_auto_reply_enabled": dialog.ai_auto_reply_enabled,
    }


@router.post("/dialogs/{dialog_id}/sync")
async def sync_dialog_messages(
    dialog_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    dialog = await session.get(Dialog, dialog_id)
    if not dialog:
        raise HTTPException(status_code=404, detail="Диалог не найден")

    synced = await account_pool.sync_dialog_history(session, dialog, limit=25)
    return {"status": "ok", "dialog_id": dialog.id, "synced_count": len(synced)}


@router.post("/dialogs/{dialog_id}/ai-reply")
async def trigger_ai_reply(
    dialog_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = await inbox_service.generate_ai_reply(session, dialog_id)
        return result
    except Exception as e:
        logger.error("AI reply failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации AI ответа: {str(e)}")
