import httpx
import json

BOT_TOKEN = "9286221746:AAFZapvWPAsJS1llwaydBUiyngF3RPlVyRI"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEB_APP_URL = "https://decimal-logical-karen-penn.trycloudflare.com"

def main():
    print(f"Configuring Telegram Bot via Bot API...")
    
    # 1. getMe
    res = httpx.get(f"{BASE_URL}/getMe", timeout=10)
    print("getMe:", res.json())
    bot_info = res.json().get("result", {})
    username = bot_info.get("username")

    # 2. setChatMenuButton (The bottom-left WebApp button in the bot)
    menu_payload = {
        "menu_button": {
            "type": "web_app",
            "text": "🚀 Открыть LeadRadar",
            "web_app": {
                "url": WEB_APP_URL
            }
        }
    }
    res = httpx.post(f"{BASE_URL}/setChatMenuButton", json=menu_payload, timeout=10)
    print("setChatMenuButton:", res.json())

    # 3. setMyDescription
    desc_payload = {
        "description": "Murasaki LeadRadar — радар заказов фриланса (Kwork, FL.ru, Telegram), генерация демо-лендингов и AI-откликов под ключ.",
        "short_description": "Радар фриланс-заказов Kwork, FL, TG и генератор лендингов."
    }
    httpx.post(f"{BASE_URL}/setMyDescription", json=desc_payload, timeout=10)
    httpx.post(f"{BASE_URL}/setMyShortDescription", json={"short_description": desc_payload["short_description"]}, timeout=10)

    print("\n" + "=" * 50)
    print("🎉 БОТ ПОЛНОСТЬЮ НАСТРОЕН!")
    print(f"Юзернейм: @{username}")
    print(f"Ссылка на бота: https://t.me/{username}")
    print(f"Mini App URL: {WEB_APP_URL}")
    print("=" * 50)

if __name__ == "__main__":
    main()
