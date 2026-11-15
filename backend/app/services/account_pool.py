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

    async def get_available_account(
        self, session: AsyncSession, user_id: Optional[str] = None
    ) -> Optional[TgAccount]:
        """Finds the next ready-to-use account (active, not flooded, not exceeded daily limits)."""
        now = utcnow()
        stmt = (
            select(TgAccount)
            .where(TgAccount.status.in_(["active", "warming"]))
            .order_by(TgAccount.daily_actions_count.asc(), TgAccount.updated_at.asc())
        )
        if user_id:
            stmt = stmt.where(TgAccount.user_id == user_id)

        res = await session.execute(stmt)
        accounts = res.scalars().all()

        for acc in accounts:
            if acc.flood_until and acc.flood_until > now:
                continue
            if acc.daily_actions_count >= settings.warmup_max_daily_actions:
                continue
            return acc

        return None

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
            acc.updated_at = utcnow()
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
                    if "свободен от каких-либо ограничений" in resp or "good news" in resp:
                        status = "active"
                    elif "к сожалению" in resp or "ограничен" in resp or "limit" in resp:
                        status = "spamblock"
                        status_text = "Обнаружен спам-блок по ответу @SpamBot"
            except Exception as sb_err:
                logger.info("SpamBot check skipped/failed: %s", sb_err)

            account.status = status
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
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Verifies received code and optional 2FA password, persists TgAccount with StringSession."""
        from telethon.errors import SessionPasswordNeededError

        pending = _PENDING_LOGINS.get(phone)
        if not pending:
            raise ValueError("Сессия авторизации не найдена или истекла. Запросите код заново.")

        client = pending["client"]
        phone_code_hash = pending["phone_code_hash"]

        try:
            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    return {"status": "needs_2fa", "message": "Требуется облачный пароль (2FA)"}
                await client.sign_in(password=password)

            me = await client.get_me()
            session_str = client.session.save()

            if session:
                new_acc = TgAccount(
                    user_id=user_id,
                    phone=phone,
                    username=me.username,
                    session_string=session_str,
                    device_model=pending["device_model"],
                    system_version=pending["system_version"],
                    app_version=pending["app_version"],
                    proxy_id=pending["proxy_id"],
                    status="active",
                    warmup_level=50,
                )
                session.add(new_acc)
                await session.commit()
                await session.refresh(new_acc)

            _PENDING_LOGINS.pop(phone, None)
            return {
                "status": "success",
                "phone": phone,
                "username": me.username,
                "first_name": me.first_name,
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

                if json_path in file_names:
                    try:
                        meta = json.loads(zf.read(json_path).decode("utf-8"))
                        device_model = meta.get("device_model") or meta.get("device") or device_model
                        system_version = meta.get("system_version") or meta.get("sdk") or system_version
                        app_version = meta.get("app_version") or meta.get("app") or app_version
                        phone = meta.get("phone") or phone
                    except Exception as err:
                        logger.warning("Failed parsing json %s: %s", json_path, err)

                session_str = None
                if session_path in file_names:
                    # In real telethon, SQLiteSession is a binary SQLite db. We can extract it or convert
                    # to a StringSession by opening a temp client.
                    session_bytes = zf.read(session_path)
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
                    new_acc = TgAccount(
                        user_id=user_id,
                        phone=phone,
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
                    imported.append({"phone": phone, "status": "imported"})

        return imported


account_pool = AccountPool()
