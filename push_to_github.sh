#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# push_to_github.sh — ساخت ریپو روی گیت‌هاب و بالا بردن پروژه
#
# استفاده:
#   bash push_to_github.sh YOUR_USERNAME kolbe-ghalb
#
# اگر ابزار gh (GitHub CLI) نصب باشد، ریپو را خودش می‌سازد و push می‌کند.
# در غیر این صورت، دستورات لازم را چاپ می‌کند تا دستی انجام دهید.
# ---------------------------------------------------------------------------
set -euo pipefail

USERNAME="${1:-}"
REPO="${2:-kolbe-ghalb}"

if [ -z "$USERNAME" ]; then
  echo "❌ نام کاربری گیت‌هاب را بده:"
  echo "   bash push_to_github.sh YOUR_USERNAME kolbe-ghalb"
  exit 1
fi

cd "$(dirname "$0")"

# مطمئن شو همه‌چیز commit شده
if [ -n "$(git status --porcelain)" ]; then
  echo "📦 تغییرات commit‌نشده پیدا شد؛ در حال commit…"
  git add -A
  git commit -m "به‌روزرسانی محتوا" || true
fi

git branch -M main 2>/dev/null || true

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "🚀 در حال ساخت ریپوی عمومی $USERNAME/$REPO با gh…"
  gh repo create "$USERNAME/$REPO" --public --source=. --remote=origin --push \
    --description "پیج عاشقانه — انتشار خودکار روی اینستاگرام و تلگرام"
  echo ""
  echo "✅ انجام شد: https://github.com/$USERNAME/$REPO"
else
  echo "ℹ️  ابزار gh در دسترس نیست (یا لاگین نیستی). این دستورات را اجرا کن:"
  echo ""
  echo "   1) برو به https://github.com/new و یک ریپوی Public به نام $REPO بساز"
  echo "      (هیچ تیکی نزن: بدون README، بدون .gitignore)"
  echo "   2) سپس این دستورات را اجرا کن:"
  echo ""
  echo "      git remote remove origin 2>/dev/null || true"
  echo "      git remote add origin https://github.com/$USERNAME/$REPO.git"
  echo "      git push -u origin main"
  echo ""
  echo "   نصب gh (اختیاری): https://cli.github.com  سپس: gh auth login"
fi

echo ""
echo "============================================================"
echo "  بعد از push، این Secretها را در ریپو اضافه کن:"
echo "  Settings → Secrets and variables → Actions → New repository secret"
echo ""
echo "    TELEGRAM_BOT_TOKEN            توکن ربات از @BotFather"
echo "    TELEGRAM_CHAT_ID              @kolbe_ghalb"
echo "    ZERNIO_API_KEY                کلید از zernio.com/dashboard/api-keys"
echo "    ZERNIO_INSTAGRAM_ACCOUNT_ID   از scripts/zernio_setup.py"
echo ""
echo "  و در تب Variables:"
echo "    PAGE_SIGNATURE = @kolbe_ghalb"
echo "============================================================"
