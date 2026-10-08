# -*- coding: utf-8 -*-
"""
publish.py — انتخاب پست بعدی از بانک محتوا و انتشار خودکار

  · تلگرام    → مستقیم با Telegram Bot API
  · اینستاگرام → از طریق Zernio (یک درخواست، بدون اپِ فیسبوک و بدون تمدید توکن)

دو فاز (در GitHub Actions جدا اجرا می‌شوند):
    python scripts/publish.py --prepare   # انتخاب پست بعدی + ساخت تصویر + commit/push
    python scripts/publish.py --publish   # ارسال به تلگرام + اینستاگرام + ذخیره‌ی وضعیت

اجرای محلی:
    python scripts/publish.py --dry-run   # شبیه‌سازی بدون ارسال واقعی
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_image import make_image, ROOT  # noqa: E402

POSTS_CSV = os.path.join(ROOT, "content", "posts.csv")
FIELDS = ["id", "tone", "theme", "text", "source", "hashtags", "caption", "image",
          "status", "tg_status", "ig_status", "published_at"]

TZ = timezone(timedelta(hours=3, minutes=30))   # وقت تهران
ZERNIO_BASE = "https://zernio.com/api/v1"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


CFG = {
    # تلگرام
    "tg_token": env("TELEGRAM_BOT_TOKEN"),
    "tg_chat": env("TELEGRAM_CHAT_ID"),
    # اینستاگرام از طریق Zernio
    "zernio_key": env("ZERNIO_API_KEY"),
    "zernio_account": env("ZERNIO_INSTAGRAM_ACCOUNT_ID"),
    # عمومی
    "repo": env("GITHUB_REPOSITORY"),
    "branch": env("GITHUB_REF_NAME", "main"),
    "signature": env("PAGE_SIGNATURE"),
    "hashtags": env("PAGE_HASHTAGS", "عاشقانه عشق دلتنگی"),
    "cdn": env("IMAGE_CDN", "raw"),
    "dry_run": env("DRY_RUN", "0") == "1",
    "ci": env("GITHUB_ACTIONS") == "true",
}


# ---------------------------------------------------------------- فایل محتوا
def load_rows() -> list[dict]:
    with open(POSTS_CSV, newline="", encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def save_rows(rows: list[dict]) -> None:
    with open(POSTS_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def update_row(rows: list[dict], post_id: str, changes: dict) -> None:
    for r in rows:
        if r["id"].strip() == post_id:
            r.update(changes)


def pick_next(rows: list[dict], phase: str) -> dict | None:
    wanted = "pending" if phase == "prepare" else "ready"
    for r in rows:
        if (r.get("status") or "").strip() == wanted:
            return r
    if phase == "publish":
        for r in rows:
            if (r.get("status") or "").strip() == "pending":
                return r
    return None


def clean_text(text: str) -> str:
    return text.replace("<br>", "\n").strip()


# ---------------------------------------------------------------- کپشن
def build_caption(row: dict, platform: str) -> str:
    # اینستاگرام: کپشنِ آماده از ستون caption + هشتگ + امضا
    if platform == "instagram" and (row.get("caption") or "").strip():
        parts = [clean_text(row["caption"])]
    else:
        parts = [clean_text(row["text"])]
        source = (row.get("source") or "").strip()
        parts.append(f"— {source}" if source and source != "اختصاصی" else "— نوشته‌ی اختصاصیِ پیج")

    tags = " ".join(
        "#" + t.strip().lstrip("#")
        for t in ((row.get("hashtags") or CFG["hashtags"]).split())
        if t.strip()
    )
    if tags:
        parts.append(tags)
    if CFG["signature"]:
        parts.append(CFG["signature"])

    caption = "\n\n".join(p for p in parts if p)
    return caption[:2200] if platform == "instagram" else caption[:4000]


# ---------------------------------------------------------------- گیت
def git_sync(message: str) -> None:
    if not CFG["ci"]:
        print("ℹ️  اجرای محلی است؛ commit انجام نشد (خودت git push کن).")
        return
    subprocess.run(["git", "config", "user.name", "kolbe-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "kolbe-bot@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", "content"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("ℹ️  تغییری برای commit وجود ندارد.")
        return
    subprocess.run(["git", "commit", "-m", message], check=True)
    subprocess.run(["git", "push"], check=True)
    print(f"📦 commit و push شد: {message}")


def public_image_url(rel_path: str) -> str:
    """لینک عمومی تصویر تا Zernio/اینستاگرام بتوانند آن را دانلود کنند."""
    rel = rel_path.replace(os.sep, "/").lstrip("/")
    if CFG["cdn"] == "jsdelivr" and CFG["repo"]:
        return f"https://cdn.jsdelivr.net/gh/{CFG['repo']}@{CFG['branch']}/{rel}"
    if CFG["repo"]:
        return f"https://raw.githubusercontent.com/{CFG['repo']}/{CFG['branch']}/{rel}"
    return ""


# ---------------------------------------------------------------- تلگرام
def telegram_send(image_path: str | None, caption: str) -> bool:
    if not (CFG["tg_token"] and CFG["tg_chat"]):
        print("⚠️  تنظیمات تلگرام کامل نیست؛ رد شد.")
        return False
    if CFG["dry_run"]:
        print("🧪 [dry-run] تلگرام:", caption[:70], "…")
        return True

    base = f"https://api.telegram.org/bot{CFG['tg_token']}"
    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as fh:
                r = requests.post(f"{base}/sendPhoto",
                                  data={"chat_id": CFG["tg_chat"], "caption": caption},
                                  files={"photo": fh}, timeout=90)
        else:
            r = requests.post(f"{base}/sendMessage",
                              json={"chat_id": CFG["tg_chat"], "text": caption}, timeout=60)
        data = r.json()
        if data.get("ok"):
            print("✅ تلگرام: ارسال شد.")
            return True
        print("❌ خطای تلگرام:", data)
    except Exception as exc:  # noqa: BLE001
        print("❌ خطای تلگرام:", exc)
    return False


# ---------------------------------------------------------------- اینستاگرام (Zernio)
def zernio_publish(image_path: str | None, caption: str) -> bool:
    if not (CFG["zernio_key"] and CFG["zernio_account"]):
        print("⚠️  تنظیمات Zernio کامل نیست؛ انتشار در اینستاگرام رد شد.")
        return False
    if not image_path:
        print("⚠️  پست بدون تصویر است؛ اینستاگرام فقط عکس/ویدیو می‌پذیرد.")
        return False

    if CFG["dry_run"]:
        print("🧪 [dry-run] اینستاگرام (Zernio):", caption[:70], "…")
        return True

    image_url = public_image_url(os.path.relpath(image_path, ROOT))
    if not image_url:
        print("⚠️  ریپو مشخص نیست و لینک عمومی برای تصویر ساخته نشد.")
        return False

    headers = {"Authorization": f"Bearer {CFG['zernio_key']}", "Content-Type": "application/json"}
    body = {
        "content": caption,
        "mediaItems": [{"type": "image", "url": image_url}],
        "platforms": [{"platform": "instagram", "accountId": CFG["zernio_account"]}],
        "publishNow": True,
    }

    try:
        r = requests.post(f"{ZERNIO_BASE}/posts", json=body, headers=headers, timeout=120)
        data = r.json()
        post = data.get("post") or {}
        status = post.get("status")
        post_id = post.get("_id")

        # تلاش برای گرفتنِ وضعیت نهایی
        for _ in range(10):
            if status in ("published", "failed", "partial"):
                break
            time.sleep(6)
            st = requests.get(f"{ZERNIO_BASE}/posts/{post_id}", headers=headers, timeout=60).json()
            status = (st.get("post") or {}).get("status", status)

        if status == "published":
            url = (post.get("platforms") or [{}])[0].get("platformPostUrl")
            print(f"✅ اینستاگرام: منتشر شد. {url or ''}")
            return True

        print(f"❌ انتشار ناموفق (status={status}):", data)
    except Exception as exc:  # noqa: BLE001
        print("❌ خطای Zernio:", exc)
    return False


# ---------------------------------------------------------------- فازها
def phase_prepare(force_id: str | None) -> int:
    rows = load_rows()
    row = next((r for r in rows if r["id"].strip() == force_id), None) if force_id else pick_next(rows, "prepare")
    if not row:
        print("ℹ️  پستِ جدیدی برای آماده‌سازی نیست.")
        return 0

    pid = row["id"].strip()
    print(f"🎯 پست انتخاب‌شده: {pid} ({row.get('tone','')})")

    img_rel = (row.get("image") or "").strip()
    img_abs = os.path.join(ROOT, img_rel) if img_rel else ""
    if not img_rel or not os.path.exists(img_abs):
        img_abs = make_image(pid, clean_text(row["text"]), row.get("theme", ""), CFG["signature"])
        img_rel = os.path.relpath(img_abs, ROOT).replace(os.sep, "/")
        update_row(rows, pid, {"image": img_rel})
        print(f"🖼️  تصویر ساخته شد: {img_rel}")
    else:
        print(f"🖼️  تصویر آماده است: {img_rel}")

    update_row(rows, pid, {"status": "ready"})
    save_rows(rows)
    git_sync(f"آماده‌سازی پست {pid}")
    print("URL عمومی تصویر:", public_image_url(img_rel) or "(بعد از push روی گیت‌هاب ساخته می‌شود)")
    return 0


def phase_publish(force_id: str | None) -> int:
    rows = load_rows()
    row = next((r for r in rows if r["id"].strip() == force_id), None) if force_id else pick_next(rows, "publish")
    if not row:
        print("ℹ️  پستی برای انتشار نیست.")
        return 0

    pid = row["id"].strip()
    img_rel = (row.get("image") or "").strip()
    img_abs = os.path.join(ROOT, img_rel) if img_rel else None

    ok_tg = telegram_send(img_abs, build_caption(row, "telegram"))
    ok_ig = zernio_publish(img_abs, build_caption(row, "instagram"))

    changes = {
        "tg_status": "sent" if ok_tg else ("skipped" if not CFG["tg_token"] else "failed"),
        "ig_status": "sent" if ok_ig else ("skipped" if not CFG["zernio_key"] else "failed"),
        "published_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
        "status": "published",
    }
    update_row(rows, pid, changes)
    save_rows(rows)
    git_sync(f"انتشار پست {pid}")
    print(f"📊 نتیجه: تلگرام={changes['tg_status']} | اینستاگرام={changes['ig_status']}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="انتشار خودکار محتوای عاشقانه")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--id", help="اجبار روی یک شناسه (مثل p003)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        CFG["dry_run"] = True

    if args.prepare:
        sys.exit(phase_prepare(args.id))
    if args.publish:
        sys.exit(phase_publish(args.id))
    if phase_prepare(args.id) == 0:
        phase_publish(args.id)


if __name__ == "__main__":
    main()
