import asyncio
import os
import random
import re
from pathlib import Path
from telethon import TelegramClient

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = str(BASE_DIR / "data" / "leadradar_user")
ENV_PATH = BASE_DIR / ".env"

async def main():
    print(f"Connecting to Telegram with session {SESSION_PATH}...")
    client = TelegramClient(
        SESSION_PATH,
        API_ID,
        API_HASH,
        connection_retries=8,
        retry_delay=2,
        timeout=25
    )
    await client.connect()
    if not await client.is_user_authorized():
        print("ERROR: User is not authorized in session!")
        return

    me = await client.get_me()
    print(f"Connected as: {me.first_name} (@{me.username})")

    botfather = await client.get_entity("BotFather")
    print(f"Found BotFather (id: {botfather.id})")

    # Cancel previous dialog
    await client.send_message(botfather, "/cancel")
    await asyncio.sleep(2)

    # Start /newbot
    print("Sending /newbot...")
    await client.send_message(botfather, "/newbot")
    await asyncio.sleep(2)

    # Bot Name
    bot_name = "Murasaki LeadRadar"
    print(f"Sending name: {bot_name}...")
    await client.send_message(botfather, bot_name)
    await asyncio.sleep(2)

    # Try usernames until success
    token = None
    final_username = None

    for attempt in range(6):
        suffix = random.randint(100, 9999)
        username = f"murasaki_radar_{suffix}_bot"
        print(f"Attempt {attempt + 1}: sending username @{username}...")
        await client.send_message(botfather, username)
        await asyncio.sleep(3)

        msgs = await client.get_messages(botfather, limit=3)
        for m in msgs:
            text = m.text or ""
            match = re.search(r"(\d{8,11}:[a-zA-Z0-9_-]{35})", text)
            if match:
                token = match.group(1)
                final_username = username
                break

        if token:
            break
        print(f"Username @{username} was probably taken or waiting, retrying...")

    if token:
        print("\n" + "=" * 50)
        print("🎉 УСПЕХ! БОТ СОЗДАН:")
        print(f"Юзернейм: @{final_username}")
        print(f"Ссылка: https://t.me/{final_username}")
        print(f"Токен: {token}")
        print("=" * 50)

        # Save to .env
        if ENV_PATH.exists():
            env_content = ENV_PATH.read_text(encoding="utf-8")
            if "TELEGRAM_BOT_TOKEN=" in env_content:
                env_content = re.sub(r"TELEGRAM_BOT_TOKEN=.*", f"TELEGRAM_BOT_TOKEN={token}", env_content)
            else:
                env_content += f"\nTELEGRAM_BOT_TOKEN={token}\n"
            ENV_PATH.write_text(env_content, encoding="utf-8")
            print("Токен сохранен в backend/.env!")
    else:
        print("Не удалось извлечь токен. Проверьте диалог с @BotFather.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
