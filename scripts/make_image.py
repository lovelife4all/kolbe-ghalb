# -*- coding: utf-8 -*-
"""
make_image.py — ساخت پست تصویری (۱۰۸۰×۱۳۵۰) برای اینستاگرام و تلگرام

  · فونت فارسیِ وزیرمتن (Vazirmatn)
  · چینشِ صحیحِ راست‌به‌چپ با Raqm/HarfBuzz
  · ایموجیِ رنگیِ واقعی (تصاویر PNG در assets/emoji)
  · پس‌زمینه‌ی عاشقانه + امضای پیج در پایینِ وسط

استفاده:
    python scripts/make_image.py --all
    python scripts/make_image.py --id p001 --text "متن شما 🌹" --theme rose
"""
from __future__ import annotations

import argparse
import csv
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, features

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "Vazirmatn-Regular.ttf")
BG_DIR = os.path.join(ROOT, "assets", "backgrounds")
EMOJI_DIR = os.path.join(ROOT, "assets", "emoji")
POSTS_CSV = os.path.join(ROOT, "content", "posts.csv")
OUT_DIR = os.path.join(ROOT, "content", "images")

W, H = 1080, 1350
MARGIN = 100
MAX_FONT = 82          # سقف اندازه‌ی فونت
MIN_FONT = 36
LINE_RATIO = 1.75
EMOJI_RATIO = 1.12     # اندازه‌ی ایموجی نسبت به فونت
EMOJI_DY = 0.30        # جابجاییِ عمودیِ ایموجی برای تراز با خطِ متن

CENTER_ALPHA = 150
EDGE_ALPHA = 88
VIGNETTE = 58
TEXT_COLOR = (255, 246, 240, 255)
SHADOW_COLOR = (0, 0, 0, 170)

FALLBACK = {
    "rose":   ("#2a0c17", "#7d2240"),   "night":  ("#0a0f28", "#2b3170"),
    "cream":  ("#33231b", "#9c6a3c"),   "sunset": ("#3a1030", "#c2410c"),
    "mint":   ("#06231e", "#1d6b59"),   "blush":  ("#2a1730", "#8c5a86"),
    "wine":   ("#180509", "#6d1420"),   "ocean":  ("#071a2b", "#175a7a"),
    "alone":  ("#0d1220", "#2f3b5c"),   "rain":   ("#0b1418", "#244a55"),
    "empty":  ("#1a1410", "#4a3a2a"),   "farewell": ("#1b0f14", "#5a2436"),
}
DEFAULT_THEME = "rose"
HAS_RAQM = features.check("raqm")


def rtl_kw() -> dict:
    return {"direction": "rtl", "language": "fa"} if HAS_RAQM else {}


def visual(line: str) -> str:
    if HAS_RAQM:
        return line
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(line))


# ---------------------------------------------------------------- ایموجی
_EMOJI_CHARS: set[str] = set()
_EMOJI_IMG: dict[str, Image.Image | None] = {}


def _scan_emoji() -> set[str]:
    if _EMOJI_CHARS or not os.path.isdir(EMOJI_DIR):
        return _EMOJI_CHARS
    for fn in os.listdir(EMOJI_DIR):
        if not fn.endswith(".png"):
            continue
        try:
            cps = fn[:-4].split("-")
            _EMOJI_CHARS.add("".join(chr(int(c, 16)) for c in cps))                       # با fe0f
            _EMOJI_CHARS.add("".join(chr(int(c, 16)) for c in cps if c != "fe0f"))        # بدون fe0f
        except ValueError:
            pass
    return _EMOJI_CHARS


def emoji_image(ch: str) -> Image.Image | None:
    if ch in _EMOJI_IMG:
        return _EMOJI_IMG[ch]
    _scan_emoji()
    base = "-".join(f"{ord(c):04x}" for c in ch)
    base_novs = "-".join(f"{ord(c):04x}" for c in ch if ord(c) != 0xFE0F)
    img = None
    for name in (base, base_novs, base_novs + "-fe0f"):
        p = os.path.join(EMOJI_DIR, name + ".png")
        if os.path.exists(p):
            img = Image.open(p).convert("RGBA")
            break
    _EMOJI_IMG[ch] = img
    return img


