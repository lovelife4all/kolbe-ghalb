# -*- coding: utf-8 -*-
"""
bulk_telegram.py — انتشار دسته‌جمعیِ پست‌ها در تلگرام

نکته‌ی مهم: فقط وضعیتِ تلگرام (tg_status) را «sent» می‌کند و status را «pending»
نگه می‌دارد تا اینستاگرام طبق برنامه‌ی روزانه (۳ پست در روز) آن‌ها را منتشر کند.

استفاده:
    export TELEGRAM_BOT_TOKEN="..." TELEGRAM_CHAT_ID="@kanal"
    python scripts/bulk_telegram.py --limit 10            # ۱۰ پست بعدی
    python scripts/bulk_telegram.py --limit 20 --delay 30  # با فاصله‌ی ۳۰ ثانیه
    python scripts/bulk_telegram.py --all                  # همه
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_image import ROOT  # noqa: E402
from publish import build_caption, load_rows, save_rows  # noqa: E402

POSTS_CSV = os.path.join(ROOT, "content", "posts.csv")


def send(chat_id: str, token: str, image_path: str | None, caption: str) -> bool:
    base = f"https://api.telegram.org/bot{token}"
    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as fh:
                r = requests.post(f"{base}/sendPhoto",
                                  data={"chat_id": chat_id, "caption": caption},
                                  files={"photo": fh}, timeout=120)
        else:
            r = requests.post(f"{base}/sendMessage",
                              json={"chat_id": chat_id, "text": caption}, timeout=60)
        return bool(r.json().get("ok"))
    except Exception as exc:  # noqa: BLE001
        print("   ❌ خطا:", exc)
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="انتشار دسته‌جمعی در تلگرام")
    ap.add_argument("--limit", type=int, default=10, help="تعداد پست (پیش‌فرض ۱۰)")
    ap.add_argument("--delay", type=int, default=15, help="فاصله‌ی بین پست‌ها به ثانیه")
    ap.add_argument("--all", action="store_true", help="همه‌ی پست‌های باقی‌مانده")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        sys.exit("❌ TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID را تنظیم کن")

    rows = load_rows()
    queue = [r for r in rows if (r.get("tg_status") or "").strip() != "sent"]
    if not args.all:
        queue = queue[: args.limit]

    print(f"📤 {len(queue)} پست برای انتشار در تلگرام (فاصله: {args.delay} ثانیه)")
    if args.dry_run:
        for r in queue:
            print(f"   [dry-run] {r['id']} — {r['text'][:50]}…")
        return

    ok = fail = 0
    for i, row in enumerate(queue, 1):
        pid = row["id"].strip()
        img = row.get("image", "").strip()
        img_abs = os.path.join(ROOT, img) if img else None
        print(f"\n[{i}/{len(queue)}] {pid} ({row.get('tone','')}) …", end=" ", flush=True)

        sent = send(chat, token, img_abs, build_caption(row, "telegram"))
        if sent:
            row["tg_status"] = "sent"
            print("✅")
            ok += 1
        else:
            print("❌")
            fail += 1

        save_rows(rows)          # ذخیره بعد از هر پست تا پیشرفت از دست نرود
        if i < len(queue):
            time.sleep(args.delay)

    print(f"\n📊 پایان: موفق {ok} | ناموفق {fail}")
    print("ℹ️  وضعیتِ اینستاگرام دست‌نخورده ماند — طبق برنامه‌ی ۳ پست در روز منتشر می‌شود.")


if __name__ == "__main__":
    main()
