# -*- coding: utf-8 -*-
"""
setup_with_token.py — ساخت ریپو روی گیت‌هاب و push کردنِ پروژه با یک Personal Access Token

    export GITHUB_PAT="ghp_..."
    python scripts/setup_with_token.py                       # ساخت kolbe-ghalb و push
    python scripts/setup_with_token.py --name my-page        # با نام دیگر
    python scripts/setup_with_token.py --with-secrets        # اگر مقدار Secretها در env باشد، آن‌ها را هم ثبت کن

نکته: توکن باید دست‌کم دو دسترسی را داشته باشد:
    ✅ repo      (ایجاد ریپو و push)
    ✅ workflow  (اجازه‌ی push کردنِ فایل‌های .github/workflows)
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys

import requests

API = "https://api.github.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_NAMES = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "ZERNIO_API_KEY", "ZERNIO_INSTAGRAM_ACCOUNT_ID"]
VAR_NAMES = ["PAGE_SIGNATURE"]


def gh(method: str, path: str, token: str, **kw):
    r = requests.request(method, f"{API}{path}", timeout=60,
                         headers={"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"}, **kw)
    return r


def run(cmd: list[str], cwd: str = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def ensure_repo(token: str, name: str, desc: str) -> tuple[str, str]:
    me = gh("GET", "/user", token)
    if me.status_code != 200:
        sys.exit(f"❌ توکن نامعتبر است (HTTP {me.status_code}): {me.text[:200]}")
    owner = me.json()["login"]
    print(f"👤 کاربر: {owner}")

    r = gh("POST", "/user/repos", token,
           json={"name": name, "description": desc, "private": False, "auto_init": False})
    if r.status_code == 201:
        print(f"✅ ریپو ساخته شد: {owner}/{name}")
    elif r.status_code == 422:
        print(f"ℹ️  ریپو از قبل وجود دارد: {owner}/{name} — ادامه می‌دهیم.")
    else:
        sys.exit(f"❌ ساخت ریپو ناموفق (HTTP {r.status_code}): {r.text[:250]}")
    return owner, name


def push(token: str, owner: str, name: str) -> None:
    url = f"https://x-access-token:{token}@github.com/{owner}/{name}.git"
    run(["git", "remote", "remove", "origin"], check=False)
    run(["git", "remote", "add", "origin", url])
    run(["git", "branch", "-M", "main"])
    res = run(["git", "push", "-u", "origin", "main"], check=False)
    if res.returncode != 0:
        print(res.stdout[-1500:])
        print(res.stderr[-1500:])
        print("\n❌ push ناموفق بود. معمولاً به این معنی است که توکن دسترسی "
              "`workflow` را ندارد (برای push کردنِ .github/workflows لازم است).")
        sys.exit(1)
    print("✅ push انجام شد.")


def set_secrets(token: str, owner: str, name: str) -> None:
    try:
        from nacl import encoding, public  # type: ignore
    except ImportError:
        print("⚠️  کتابخانه‌ی PyNaCl نصب نیست؛ ثبت Secretها رد شد (بعداً دستی اضافه کن).")
        return

    pk = gh("GET", f"/repos/{owner}/{name}/actions/secrets/public-key", token).json()
    pub = public.PublicKey(pk["key"].encode(), encoding.Base64Encoder())
    for name_ in SECRET_NAMES:
        val = os.getenv(name_, "").strip()
        if not val:
            print(f"   ⏭️  {name_}: مقداری ندارد، رد شد.")
            continue
        sealed = public.SealedBox(pub).encrypt(val.encode(), encoder=encoding.Base64Encoder())
        r = gh("PUT", f"/repos/{owner}/{name}/actions/secrets/{name_}", token,
               json={"encrypted_value": sealed.decode(), "key_id": pk["key_id"]})
        print(f"   {'✅' if r.status_code in (201, 204) else '❌'} Secret {name_}")

    for var in VAR_NAMES:
        val = os.getenv(var, "").strip()
        if not val:
            continue
        r = gh("POST", f"/repos/{owner}/{name}/actions/variables", token,
               json={"name": var, "value": val})
        if r.status_code not in (201, 204):
            gh("PATCH", f"/repos/{owner}/{name}/actions/variables/{var}", token,
               json={"name": var, "value": val})
        print(f"   ✅ Variable {var}")


def main() -> None:
    ap = argparse.ArgumentParser(description="ساخت ریپو و push با توکن شخصی")
    ap.add_argument("--name", default="kolbe-ghalb")
    ap.add_argument("--desc", default="پیج عاشقانه — انتشار خودکار روی اینستاگرام و تلگرام")
    ap.add_argument("--with-secrets", action="store_true",
                    help="ثبت Secretها از متغیرهای محیطی هم‌نام")
    args = ap.parse_args()

    token = os.getenv("GITHUB_PAT", "").strip()
    if not token:
        sys.exit("❌ توکن را در متغیر محیطی GITHUB_PAT قرار بده.")

    owner, name = ensure_repo(token, args.name, args.desc)
    push(token, owner, name)

    if args.with_secrets:
        print("\n🔐 ثبت Secretها…")
        set_secrets(token, owner, name)

    repo = gh("GET", f"/repos/{owner}/{name}", token).json()
    print("\n" + "=" * 60)
    print(f"🎉 آماده: https://github.com/{owner}/{name}")
    print(f"   Actions: https://github.com/{owner}/{name}/actions")
    print(f"   Secrets: https://github.com/{owner}/{name}/settings/secrets/actions")
    print("=" * 60)


if __name__ == "__main__":
    main()