def split_runs(line: str) -> list[tuple[str, str]]:
    """تقسیمِ خط به بخش‌های «متن» و «ایموجی»."""
    chars = sorted(_scan_emoji(), key=len, reverse=True)
    if not chars:
        return [("t", line)] if line else []
    runs: list[tuple[str, str]] = []
    buf, i = "", 0
    while i < len(line):
        hit = next((c for c in chars if line.startswith(c, i)), None)
        if hit:
            if buf:
                runs.append(("t", buf))
                buf = ""
            runs.append(("e", hit))
            i += len(hit)
        else:
            buf += line[i]
            i += 1
    if buf:
        runs.append(("t", buf))
    return runs


def run_width(run: tuple[str, str], font: ImageFont.FreeTypeFont) -> float:
    kind, s = run
    if kind == "e":
        return font.size * EMOJI_RATIO
    return font.getlength(visual(s), **rtl_kw())


def line_width(line: str, font: ImageFont.FreeTypeFont) -> float:
    return sum(run_width(r, font) for r in split_runs(line))


# ---------------------------------------------------------------- پس‌زمینه
def hex_to_rgb(v: str) -> tuple[int, int, int]:
    v = v.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def fallback_gradient(theme: str) -> Image.Image:
    a, b = (hex_to_rgb(x) for x in FALLBACK.get(theme, FALLBACK[DEFAULT_THEME]))
    small = Image.new("RGB", (96, 96))
    px = small.load()
    for y in range(96):
        for x in range(96):
            t = (x / 95 * 0.45) + (y / 95 * 0.55)
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return small.resize((W, H), Image.BICUBIC)


def load_background(theme: str) -> Image.Image:
    path = os.path.join(BG_DIR, f"{theme}.jpg")
    if not os.path.exists(path):
        return fallback_gradient(theme).convert("RGB")
    bg = Image.open(path).convert("RGB")
    scale = max(W / bg.width, H / bg.height)
    nw, nh = max(W, int(bg.width * scale) + 1), max(H, int(bg.height * scale) + 1)
    bg = bg.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    return bg.crop((left, top, left + W, top + H))


def normalize_brightness(bg: Image.Image, target: int = 118) -> Image.Image:
    gray = bg.convert("L")
    hist = gray.histogram()
    total = sum(hist) or 1
    lum = sum(i * hist[i] for i in range(256)) / total
    if lum < 2:
        return bg
    scale = max(0.42, min(2.8, target / lum))
    lift = max(0.0, min(45.0, (target - min(255, lum * scale)) * 0.6))
    if abs(scale - 1) < 0.04 and lift < 1:
        return bg
    lut = [min(255, int(i * scale + lift)) for i in range(256)]
    return bg.point(lut * 3)


def apply_scrim(bg: Image.Image) -> Image.Image:
    band = Image.new("L", (1, H))
    bp = band.load()
    for y in range(H):
        center = 1 - abs(2 * y / H - 1)
        bp[0, y] = int(EDGE_ALPHA + (CENTER_ALPHA - EDGE_ALPHA) * center)
    mask = band.resize((W, H), Image.BICUBIC)

    vig = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vig)
    for i in range(80):
        r = int((i / 80) * (W * 0.80))
        d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=int(VIGNETTE * (1 - i / 80)))
    vig = vig.filter(ImageFilter.GaussianBlur(70))

    mask = ImageChops.add(mask, vig)
    return Image.composite(Image.new("RGB", (W, H), (12, 9, 14)), bg, mask)


# ---------------------------------------------------------------- متن
def logical_lines(text: str) -> list[str]:
    return [p.strip() for p in text.replace("<br>", "\n").split("\n") if p.strip()]


def wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    out: list[str] = []
    for para in logical_lines(text):
        words = para.split()
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if not current or line_width(trial, font) <= max_width:
                current = trial
            else:
                out.append(current)
                current = word
        if current:
            out.append(current)
    return out


def fit_font(text: str) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    max_width = W - 2 * MARGIN
    max_height = H - 2 * MARGIN - 210
    for size in range(MAX_FONT, MIN_FONT - 1, -2):
        font = ImageFont.truetype(FONT_REGULAR, size)
        lines = wrap(text, font, max_width)
        if len(lines) * size * LINE_RATIO <= max_height:
            return font, lines
    font = ImageFont.truetype(FONT_REGULAR, MIN_FONT)
    return font, wrap(text, font, max_width)


