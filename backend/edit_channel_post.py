import asyncio
from pathlib import Path
from telethon import TelegramClient

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = str(BASE_DIR / "data" / "leadradar_user")
POST_PATH = BASE_DIR / "data" / "pricing_post.txt"
CHANNEL = "Murasaki_website"
MESSAGE_ID = 13

async def main():
    text = POST_PATH.read_text(encoding="utf-8").strip()

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

    try:
        entity = await client.get_entity(CHANNEL)
        print(f"Editing message {MESSAGE_ID} in channel: {entity.title}...")
        edited_msg = await client.edit_message(entity, MESSAGE_ID, text=text)
        print(f"SUCCESS: Message {MESSAGE_ID} edited successfully!")
        print(f"Direct link: https://t.me/{CHANNEL}/{MESSAGE_ID}")
    except Exception as e:
        print("ERROR editing message:", type(e).__name__, e)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
