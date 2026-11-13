import asyncio
import os
import sys
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    UserAlreadyParticipantError,
    InviteRequestSentError,
)

# Configuration from .env
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = str(BASE_DIR / "data" / "leadradar_user")

# Target channels and chat groups for auto-joining
CHANNELS_TO_JOIN = [
    # Freelance order chats & boards
    "freelancetavern",
    "finder_vc",
    "distantsiya",
    "freelance_chat_ru",
    "forfreelance",
    "tabor_it",
    "zakazy_freelance",
    "web_freelance_jobs",
    "designer_jobs",
    "freelancefeed",
    "digital_rabota",
    "it_freelance_chat",
    "tg_bots_orders",
    "remotework_ru",
    "frilans_zakazi",
    # Commenting target channels
    "temablog",
    "designer_ru",
    "startup_daily",
    "ecom_business",
]

async def main():
    print(f"=== LeadRadar Auto-Join Channels ===")
    print(f"Session path: {SESSION_PATH}")

    if not Path(f"{SESSION_PATH}.session").exists():
        print("ERROR: Session file not found!")
        return

    client = TelegramClient(
        SESSION_PATH,
        API_ID,
        API_HASH,
        connection_retries=5,
        retry_delay=3,
        timeout=25,
    )

    try:
        print("Connecting to Telegram MTProto...")
        await client.connect()
        if not await client.is_user_authorized():
            print("ERROR: User is not authorized in this session. Re-login required.")
            return

        me = await client.get_me()
        print(f"SUCCESS: Authorized as {me.first_name} (@{me.username or 'no_username'}, phone: {getattr(me, 'phone', 'hidden')})")

        print(f"\nFound {len(CHANNELS_TO_JOIN)} target channels/groups to join.")
        print("Safety interval: 10-15s between channels to prevent Telegram spam flag.\n")

        success_count = 0
        already_count = 0
        failed_count = 0

        for idx, channel in enumerate(CHANNELS_TO_JOIN, 1):
            uname = channel.replace("@", "").strip()
            print(f"[{idx}/{len(CHANNELS_TO_JOIN)}] Joining @{uname}...")

            try:
                entity = await client.get_entity(uname)
                await client(JoinChannelRequest(entity))
                print(f"  -> OK! Joined: {getattr(entity, 'title', uname)}")
                success_count += 1
                await asyncio.sleep(12)  # Anti-flood delay
            except UserAlreadyParticipantError:
                print(f"  -> Already a member of @{uname}")
                already_count += 1
            except InviteRequestSentError:
                print(f"  -> Join request sent (private/moderated group)")
                success_count += 1
            except FloodWaitError as e:
                print(f"  -> RATE LIMIT (FloodWait): Telegram requires waiting {e.seconds} seconds!")
                break
            except ChannelPrivateError:
                print(f"  -> Group is private or blocked")
                failed_count += 1
            except Exception as e:
                print(f"  -> Error joining @{uname}: {type(e).__name__} {e}")
                failed_count += 1
                await asyncio.sleep(4)

        print("\n" + "=" * 50)
        print(f"SUMMARY: Successfully joined: {success_count}, Already in chat: {already_count}, Skipped/Errors: {failed_count}")
        print("=" * 50)

    except Exception as exc:
        print(f"Connection failed: {type(exc).__name__} {exc}")
        print("\nTIP: If connection times out, ensure a VPN/Proxy is active for Telegram connection.")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
