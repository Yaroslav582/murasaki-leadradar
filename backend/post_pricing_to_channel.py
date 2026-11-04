import asyncio
import os
import sys
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import MediaCaptionTooLongError

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = str(BASE_DIR / "data" / "leadradar_user")
PHOTO_PATH = BASE_DIR / "data" / "murasaki_pricing_banner.jpg"
POST_PATH = BASE_DIR / "data" / "pricing_post.txt"
CHANNEL = "Murasaki_website"

async def main():
    if not POST_PATH.exists() or not PHOTO_PATH.exists():
        print("ERROR: Files missing (pricing_post.txt or murasaki_pricing_banner.jpg)")
        return

    text = POST_PATH.read_text(encoding="utf-8").strip()

    print(f"Connecting to Telegram with session: {SESSION_PATH}...")
    client = TelegramClient(
        SESSION_PATH,
        API_ID,
        API_HASH,
        connection_retries=6,
        retry_delay=2,
        timeout=25
    )
    await client.connect()
    if not await client.is_user_authorized():
        print("ERROR: User is not authorized in session!")
        return

    me = await client.get_me()
    print(f"Connected as: {me.first_name} (@{me.username})")

    try:
        entity = await client.get_entity(CHANNEL)
        print(f"Found channel: {entity.title} (id: {entity.id}, username: @{entity.username})")

        print("Uploading banner and publishing post...")
        try:
            msg = await client.send_file(entity, str(PHOTO_PATH), caption=text, parse_mode="md")
            print(f"SUCCESS: Post with photo published! Message ID: {msg.id}")
            print(f"Direct link: https://t.me/{CHANNEL}/{msg.id}")
        except MediaCaptionTooLongError:
            print("Caption slightly over limit, sending photo + text message separately...")
            photo_msg = await client.send_file(entity, str(PHOTO_PATH))
            text_msg = await client.send_message(entity, text, parse_mode="md", link_preview=False)
            print(f"SUCCESS: Photo sent (ID {photo_msg.id}) & Text sent (ID {text_msg.id})")
            print(f"Direct link: https://t.me/{CHANNEL}/{text_msg.id}")
    except Exception as e:
        print("ERROR publishing to channel:", type(e).__name__, e)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
