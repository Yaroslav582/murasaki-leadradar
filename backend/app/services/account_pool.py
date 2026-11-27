from __future__ import annotations

import asyncio
import io
import json
import logging
import socket
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Proxy, TgAccount, utcnow

logger = logging.getLogger(__name__)

# In-memory storage for active Telethon login sessions awaiting SMS code / 2FA
_PENDING_LOGINS: dict[str, dict[str, Any]] = {}


def parse_proxy_tuple(proxy: Optional[Proxy]) -> Optional[dict]:
    """Converts a Proxy DB model into Telethon proxy dict or tuple."""
    if not proxy:
        return None
    proto = (proxy.protocol or "socks5").lower()
    import socks  # python-socks or PySocks if available
    proxy_type = socks.SOCKS5 if proto == "socks5" else socks.HTTP
    return {
        "proxy_type": proxy_type,
        "addr": proxy.host,
        "port": proxy.port,
        "username": proxy.username,
        "password": proxy.password,
        "rdns": True,
    }


class AccountPool:
    """Manages Telethon Telegram account pool, device spoofing, health checks,

    and seamless rotation on flood/spam limits.
    """

    def __init__(self) -> None:
        self._active_clients: dict[str, Any] = {}

    async def get_client_for_account(
        self, account: TgAccount, proxy: Optional[Proxy] = None
    ) -> Any:
        """Instantiates or retrieves cached Telethon TelegramClient for an account."""
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        if account.id in self._active_clients:
            client = self._active_clients[account.id]
            if client.is_connected():
                return client

        api_id = settings.telegram_api_id or 2040
        api_hash = settings.telegram_api_hash or "b18441a1ff607e10a989891a5462e627"

        session_arg = StringSession(account.session_string) if account.session_string else StringSession("")

        proxy_dict = None
        if proxy and proxy.is_alive:
            try:
                import socks
                ptype = socks.SOCKS5 if proxy.protocol == "socks5" else socks.HTTP
                proxy_dict = (ptype, proxy.host, proxy.port, True, proxy.username, proxy.password)
            except Exception as e:
                logger.warning("Could not setup proxy dict: %s", e)

        client = TelegramClient(
            session_arg,
            api_id,
            api_hash,
            device_model=account.device_model or "Samsung Galaxy S21",
            system_version=account.system_version or "SDK 30",
            app_version=account.app_version or "8.4.1",
            proxy=proxy_dict,
        )
        self._active_clients[account.id] = client
        return client

    def _attach_message_handler(self, client: Any, account: TgAccount) -> None:
        """Attaches @client.on(events.NewMessage) to capture incoming/outgoing PMs in DB."""
        from telethon import events

        if getattr(client, "_leadradar_handler_attached", False):
            return
        client._leadradar_handler_attached = True

        acc_id = account.id

        @client.on(events.NewMessage)
        async def _new_message_handler(event):
            try:
                # 1. Filter: private 1-on-1 chats only (ignore channels, supergroups, groups)
                if not event.is_private:
                    return

                # 2. Filter out Telegram system services & bots
                chat_id = event.chat_id
                if chat_id in (777000, 4244, 4000000):
                    return

                sender = await event.get_sender()
                peer_username = getattr(sender, "username", None) or ""
                is_bot = bool(
                    getattr(sender, "bot", False)
                    or (peer_username and peer_username.lower().endswith("bot"))
                    or (peer_username and peer_username.lower() in ("spambot", "telegram", "botfather"))
                )
                if is_bot:
                    # Strictly ignore all bots to prevent infinite auto-reply loops
                    return

                # 3. Determine direction and peer
                is_out = bool(event.out)
                direction = "out" if is_out else "in"
                peer_id = str(event.chat_id if is_out else (event.sender_id or event.chat_id))
                first_name = getattr(sender, "first_name", "") or ""
                last_name = getattr(sender, "last_name", "") or ""
                peer_name = f"{first_name} {last_name}".strip() or peer_username or peer_id
                raw_text = event.raw_text or getattr(event.message, "message", "") or ""
                if not raw_text.strip():
                    return

                # 4. Save/update Dialog and Message
                from app.db import SessionLocal
                from app.models import Dialog, Message, utcnow
                from app.services.inbox_service import inbox_service

                dialog_id = None
                auto_reply_enabled = False
                dialog_status = "new"
                has_lead = False

                async with SessionLocal() as db_session:
                    stmt = select(Dialog).where(
                        Dialog.account_id == acc_id,
                        Dialog.peer_id == peer_id,
                    )
                    res = await db_session.execute(stmt)
                    dialog = res.scalar_one_or_none()

                    if not dialog:
                        dialog = Dialog(
                            account_id=acc_id,
                            peer_id=peer_id,
                            peer_username=peer_username or None,
                            peer_name=peer_name,
                            status="manual" if is_out else "new",
                            unread_count=1 if not is_out else 0,
                            last_message_at=utcnow(),
                            ai_auto_reply_enabled=False,
                        )
                        db_session.add(dialog)
                        await db_session.flush()
                    else:
                        dialog.last_message_at = utcnow()
                        if peer_username:
                            dialog.peer_username = peer_username
                        if peer_name and not dialog.peer_name:
                            dialog.peer_name = peer_name
                        if not is_out:
                            dialog.unread_count += 1
                            dialog.next_followup_at = None
                        else:
                            # User manually replied from personal account -> disable AI auto-reply
                            dialog.status = "manual"
                            dialog.ai_auto_reply_enabled = False

                    # Save message if not already saved
                    msg_id = getattr(event, "id", None)
                    msg_stmt = select(Message).where(
                        Message.dialog_id == dialog.id,
                        Message.tg_message_id == msg_id,
                    )
                    m_res = await db_session.execute(msg_stmt)
                    if not m_res.scalar_one_or_none():
                        new_msg = Message(
                            dialog_id=dialog.id,
                            account_id=acc_id,
                            direction=direction,
                            text=raw_text,
                            tg_message_id=msg_id,
                            is_ai_generated=False,
                            created_at=utcnow(),
                        )
                        db_session.add(new_msg)

                    await db_session.commit()
                    dialog_id = dialog.id
                    auto_reply_enabled = bool(dialog.ai_auto_reply_enabled)
                    dialog_status = dialog.status
                    has_lead = bool(dialog.lead_id)

                # 5. Trigger AI auto-reply ONLY if:
                # - message is incoming (!is_out)
                # - auto-reply is explicitly enabled for this specific dialog
                # - peer is NOT a bot
                # - dialog is in 'ai_handling' status
                # - dialog has a confirmed lead linked to it
                if (
                    not is_out
                    and not is_bot
                    and auto_reply_enabled
                    and dialog_id
                    and dialog_status == "ai_handling"
                    and has_lead
                ):
                    asyncio.create_task(inbox_service.handle_incoming_auto_reply(dialog_id, raw_text))

            except Exception as e:
                logger.error("Error in NewMessage handler for account %s: %s", acc_id, e)

    async def register_client_from_account(
        self, account: TgAccount, session: Optional[AsyncSession] = None
    ) -> Any:
        """Immediately connects and attaches event listener to a newly added account."""
        proxy = None
        if account.proxy_id and session:
            proxy = await session.get(Proxy, account.proxy_id)

        try:
            client = await self.get_client_for_account(account, proxy)
            await client.connect()
            if await client.is_user_authorized():
                self._attach_message_handler(client, account)
                logger.info("Registered and attached NewMessage handler for account %s", account.phone)
            return client
        except Exception as e:
            logger.warning("Failed to register live client for account %s: %s", account.phone, e)
            return None

    async def load_all_from_db(self) -> int:
        """Loads all active/warming sessions from database on server startup,

        connects Telethon clients, and attaches NewMessage event handlers.
        """
        from app.db import SessionLocal

        loaded_count = 0
        async with SessionLocal() as session:
            stmt = select(TgAccount).where(
                TgAccount.session_string.isnot(None),
                TgAccount.status.in_(["active", "warming"]),
            )
            res = await session.execute(stmt)
            accounts = res.scalars().all()

            logger.info("Found %d saved accounts in DB to load on startup", len(accounts))

            for acc in accounts:
                try:
                    proxy = None
                    if acc.proxy_id:
                        proxy = await session.get(Proxy, acc.proxy_id)
                    client = await self.get_client_for_account(acc, proxy)
                    await client.connect()
                    if await client.is_user_authorized():
                        self._attach_message_handler(client, acc)
                        loaded_count += 1
                        logger.info("Telethon client active & listening: %s (id: %s)", acc.phone, acc.id)
                    else:
                        acc.status = "banned"
                        await session.commit()
                        logger.warning("Account %s is not authorized (marked as banned)", acc.phone)
                except Exception as e:
                    logger.warning("Could not auto-connect account %s on startup: %s", acc.phone, e)

        return loaded_count

    async def disconnect_all(self) -> None:
        """Disconnects all cached Telethon clients gracefully on server shutdown."""
        for client in list(self._active_clients.values()):
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception:
                pass
        self._active_clients.clear()

    async def reset_daily_counters_if_needed(self, session: AsyncSession) -> int:
        """Zeros per-day action counters for accounts whose counters belong to a previous day.

        Without this the counters only ever grow (warmup + outreach), so an account
        is eventually excluded from the pool forever.
        """
        now = utcnow()
        today = now.date()

        def _stale(reset_at: datetime | None) -> bool:
            if reset_at is None:
                return True
            if reset_at.tzinfo is None:
                reset_at = reset_at.replace(tzinfo=timezone.utc)
            return reset_at.astimezone(timezone.utc).date() < today

        res = await session.execute(
            select(TgAccount).where(TgAccount.session_string.isnot(None))
        )
        reset = 0
        for acc in res.scalars().all():
            changed = False
            if _stale(acc.daily_actions_reset_at):
                acc.daily_actions_count = 0
                acc.daily_actions_reset_at = now
                changed = True
            if _stale(acc.daily_outreach_reset_at):
                acc.daily_outreach_count = 0
                acc.daily_outreach_reset_at = now
                changed = True
            if changed:
                session.add(acc)
                reset += 1
        if reset:
            await session.commit()
            logger.info("Reset daily action counters for %d account(s)", reset)
        return reset

    async def get_available_account(
        self,
        session: AsyncSession,
        user_id: Optional[str] = None,
        max_daily_actions: Optional[int] = None,
        max_daily_outreach: Optional[int] = None,
    ) -> Optional[TgAccount]:
        """Finds the next ready-to-use account (active, not flooded, not exceeded daily limits)."""
        now = utcnow()
        await self.reset_daily_counters_if_needed(session)

        # Auto-restore accounts whose temporary floodwait window has already expired
        fw_res = await session.execute(
            select(TgAccount).where(
                TgAccount.status == "floodwait",
                TgAccount.flood_until.isnot(None),
            )
        )
        restored = 0
        for fw_acc in fw_res.scalars().all():
            due = fw_acc.flood_until
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due <= now:
                fw_acc.status = "active"
                fw_acc.flood_until = None
                fw_acc.updated_at = now
                session.add(fw_acc)
                restored += 1
        if restored:
            await session.commit()
            logger.info("Auto-restored %d account(s) after expired floodwait", restored)

        actions_cap = int(
            max_daily_actions
            if max_daily_actions is not None
            else settings.warmup_max_daily_actions
        )
        stmt = select(TgAccount).where(TgAccount.status.in_(["active", "warming"]))
        if max_daily_outreach is not None:
            stmt = stmt.order_by(
                TgAccount.daily_outreach_count.asc(),
                TgAccount.daily_actions_count.asc(),
                TgAccount.updated_at.asc(),
            )
        else:
            stmt = stmt.order_by(
                TgAccount.daily_actions_count.asc(), TgAccount.updated_at.asc()
            )
        if user_id:
            stmt = stmt.where(TgAccount.user_id == user_id)

        res = await session.execute(stmt)
        accounts = res.scalars().all()

        for acc in accounts:
            if acc.flood_until:
                due = acc.flood_until
                if due.tzinfo is None:
                    due = due.replace(tzinfo=timezone.utc)
                if due > now:
                    continue
            if acc.daily_actions_count >= actions_cap:
                continue
            if max_daily_outreach is not None and acc.daily_outreach_count >= int(max_daily_outreach):
                continue
            return acc

        return None

    async def mark_spam_limited(
        self, session: AsyncSession, account_id: str, hours: int = 24
    ) -> Optional[TgAccount]:
        """Parks an account that Telegram restricted (PEER_FLOOD / spam block).

        The account is excluded from ``get_available_account`` until ``flood_until``
        passes and a @SpamBot re-check reports it clean again.
        """
        acc = await session.get(TgAccount, account_id)
        if not acc:
            return None
        acc.status = "spamblock"
        acc.flood_until = utcnow() + timedelta(hours=max(1, int(hours)))
        acc.updated_at = utcnow()
        session.add(acc)
        await session.commit()
        await session.refresh(acc)
        logger.warning(
            "Account %s parked as spamblock until %s (Telegram PEER_FLOOD limit)",
            acc.phone,
            acc.flood_until,
        )
        return acc

    async def rotate_on_error(
        self, session: AsyncSession, account_id: str, exc: Exception
    ) -> TgAccount:
        """Updates account state on Telethon errors and rotates to next account."""
        now = utcnow()
        acc = await session.get(TgAccount, account_id)
        if not acc:
            raise ValueError(f"Account {account_id} not found")

        exc_name = type(exc).__name__
        logger.warning("Handling error %s on account %s (%s)", exc_name, acc.phone, acc.id)

        if "FloodWait" in exc_name or hasattr(exc, "seconds"):
            wait_sec = getattr(exc, "seconds", 3600)
            acc.status = "floodwait"
            acc.flood_until = now + timedelta(seconds=wait_sec)
            logger.info("Account %s flood-waited for %s seconds", acc.phone, wait_sec)
        elif "PeerFlood" in exc_name:
            acc.status = "floodwait"
            acc.flood_until = now + timedelta(hours=24)
            logger.info("Account %s peer-flooded for 24h", acc.phone)
        elif "UserBannedInChannel" in exc_name or "Spam" in exc_name:
            acc.status = "spamblock"
        elif "UserDeactivated" in exc_name or "AuthKeyUnregistered" in exc_name:
            acc.status = "banned"
        else:
            acc.status = "floodwait"
            acc.flood_until = now + timedelta(minutes=15)

        await session.commit()
        await session.refresh(acc)
        return acc

    async def record_action(self, session: AsyncSession, account_id: str) -> None:
        """Increments daily actions count for an account."""
        acc = await session.get(TgAccount, account_id)
        if acc:
            acc.daily_actions_count += 1
            if acc.daily_actions_reset_at is None:
                acc.daily_actions_reset_at = utcnow()
            acc.updated_at = utcnow()
            session.add(acc)
            await session.commit()

    async def record_outreach_action(self, session: AsyncSession, account_id: str) -> None:
        """Increments the dedicated cold-DM counter for an account (and the general one)."""
        acc = await session.get(TgAccount, account_id)
        if acc:
            acc.daily_actions_count += 1
            acc.daily_outreach_count += 1
            if acc.daily_actions_reset_at is None:
                acc.daily_actions_reset_at = utcnow()
            if acc.daily_outreach_reset_at is None:
                acc.daily_outreach_reset_at = utcnow()
            acc.updated_at = utcnow()
            session.add(acc)
            await session.commit()

    async def check_proxy_health(self, proxy: Proxy) -> bool:
        """Tests whether TCP connection to proxy host and port succeeds."""
        loop = asyncio.get_running_loop()
        is_alive = False

        def _test_connect():
            try:
                with socket.create_connection((proxy.host, proxy.port), timeout=5.0):
                    return True
            except Exception:
                return False

        try:
            is_alive = await loop.run_in_executor(None, _test_connect)
        except Exception as e:
            logger.warning("Proxy check failed for %s:%d: %s", proxy.host, proxy.port, e)
            is_alive = False

        proxy.is_alive = is_alive
        proxy.last_check = utcnow()
        return is_alive

    async def check_account_health(
        self, session: AsyncSession, account: TgAccount
    ) -> dict[str, Any]:
        """Checks account validity, connects via Telethon and checks status with @SpamBot."""
        proxy = None
        if account.proxy_id:
            proxy = await session.get(Proxy, account.proxy_id)

        try:
            client = await self.get_client_for_account(account, proxy)
            await client.connect()

            if not await client.is_user_authorized():
                account.status = "banned"
                await session.commit()
                return {"status": "banned", "reason": "Сессия завершена или деактивирована"}

            me = await client.get_me()
            account.username = me.username
            account.phone = me.phone or account.phone

            # Send message to @SpamBot to check limitations
            status_text = "Активен, ограничений нет"
            status = "active"
            try:
                await client.send_message("@SpamBot", "/start")
                await asyncio.sleep(2.0)
                msgs = await client.get_messages("@SpamBot", limit=1)
                if msgs and msgs[0].text:
                    resp = msgs[0].text.lower()
                    if (
                        "свободен от каких-либо ограничений" in resp
                        or "good news" in resp
                        or "no limits" in resp
                        or "free as a bird" in resp
                    ):
                        status = "active"
                    elif (
                        "к сожалению" in resp
                        or "ограничен" in resp
                        or "limit" in resp
                        or "non-contact" in resp
                        or "spam" in resp
                    ):
                        status = "spamblock"
                        status_text = "Обнаружен спам-блок по ответу @SpamBot"
            except Exception as sb_err:
                logger.info("SpamBot check skipped/failed: %s", sb_err)

            account.status = status
            if status == "active":
                account.flood_until = None
            await session.commit()
            return {"status": status, "info": status_text, "user": me.first_name}
        except Exception as err:
            logger.error("Health check error on account %s: %s", account.id, err)
            account.status = "banned" if "auth" in str(err).lower() else "floodwait"
            await session.commit()
            return {"status": account.status, "error": str(err)}

    # == Phone + 2FA Login Flow ==
    async def request_sms_code(
        self,
        phone: str,
        proxy_id: Optional[str] = None,
        device_model: str = "Samsung Galaxy S21",
        system_version: str = "SDK 30",
        app_version: str = "8.4.1",
        session: Optional[AsyncSession] = None,
    ) -> dict[str, Any]:
        """Sends verification code to the phone via Telethon."""
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        api_id = settings.telegram_api_id or 2040
        api_hash = settings.telegram_api_hash or "b18441a1ff607e10a989891a5462e627"

        proxy_dict = None
        if proxy_id and session:
            db_proxy = await session.get(Proxy, proxy_id)
            if db_proxy:
                try:
                    import socks
                    ptype = socks.SOCKS5 if db_proxy.protocol == "socks5" else socks.HTTP
                    proxy_dict = (ptype, db_proxy.host, db_proxy.port, True, db_proxy.username, db_proxy.password)
                except Exception:
                    pass

        client = TelegramClient(
            StringSession(""),
            api_id,
            api_hash,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            proxy=proxy_dict,
        )

        await client.connect()
        sent_code = await client.send_code_request(phone)

        # Store in pending logins
        _PENDING_LOGINS[phone] = {
            "client": client,
            "phone_code_hash": sent_code.phone_code_hash,
            "proxy_id": proxy_id,
            "device_model": device_model,
            "system_version": system_version,
            "app_version": app_version,
            "created_at": datetime.now(timezone.utc),
        }

        return {
            "status": "code_sent",
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
        }

    async def verify_code(
        self,
        phone: str,
        code: str,
        password: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        user_id: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Verifies received code and optional 2FA password, persists TgAccount with StringSession."""
        from telethon.errors import SessionPasswordNeededError

        pending = _PENDING_LOGINS.get(phone)
        if not pending:
            raise ValueError("Сессия авторизации не найдена или истекла. Запросите код заново.")

        client = pending["client"]
        phone_code_hash = pending["phone_code_hash"]

        int_user_id: Optional[int] = None
        if user_id is not None:
            try:
                int_user_id = int(user_id)
            except (ValueError, TypeError):
                pass

        try:
            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    return {"status": "needs_2fa", "message": "Требуется облачный пароль (2FA)"}
                await client.sign_in(password=password)

            me = await client.get_me()
            session_str = client.session.save()

            new_acc_id: Optional[str] = None
            if session:
                phone_clean = phone.strip()
                existing_acc = (
                    await session.execute(select(TgAccount).where(TgAccount.phone == phone_clean))
                ).scalars().first()

                if existing_acc:
                    new_acc = existing_acc
                    if int_user_id is not None:
                        new_acc.user_id = int_user_id
                    new_acc.username = getattr(me, "username", None) or new_acc.username
                    new_acc.session_string = session_str
                    new_acc.status = "active"
                    new_acc.device_model = pending.get("device_model") or new_acc.device_model
                    new_acc.system_version = pending.get("system_version") or new_acc.system_version
                    new_acc.app_version = pending.get("app_version") or new_acc.app_version
                    if pending.get("proxy_id"):
                        new_acc.proxy_id = pending["proxy_id"]
                    new_acc.updated_at = utcnow()
                else:
                    new_acc = TgAccount(
                        user_id=int_user_id,
                        phone=phone_clean,
                        username=getattr(me, "username", None),
                        session_string=session_str,
                        device_model=pending.get("device_model", "Samsung Galaxy S21"),
                        system_version=pending.get("system_version", "SDK 30"),
                        app_version=pending.get("app_version", "8.4.1"),
                        proxy_id=pending.get("proxy_id"),
                        status="active",
                        warmup_level=50,
                    )
                    session.add(new_acc)

                await session.commit()
                await session.refresh(new_acc)
                new_acc_id = new_acc.id
                await self.register_client_from_account(new_acc, session)

            _PENDING_LOGINS.pop(phone, None)
            return {
                "status": "success",
                "id": new_acc_id,
                "user_id": int_user_id,
                "phone": phone,
                "username": getattr(me, "username", None),
                "first_name": getattr(me, "first_name", ""),
            }
        except Exception as e:
            logger.error("Verification failed for %s: %s", phone, e)
            raise

    # == ZIP Archive Import (.session + .json) ==
    async def import_from_zip(
        self,
        zip_bytes: bytes,
        user_id: Optional[str] = None,
        proxy_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> list[dict[str, Any]]:
        """Extracts .session and .json pairs from a zip archive and imports accounts."""
        from telethon.sessions import SQLiteSession, StringSession
        from telethon import TelegramClient

        imported = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_names = zf.namelist()
            # Group by base name
            base_names = set()
            for fn in file_names:
                if fn.endswith(".json") or fn.endswith(".session"):
                    base_names.add(fn.rsplit(".", 1)[0])

            for base in base_names:
                json_path = f"{base}.json"
                session_path = f"{base}.session"

                device_model = "Samsung Galaxy S21"
                system_version = "SDK 30"
                app_version = "8.4.1"
                phone = base.split("/")[-1].replace("+", "")

                session_str = None
                if json_path in file_names:
                    try:
                        meta = json.loads(zf.read(json_path).decode("utf-8"))
                        device_model = meta.get("device_model") or meta.get("device") or device_model
                        system_version = meta.get("system_version") or meta.get("sdk") or system_version
                        app_version = meta.get("app_version") or meta.get("app") or app_version
                        phone = meta.get("phone") or phone
                        if meta.get("session_string"):
                            session_str = meta["session_string"]
                    except Exception as err:
                        logger.warning("Failed parsing json %s: %s", json_path, err)

                if not session_str and session_path in file_names:
                    session_bytes = zf.read(session_path)
                    # Check if the session file is actually a plaintext StringSession
                    try:
                        decoded_str = session_bytes.decode("utf-8").strip()
                        if len(decoded_str) > 200 and not decoded_str.startswith("SQLite format"):
                            session_str = decoded_str
                    except Exception:
                        pass
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".session", delete=False) as tmp:
                        tmp.write(session_bytes)
                        tmp_path = tmp.name

                    try:
                        api_id = settings.telegram_api_id or 2040
                        api_hash = settings.telegram_api_hash or "b18441a1ff607e10a989891a5462e627"
                        temp_client = TelegramClient(tmp_path.replace(".session", ""), api_id, api_hash)
                        await temp_client.connect()
                        if await temp_client.is_user_authorized():
                            session_str = StringSession.save(temp_client.session)
                            me = await temp_client.get_me()
                            if me and me.phone:
                                phone = me.phone
                        await temp_client.disconnect()
                    except Exception as ce:
                        logger.warning("Could not convert SQLite session %s: %s", session_path, ce)
                        # Fallback: store dummy string
                        session_str = f"sqlite_file:{base}"

                if session and session_str:
                    int_user_id: Optional[int] = None
                    if user_id is not None:
                        try:
                            int_user_id = int(user_id)
                        except (ValueError, TypeError):
                            pass

                    clean_phone = phone.strip()
                    existing_acc = (
                        await session.execute(
                            select(TgAccount).where(
                                (TgAccount.phone == clean_phone)
                                | (TgAccount.phone == ("+" + clean_phone.lstrip("+")))
                                | (TgAccount.phone == clean_phone.lstrip("+"))
                            )
                        )
                    ).scalars().first()

                    if existing_acc:
                        new_acc = existing_acc
                        if int_user_id is not None:
                            new_acc.user_id = int_user_id
                        new_acc.session_string = session_str
                        new_acc.device_model = device_model
                        new_acc.system_version = system_version
                        new_acc.app_version = app_version
                        if proxy_id:
                            new_acc.proxy_id = proxy_id
                        new_acc.status = "active"
                        new_acc.updated_at = utcnow()
                    else:
                        new_acc = TgAccount(
                            user_id=int_user_id,
                            phone=clean_phone,
                            session_string=session_str,
                            device_model=device_model,
                            system_version=system_version,
                            app_version=app_version,
                            proxy_id=proxy_id,
                            status="active",
                            warmup_level=60,
                        )
                        session.add(new_acc)

                    await session.commit()
                    await session.refresh(new_acc)
                    await self.register_client_from_account(new_acc, session)
                    imported.append({"phone": new_acc.phone, "status": "imported", "id": new_acc.id, "user_id": new_acc.user_id})

        return imported

    async def sync_dialog_history(
        self, session: AsyncSession, dialog: Any, limit: int = 25
    ) -> list[dict[str, Any]]:
        """Pulls recent message history from Telegram for a dialog."""
        from app.models import Dialog, Message, TgAccount, utcnow

        acc = await session.get(TgAccount, dialog.account_id)
        if not acc or not acc.session_string:
            return []

        try:
            client = await self.get_client_for_account(acc)
            await client.connect()
            if not await client.is_user_authorized():
                return []

            peer_val = dialog.peer_username or (int(dialog.peer_id) if str(dialog.peer_id).isdigit() else dialog.peer_id)
            entity = await client.get_entity(peer_val)
            tg_msgs = await client.get_messages(entity, limit=limit)

            synced = []
            for tm in reversed(tg_msgs):
                text_content = tm.text or getattr(tm, "message", "") or ""
                if not text_content.strip():
                    continue
                is_out = bool(tm.out)
                direction = "out" if is_out else "in"
                # Check if exists
                stmt = select(Message).where(Message.dialog_id == dialog.id, Message.tg_message_id == tm.id)
                res = await session.execute(stmt)
                existing = res.scalar_one_or_none()
                if not existing:
                    msg = Message(
                        dialog_id=dialog.id,
                        account_id=acc.id,
                        direction=direction,
                        text=text_content,
                        tg_message_id=tm.id,
                        is_ai_generated=False,
                        created_at=tm.date or utcnow(),
                    )
                    session.add(msg)
                    synced.append(msg)

            if synced:
                dialog.last_message_at = synced[-1].created_at
                await session.commit()

            return [{"id": m.id, "text": m.text, "direction": m.direction} for m in synced]
        except Exception as e:
            logger.warning("History sync failed for dialog %s: %s", dialog.id, e)
            return []

    async def resolve_phone_to_telegram(
        self, session: AsyncSession, phone: str, first_name: str = "Lead"
    ) -> dict[str, Any] | None:
        """Check if a mobile phone number is registered in Telegram via ImportContacts."""
        import re
        from telethon.tl.functions.contacts import DeleteContactsRequest, ImportContactsRequest
        from telethon.tl.types import InputPhoneContact

        digits = re.sub(r"\D", "", phone or "")
        if len(digits) < 10:
            return None
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
        normalized = f"+{digits}"

        account = await self.get_available_account(session)
        if not account:
            return None

        try:
            client = await self.get_client_for_account(account)
            await client.connect()
            if not await client.is_user_authorized():
                return None

            contact = InputPhoneContact(
                client_id=0,
                phone=normalized,
                first_name=(first_name or "Lead")[:64],
                last_name="",
            )
            res = await client(ImportContactsRequest([contact]))
            users = getattr(res, "users", []) or []
            if not users:
                return None

            tg_user = users[0]
            username = getattr(tg_user, "username", None)
            tg_id = getattr(tg_user, "id", None)
            try:
                await client(DeleteContactsRequest(id=[tg_user]))
            except Exception:
                pass

            telegram_url = f"https://t.me/{username}" if username else (f"tg://user?id={tg_id}" if tg_id else None)
            return {
                "user_id": tg_id,
                "username": username,
                "telegram_url": telegram_url,
                "phone": normalized,
            }
        except Exception as exc:
            logger.debug("Phone-to-Telegram lookup failed for %s: %s", normalized, exc)
            return None


account_pool = AccountPool()
