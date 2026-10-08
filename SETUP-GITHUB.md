# 🚀 چک‌لیستِ راه‌اندازی روی گیت‌هاب

همه‌چیز آماده است؛ فقط این ۵ قدم باقی مانده. حدود **۱۰ دقیقه**.

> ⚠️ **ریپو باید Public باشد** — چون Zernio باید بتواند تصویر پست را از
> `raw.githubusercontent.com` دانلود کند.

---

## قدم ۱ — ساخت ریپو

**راه سریع** (اگر GitHub CLI نصب است):
```bash
bash push_to_github.sh YOUR_USERNAME kolbe-ghalb
```

**راه دستی:**
1. برو به [github.com/new](https://github.com/new)
2. نام: `kolbe-ghalb` | نوع: **Public** | هیچ تیکی نزن (بدون README/.gitignore)
3. Create repository
4. در پوشه‌ی پروژه:
```bash
git remote add origin https://github.com/YOUR_USERNAME/kolbe-ghalb.git
git push -u origin main
```

---

## قدم ۲ — Secretها (Settings → Secrets and variables → Actions)

تب **Secrets** → *New repository secret*:

| نام | از کجا می‌آید |
|---|---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_CHAT_ID` | `@kolbe_ghalb` (چون کانال عمومی است) |
| `ZERNIO_API_KEY` | [zernio.com/dashboard/api-keys](https://zernio.com/dashboard/api-keys) → Create API key |
| `ZERNIO_INSTAGRAM_ACCOUNT_ID` | `python scripts/zernio_setup.py` → مقدار `_id` جلوی `platform=instagram` |

تب **Variables** → *New repository variable*:

| نام | مقدار |
|---|---|
| `PAGE_SIGNATURE` | `@kolbe_ghalb` |

---

## قدم ۳ — اولین تست (بدون انتشار واقعی)

Actions → **«انتشار خودکار پست»** → **Run workflow** → تیک **dry_run** → **Run**

در لاگ باید این‌ها را ببینی:
```
🎯 پست انتخاب‌شده: p001 (عاشقانه)
🖼️  تصویر ساخته شد: content/images/post_p001.jpg
🧪 [dry-run] تلگرام: ...
🧪 [dry-run] اینستاگرام (Zernio): ...
📊 نتیجه: تلگرام=sent | اینستاگرام=sent
```
اگر سبز شد، اتصال‌ها برقرار است.

---

## قدم ۴ — تستِ واقعی

دوباره **Run workflow**، این بار **بدون تیک dry_run**.
برو کانال تلگرام و پیج اینستاگرام را چک کن. ✅

---

## قدم ۵ — فعال‌سازی خودکار

از این لحظه خودکار اجرا می‌شود:

| نوبت | وقت تهران | کرون (UTC) |
|---|---|---|
| صبح | ۰۹:۰۰ | `30 5 * * *` |
| عصر | ۱۵:۰۰ | `30 11 * * *` |
| شب | ۲۱:۰۰ | `30 17 * * *` |

---

## ⚠️ سه نکته‌ی مهم درباره‌ی GitHub Actions

1. **تأخیر:** کرونِ گیت‌هاب معمولاً ۵ تا ۱۵ دقیقه تأخیر دارد (سر ساعتِ دقیق اجرا نمی‌شود).
   برای پیج عاشقانه مشکلی نیست.
2. **خوابِ ۶۰ روزه:** اگر **۶۰ روز** هیچ commit ی در ریپو نباشد، گیت‌هاب زمان‌بندی را
   غیرفعال می‌کند. چون هر انتشار یک commit می‌سازد، این اتفاق نمی‌افتد — فقط اگر
   بانک محتوا خالی شود.
3. **حجم ریپو:** هر پست حدود ۲۸۰ کیلوبایت تصویر اضافه می‌کند (≈ ۲۵ مگابایت در ماه).
   تا چندین سال جا دارد (سقفِ نرمِ گیت‌هاب ۱ گیگابایت است).

---

## 🆘 اگر چیزی کار نکرد

| خطا | علت احتمالی |
|---|---|
| `تنظیمات تلگرام کامل نیست` | Secretهای تلگرام خالی است |
| `تنظیمات Zernio کامل نیست` | Secretهای Zernio خالی است یا accountId اشتباه |
| تلگرام کار کرد، اینستاگرام نه | اکانت اینستاگرام باید **Business/Creator** باشد |
| Zernio خطای تصویر داد | ریپو Private است، یا تصویر هنوز push نشده |
| `پستی برای انتشار نیست` | بانک محتوا تمام شده — پست‌های جدید به `posts.csv` اضافه کن |
