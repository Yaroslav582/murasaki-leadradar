import asyncio
import os
from telethon import TelegramClient
from telethon.errors import RPCError

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
SESSION_PATH = os.path.join(os.path.dirname(__file__), "data", "leadradar_user")
POST_PATH = os.path.join(os.path.dirname(__file__), "data", "next_post.txt")

CHANNEL = "Murasaki_website"

async def main():
    with open(POST_PATH, "r", encoding="utf-8") as f:
        text = f.read().strip()
    
    print(f"Connecting to Telegram with session: {SESSION_PATH}...")
    client = TelegramClient(
        SESSION_PATH,
        API_ID,
        API_HASH,
        connection_retries=10,
        retry_delay=2,
        timeout=25
    )
    
    await client.connect()
    if not await client.is_user_authorized():
        print("ERROR: User is not authorized in session!")
        return
    
    me = await client.get_me()
    print(f"Authorized as: {me.first_name} (@{me.username})")
    
    entity = await client.get_entity(CHANNEL)
    print(f"Target channel found: {entity.title} (id: {entity.id})")
    
    msg = await client.send_message(entity, text, parse_mode="md")
    print(f"SUCCESS! Message sent, id: {msg.id}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