def draw_line(img: Image.Image, d: ImageDraw.ImageDraw, line: str,
              font: ImageFont.FreeTypeFont, x_right: float, y: float) -> None:
    """رسم یک خطِ راست‌به‌چپ با پشتیبانی از ایموجی."""
    runs = split_runs(line)
    if not runs:
        return
    widths = [run_width(r, font) for r in runs]
    x = x_right - sum(widths)
    kw = rtl_kw()

    for run, w in zip(reversed(runs), reversed(widths)):      # ترتیبِ بصری: چپ به راست
        kind, s = run
        if kind == "e":
            em = emoji_image(s)
            if em:
                size = int(font.size * EMOJI_RATIO)
                top = int(y + font.size * EMOJI_DY)
                img.paste(em.resize((size, size), Image.LANCZOS), (int(x), top),
                          em.resize((size, size), Image.LANCZOS))
        else:
            vis = visual(s)
            d.text((x + 4, y + 4), vis, font=font, fill=SHADOW_COLOR, anchor="la", **kw)
            d.text((x, y), vis, font=font, fill=TEXT_COLOR, anchor="la", **kw)
        x += w


def draw_block(img: Image.Image, lines: list[str], font: ImageFont.FreeTypeFont) -> None:
    d = ImageDraw.Draw(img)
    size = font.size
    lh = size * LINE_RATIO
    y = (H - len(lines) * lh) / 2
    x_right = W - MARGIN

    d.line([(x_right - 160, y - 66), (x_right, y - 66)], fill=(255, 240, 235, 210), width=5)
    for line in lines:
        draw_line(img, d, line, font, x_right, y)
        y += lh


def make_image(post_id: str, text: str, theme: str, signature: str = "") -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    theme = (theme or DEFAULT_THEME).strip().lower()
    if theme not in FALLBACK:
        theme = DEFAULT_THEME

    img = apply_scrim(normalize_brightness(load_background(theme)))
    font, lines = fit_font(text)
    draw_block(img, lines, font)

    if signature:
        sig = ImageFont.truetype(FONT_REGULAR, 38)
        d = ImageDraw.Draw(img)
        cx, cy = W / 2, H - 118
        d.text((cx + 3, cy + 3), signature, font=sig, fill=(0, 0, 0, 150),
               anchor="ma", direction="ltr")
        d.text((cx, cy), signature, font=sig, fill=(255, 238, 232, 230),
               anchor="ma", direction="ltr")

    out = os.path.join(OUT_DIR, f"post_{post_id}.jpg")
    img.save(out, "JPEG", quality=92, optimize=True)
    return out


# ---------------------------------------------------------------- اجرا
def build_all(signature: str = "") -> int:
    with open(POSTS_CSV, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys()) if rows else []
    made = 0
    for row in rows:
        pid = row["id"].strip()
        rel = f"content/images/post_{pid}.jpg"
        if not os.path.exists(os.path.join(ROOT, rel)) or os.getenv("FORCE") == "1":
            make_image(pid, row["text"].strip(), row.get("theme", ""), signature)
            row["image"] = rel
            made += 1
            print(f"✅ تصویر ساخته شد: {rel}")
    if fields:
        with open(POSTS_CSV, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    if made == 0:
        print("ℹ️  همه‌ی پست‌ها تصویر دارند.")
    return made


def main() -> None:
    ap = argparse.ArgumentParser(description="ساخت تصویر پست")
    ap.add_argument("--id")
    ap.add_argument("--text")
    ap.add_argument("--theme", default=DEFAULT_THEME, choices=list(FALLBACK))
    ap.add_argument("--signature", default=os.getenv("PAGE_SIGNATURE", ""))
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    print(f"🔤 Raqm: {'فعال' if HAS_RAQM else 'غیرفعال'} | ایموجی: {len(_scan_emoji())//2} مورد")
    if args.all:
        build_all(args.signature)
    elif args.id and args.text:
        print("✅ ذخیره شد:", make_image(args.id, args.text, args.theme, args.signature))
    else:
        ap.error("یا --all بدهید، یا همزمان --id و --text")


if __name__ == "__main__":
    main()
