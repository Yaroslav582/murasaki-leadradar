import pytest
from app.db import SessionLocal
from app.models import Dialog, Message, TgAccount
from app.services.inbox_service import inbox_service


@pytest.mark.asyncio
async def test_dialog_persisted_default_auto_reply_is_false():
    async with SessionLocal() as session:
        acc = TgAccount(
            id="acc-default-test",
            phone="+1999999999",
            status="active",
        )
        session.add(acc)
        dlg = Dialog(
            id="dlg-default-test",
            account_id=acc.id,
            peer_id="12345",
            status="new",
        )
        session.add(dlg)
        await session.commit()

        refreshed = await session.get(Dialog, "dlg-default-test")
        assert refreshed.ai_auto_reply_enabled is False


@pytest.mark.asyncio
async def test_circuit_breaker_trips_after_consecutive_ai_replies():
    async with SessionLocal() as session:
        # Setup test account & dialog
        acc = TgAccount(
            id="test-acc-circuit",
            phone="+1234567890",
            status="active",
        )
        session.add(acc)

        dlg = Dialog(
            id="test-dlg-circuit",
            account_id=acc.id,
            peer_id="999888777",
            peer_username="client_user",
            status="ai_handling",
            ai_auto_reply_enabled=True,
            lead_id=None,
        )
        session.add(dlg)

        # 2 consecutive outbound AI messages
        m1 = Message(
            dialog_id=dlg.id,
            account_id=acc.id,
            direction="out",
            text="AI message 1",
            is_ai_generated=True,
        )
        m2 = Message(
            dialog_id=dlg.id,
            account_id=acc.id,
            direction="out",
            text="AI message 2",
            is_ai_generated=True,
        )
        session.add_all([m1, m2])
        await session.commit()

        # generate_ai_reply should trigger circuit breaker
        res = await inbox_service.generate_ai_reply(session, dlg.id)
        assert res["status"] == "manual"

        # Verify dialog state in DB
        refreshed = await session.get(Dialog, dlg.id)
        assert refreshed.ai_auto_reply_enabled is False
        assert refreshed.status == "manual"


@pytest.mark.asyncio
async def test_bot_peer_auto_reply_aborted():
    async with SessionLocal() as session:
        acc = TgAccount(
            id="test-acc-bot",
            phone="+1234567899",
            status="active",
        )
        session.add(acc)

        dlg = Dialog(
            id="test-dlg-bot",
            account_id=acc.id,
            peer_id="777666555",
            peer_username="my_test_bot",
            status="ai_handling",
            ai_auto_reply_enabled=True,
        )
        session.add(dlg)
        await session.commit()

        res = await inbox_service.generate_ai_reply(session, dlg.id)
        assert res["text"] == ""

        refreshed = await session.get(Dialog, dlg.id)
        assert refreshed.ai_auto_reply_enabled is False
