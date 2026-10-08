# -*- coding: utf-8 -*-
"""
zernio_setup.py — راه‌اندازی و تستِ اتصال اینستاگرام از طریق Zernio

پیش‌نیاز: یک کلید API از https://zernio.com/dashboard/api-keys

    export ZERNIO_API_KEY="sk_..."

    python scripts/zernio_setup.py                    # نمایش حساب‌های متصل (و گرفتن accountId)
    python scripts/zernio_setup.py --new-profile "kolbe_ghalb"
    python scripts/zernio_setup.py --connect <PROFILE_ID>   # لینک اتصال اینستاگرام
    python scripts/zernio_setup.py --test p001              # انتشار یک پست واقعی برای تست
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://zernio.com/api/v1"
KEY = os.getenv("ZERNIO_API_KEY", "").strip()


def headers() -> dict:
    return {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def show_accounts() -> None:
    r = requests.get(f"{BASE}/accounts", headers=headers(), timeout=60)
    data = r.json()
    accounts = data.get("accounts") or []
    if not accounts:
        print("⚠️  هیچ حسابی متصل نیست. اول --new-profile و --connect را اجرا کن.")
        print("   پاسخ:", str(data)[:300])
        return
    print("✅ حساب‌های متصل:")
    for a in accounts:
        flag = " ← اینستاگرام" if a.get("platform") == "instagram" else ""
        print(f"   platform={a.get('platform'):<12} _id={a.get('_id')}  @{a.get('username','?')}{flag}")
    ig = [a for a in accounts if a.get("platform") == "instagram"]
    if ig:
        print(f"\n👉 مقدار ZERNIO_INSTAGRAM_ACCOUNT_ID را برابر بگذار با: {ig[0]['_id']}")


def new_profile(name: str) -> None:
    r = requests.post(f"{BASE}/profiles", json={"name": name}, headers=headers(), timeout=60)
    data = r.json()
    pid = (data.get("profile") or {}).get("_id")
    if pid:
        print(f"✅ پروفایل ساخته شد. profileId = {pid}")
        print(f"   حالا اجرا کن: python scripts/zernio_setup.py --connect {pid}")
    else:
        print("❌ خطا:", str(data)[:400])


def connect(profile_id: str) -> None:
    r = requests.get(f"{BASE}/connect/instagram", params={"profileId": profile_id},
                     headers=headers(), timeout=60)
    data = r.json()
    url = data.get("authUrl")
    if url:
        print("✅ این لینک را در مرورگر باز کن و اجازه بده:")
        print(f"\n{url}\n")
        print("بعد از اتصال، دوباره اجرا کن:  python scripts/zernio_setup.py")
    else:
        print("❌ خطا:", str(data)[:400])


def test_post(post_id: str, account_id: str, repo: str, branch: str = "main") -> None:
    import csv
    rows = list(csv.DictReader(open(os.path.join(ROOT, "content", "posts.csv"), encoding="utf-8")))
    row = next((r for r in rows if r["id"].strip() == post_id), None)
    if not row:
        print(f"❌ پست {post_id} پیدا نشد.")
        return
    rel = (row.get("image") or "").lstrip("/")
    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}"
    caption = (row["text"].replace("<br>", "\n") + "\n\n#عاشقانه #تست\n@kolbe_ghalb")[:2200]

    print(f"🖼️  تصویر: {image_url}")
    body = {
        "content": caption,
        "mediaItems": [{"type": "image", "url": image_url}],
        "platforms": [{"platform": "instagram", "accountId": account_id}],
        "publishNow": True,
    }
    r = requests.post(f"{BASE}/posts", json=body, headers=headers(), timeout=120)
    data = r.json()
    status = (data.get("post") or {}).get("status")
    if status in ("published", "publishing", "pending", "queued", "scheduled"):
        print(f"✅ ارسال شد (status={status}). اینستاگرام را چک کن.")
        print("   postId:", (data.get("post") or {}).get("_id"))
    else:
        print("❌ پاسخ:", str(data)[:500])


def main() -> None:
    ap = argparse.ArgumentParser(description="راه‌اندازی Zernio برای اینستاگرام")
    ap.add_argument("--new-profile", metavar="NAME")
    ap.add_argument("--connect", metavar="PROFILE_ID")
    ap.add_argument("--test", metavar="POST_ID")
    ap.add_argument("--account", default=os.getenv("ZERNIO_INSTAGRAM_ACCOUNT_ID", ""))
    ap.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""))
    args = ap.parse_args()

    if not KEY:
        ap.error("کلید API را در متغیر محیطی ZERNIO_API_KEY تنظیم کن")

    if args.new_profile:
        new_profile(args.new_profile)
    elif args.connect:
        connect(args.connect)
    elif args.test:
        if not args.account:
            ap.error("برای تست باید --account یا متغیر ZERNIO_INSTAGRAM_ACCOUNT_ID را بدهی")
        if not args.repo:
            ap.error("برای تست باید --repo owner/name را بدهی (ریپو باید عمومی باشد)")
        test_post(args.test, args.account, args.repo)
    else:
        show_accounts()


if __name__ == "__main__":
    main()
