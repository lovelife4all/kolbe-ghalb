# -*- coding: utf-8 -*-
"""
telegram_setup.py — بررسیِ تنظیمات تلگرام قبل از فعال‌سازی انتشار خودکار

کمک می‌کند مطمئن شوی ربات و کانال درست وصل شده‌اند:

    export TELEGRAM_BOT_TOKEN="توکنی که BotFather داده"
    python scripts/telegram_setup.py                      # نمایش اطلاعات ربات و چت‌های یافت‌شده
    python scripts/telegram_setup.py --send @kolbe_ghalb  # ارسال یک پیام تست
"""
from __future__ import annotations

import argparse
import os

import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def api(method: str, **params) -> dict:
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}",
                      json=params or None, timeout=60)
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"ok": False, "description": r.text[:300]}


def main() -> None:
    ap = argparse.ArgumentParser(description="بررسی و تستِ تنظیمات تلگرام")
    ap.add_argument("--token", help="توکن ربات (یا از متغیر محیطی TELEGRAM_BOT_TOKEN)")
    ap.add_argument("--send", metavar="CHAT", help="ارسال پیام تست به این چت (مثل @kolbe_ghalb)")
    args = ap.parse_args()

    global TOKEN
    TOKEN = (args.token or TOKEN).strip()
    if not TOKEN:
        ap.error("توکن را با --token بده یا متغیر TELEGRAM_BOT_TOKEN را تنظیم کن")

    me = api("getMe")
    if not me.get("ok"):
        print("❌ توکن نامعتبر است:", me.get("description"))
        return
    print(f"✅ ربات پیدا شد: @{me['result']['username']} ({me['result']['first_name']})")

    if args.send:
        res = api("sendMessage", chat_id=args.send,
                  text="🌹 تستِ اتصال — پیج عاشقانه‌ی kolbe_ghalb")
        if res.get("ok"):
            print(f"✅ پیام تست به {args.send} ارسال شد. برو کانال را چک کن.")
        else:
            print("❌ ارسال ناموفق بود:", res.get("description"))
        return

    print("\nدر حال جستجوی چت‌ها… (اگر خالی بود، یک پیام در کانال بفرست و دوباره اجرا کن)")
    upd = api("getUpdates", timeout=10)
    chats: dict[str, str] = {}
    for item in upd.get("result", []):
        for key in ("message", "channel_post", "my_chat_member", "edited_channel_post"):
            if key in item and isinstance(item[key], dict):
                chat = item[key].get("chat", {})
                if chat.get("id"):
                    title = chat.get("title") or chat.get("username") or chat.get("first_name")
                    chats[str(chat["id"])] = f"{chat.get('type', '?')} — {title}"

    if not chats:
        print("⚠️  چتی پیدا نشد. مطمئن شو ربات را ادمینِ کانال کرده‌ای و یک پیام در کانال فرستاده‌ای.")
        print("💡 اگر کانال عمومی است، می‌توانی مستقیماً از @username به عنوان TELEGRAM_CHAT_ID استفاده کنی.")
        return

    print("\n✅ چت‌های پیدا شده (مقدارِ سمت چپ را به عنوان TELEGRAM_CHAT_ID استفاده کن):")
    for cid, desc in chats.items():
        print(f"   {cid}   ←   {desc}")


if __name__ == "__main__":
    main()
