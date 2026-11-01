import asyncio
import os
import sys
from pathlib import Path
from telethon import TelegramClient

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = str(BASE_DIR / "data" / "leadradar_user")
AVATAR_PATH = BASE_DIR / "data" / "murasaki_avatar.jpg"
BOT_USERNAME = "@murasaki_radar_1438_bot"

async def main():
    if not AVATAR_PATH.exists():
        print(f"ERROR: Avatar file not found: {AVATAR_PATH}")
        return

    print(f"Connecting to Telegram with session {SESSION_PATH}...")
    client = TelegramClient(
        SESSION_PATH,
        API_ID,
        API_HASH,
        connection_retries=5,
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

    # Start /setuserpic
    print("Sending /setuserpic...")
    await client.send_message(botfather, "/setuserpic")
    await asyncio.sleep(2)

    # Send bot username
    print(f"Selecting bot {BOT_USERNAME}...")
    await client.send_message(botfather, BOT_USERNAME)
    await asyncio.sleep(2)

    # Send avatar image
    print(f"Uploading avatar image {AVATAR_PATH.name}...")
    await client.send_file(botfather, str(AVATAR_PATH))
    await asyncio.sleep(3)

    # Read latest response
    msgs = await client.get_messages(botfather, limit=2)
    for m in msgs:
        print("BotFather response:", m.text)

    await client.disconnect()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
