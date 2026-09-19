#!/usr/bin/env python3
"""
Dollar Bets — square share cards for social posts (1080×1080).

Two variants, mirroring how the board itself presents a market:

  "tile"    — the light tinted ticket. Standard board pick. Tier wash + left
              bar carry the odds colour system; the payout is the hook.
  "ticket"  — the dark hero ticket. Today's filthy little longshot. One a day.

generate.py renders one per market at build time into
public/share/{ticker}/card.png, next to the 1200×630 og.png (which stays:
that one is the link preview, this one is the post attachment).

Fonts: Archivo (variable) + IBM Plex Mono, fetched by build.sh into .fonts/.
If they are missing the renderer falls back to the DejaVu files the OG image
already needs, so a font download failure degrades the look, not the build.

Local test:
  python3 share_card.py --board data/boards/2026-08-26.json --out /tmp/cards
"""

import os
import re
from datetime import datetime

W = H = 1080

# Palette — the site's own tokens (generate.py CSS), not new ones.
PAPER = "#fdf6ee"
INK = "#2d2319"
INK_2 = "#806b5b"
INK_3 = "#a08b77"
RULE = "#e8cdb5"
RULE_DASH = "#d9c3ad"
ORANGE = "#e8642c"
DARK_RULE = "#5a4e3f"
DARK_MUTE = "#b7a894"
DARK_MUTE_2 = "#857662"
LAVENDER = "#c9a2ec"

TIERS = {
    #          left bar    wash        ink (light)  bright (dark)
    "green":  ("#4caf50", "#f2f9f0", "#2e7d32", "#7ee2a1"),
    "yellow": ("#e6c731", "#fdf9e8", "#a08508", "#f3df6a"),
    "orange": ("#d06a1a", "#fdf2e7", "#c05a10", "#ffa45c"),
    "red":    ("#e05252", "#fdf0ef", "#c73e3e", "#ff8a8a"),
    "purple": ("#9c5ec7", "#f8f2fc", "#8546b3", "#d3a4f5"),
}
TIER_DEFAULT = ("#806b5b", "#ffffff", "#237a3f", "#7ee2a1")

PLATFORM_NAMES = {
    "kalshi": "Kalshi", "polymarket": "Polymarket", "fanduel": "FanDuel",
    "draftkings": "DraftKings", "betmgm": "BetMGM", "betrivers": "BetRivers",
}


# ── Fonts ──────────────────────────────────────────────────────────────────

class _Fonts:
    """Lazy font factory. Archivo is a variable font: one file, any weight."""

    def __init__(self, fonts_dir):
        from PIL import ImageFont
        self._IF = ImageFont
        self.dir = fonts_dir
        self.archivo_vf = self._first("Archivo-VF.ttf")
        self.mono_regular = self._first("IBMPlexMono-Regular.ttf", "DejaVuSansMono.ttf")
        self.mono_semibold = self._first("IBMPlexMono-SemiBold.ttf", "DejaVuSansMono-Bold.ttf")
        self.display_fallback = self._first("DejaVuSerif-Bold.ttf")
        self.ok = bool((self.archivo_vf or self.display_fallback) and self.mono_regular)

    def _first(self, *names):
        for n in names:
            p = os.path.join(self.dir, n)
            if os.path.exists(p):
                return p
        return None

    def display(self, size, weight=700):
        if self.archivo_vf:
            f = self._IF.truetype(self.archivo_vf, size)
            try:
                f.set_variation_by_axes([weight, 100])  # [Weight, Width]
            except Exception:
                pass
            return f
        return self._IF.truetype(self.display_fallback, size)

    def mono(self, size, semibold=False):
        path = self.mono_semibold if semibold else self.mono_regular
        return self._IF.truetype(path or self.mono_regular, size)


# ── Drawing helpers ────────────────────────────────────────────────────────

def _text_w(draw, text, font):
    return draw.textlength(text, font=font)


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if _text_w(draw, trial, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_title(draw, text, fonts, max_w, sizes=(68, 60, 52), max_lines=4):
    """Largest size at which the title wraps within max_lines."""
    for s in sizes:
        f = fonts.display(s, 700)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, s
    f = fonts.display(sizes[-1], 700)
    lines = _wrap(draw, text, f, max_w)[:max_lines]
    lines[-1] = lines[-1].rstrip() + "…"
    return f, lines, sizes[-1]


def _draw_tracked(draw, xy, text, font, fill, tracking, anchor_right=False, baseline=False):
    """Draw text with manual letter-spacing (Pillow has none). Returns width.
    baseline=True anchors y on the baseline instead of the top of the box, so
    mixed sizes can sit on one line."""
    widths = [_text_w(draw, ch, font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if anchor_right:
        x = x - total
    anchor = "ls" if baseline else "la"
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        x += w + tracking
    return total


def _tracked_w(draw, text, font, tracking):
    return sum(_text_w(draw, ch, font) for ch in text) + tracking * (len(text) - 1)


def _fit_payout(draw, fonts, payout_str, base, avail, floor=110):
    """Shrink the payout until it fits beside the meta column."""
    size = _payout_size(payout_str, base)
    while size > floor:
        f = fonts.display(size, 900)
        if _tracked_w(draw, payout_str, f, -0.03 * size) <= avail:
            break
        size -= 8
    return fonts.display(size, 900), size


def _dashed_h(draw, x0, x1, y, fill, width=2, on=12, off=8):
    x = x0
    while x < x1:
        draw.line([(x, y), (min(x + on, x1), y)], fill=fill, width=width)
        x += on + off


def _payout_size(payout_str, base):
    n = len(payout_str)
    if n <= 5:
        return base
    if n == 6:
        return int(base * 0.85)
    return int(base * 0.70)


def _wordmark(draw, fonts, x, y, ink):
    f = fonts.display(44, 900)
    w = _draw_tracked(draw, (x, y), "DOLLAR", f, ink, -1.5)
    _draw_tracked(draw, (x + w - 1.5, y), "BETS", f, ORANGE, -1.5)


def format_payout(payout):
    """Mirror generate.py — $1 → $X.XX, whole dollars bare, thousands grouped."""
    try:
        v = float(payout)
    except (TypeError, ValueError):
        return "?"
    if v >= 1000:
        return f"${v:,.0f}"
    if v == int(v):
        return f"${int(v)}"
    return f"${v:.2f}"


def _priced_in(payout):
    try:
        v = float(payout)
    except (TypeError, ValueError):
        return ""
    if v <= 0:
        return ""
    return "<1%" if v >= 100 else f"{round(100 / v)}%"


def _stamp(board_date):
    try:
        d = datetime.strptime(board_date, "%Y-%m-%d")
        return f"today’s board · {d.strftime('%b')} {d.day}".lower()
    except (TypeError, ValueError):
        return "today’s board"


# ── Variants ───────────────────────────────────────────────────────────────

def _render_tile(img, draw, fonts, m, board_date):
    bar, wash, ink_tier, _ = TIERS.get(m.get("tier", ""), TIER_DEFAULT)
    pad, r, barw = 0, 0, 16   # full bleed: X frames and rounds the image itself
    box = (pad, pad, W - pad, H - pad)

    # Tier bar under a wash panel offset by the bar width — same shape a CSS
    # border-left + border-radius produces on the site.
    draw.rounded_rectangle(box, radius=r, fill=bar)
    draw.rounded_rectangle((pad + barw, pad, W - pad, H - pad), radius=r, fill=wash)
    draw.rounded_rectangle(box, radius=r, outline=RULE, width=3)

    x0 = pad + barw + 64          # content left
    x1 = W - pad - 64             # content right
    y = pad + 60

    # Head: wordmark + date stamp
    _wordmark(draw, fonts, x0, y, INK)
    f_stamp = fonts.mono(22, semibold=True)
    _draw_tracked(draw, (x1, y + 12), _stamp(board_date), f_stamp, INK_2, 1, anchor_right=True)

    # Title
    y += 44 + 64
    f_title, lines, size = _fit_title(draw, m.get("title", ""), fonts, x1 - x0)
    lh = int(size * 1.12)
    for ln in lines:
        _draw_tracked(draw, (x0, y), ln, f_title, INK, -1.5)
        y += lh

    # Bottom block, built upward from the tile's bottom edge
    f_foot = fonts.mono(24)
    foot_y = H - pad - 56 - 30
    draw.text((x0, foot_y), "dollarbets.lol", font=f_foot, fill=INK_3)
    _draw_tracked(draw, (x1, foot_y), "what does a dollar pay?", f_foot, INK_3, 0, anchor_right=True)
    rule_y = foot_y - 28
    _dashed_h(draw, x0, x1, rule_y, RULE_DASH)

    # Meta column first, so the payout can be sized to the room left beside it
    f_meta = fonts.mono(24, semibold=True)
    platform = m.get("platform", "kalshi") or "kalshi"
    pname = PLATFORM_NAMES.get(platform, platform.title())
    line1 = pname + (" · CFTC-regulated" if platform == "kalshi" else "")
    pi = _priced_in(m.get("payout", 0))
    line2 = f"{pi} chance priced in" if pi else ""
    meta_w = max(_text_w(draw, line1, f_meta), _text_w(draw, line2, f_meta) if line2 else 0)

    payout_str = format_payout(m.get("payout", 0))
    base_y = rule_y - 40                      # payout baseline
    f_pay, psize = _fit_payout(draw, fonts, payout_str, 200, (x1 - x0) - meta_w - 32)
    _draw_tracked(draw, (x0, base_y), payout_str, f_pay, ink_tier, -0.03 * psize, baseline=True)
    cap_top = f_pay.getbbox("0", anchor="ls")[1]   # negative: distance above baseline

    f_label = fonts.mono(28, semibold=True)   # a step above the other small text
    _draw_tracked(draw, (x0, base_y + cap_top - 28 - 16), "$1 PAYS", f_label, INK_2, 4)

    if line2:
        _draw_tracked(draw, (x1, base_y - 6), line2, f_meta, INK_2, 0, anchor_right=True, baseline=True)
        _draw_tracked(draw, (x1, base_y - 42), line1, f_meta, INK_2, 0, anchor_right=True, baseline=True)
    else:
        _draw_tracked(draw, (x1, base_y - 6), line1, f_meta, INK_2, 0, anchor_right=True, baseline=True)


def _render_ticket(img, draw, fonts, m, board_date):
    _, _, _, bright = TIERS.get(m.get("tier", ""), TIER_DEFAULT)
    pad, r = 0, 0   # full bleed: X frames and rounds the image itself
    draw.rounded_rectangle((pad, pad, W - pad, H - pad), radius=r, fill=INK)

    # Notches at 60% height, like the hero ticket on the board
    ny = pad + int((H - 2 * pad) * 0.60)
    for cx in (pad, W - pad):
        draw.ellipse((cx - 22, ny - 22, cx + 22, ny + 22), fill=PAPER)

    x0 = pad + 64
    x1 = W - pad - 64
    y = pad + 64

    _wordmark(draw, fonts, x0, y, PAPER)
    f_stamp = fonts.mono(22, semibold=True)
    _draw_tracked(draw, (x1, y + 12), _stamp(board_date), f_stamp, DARK_MUTE_2, 1, anchor_right=True)

    y += 44 + 56
    f_lab = fonts.mono(22, semibold=True)
    _draw_tracked(draw, (x0, y), "TODAY’S FILTHY LITTLE LONGSHOT", f_lab, LAVENDER, 5)

    y += 22 + 28
    f_title, lines, size = _fit_title(draw, m.get("title", ""), fonts, x1 - x0)
    lh = int(size * 1.12)
    for ln in lines:
        _draw_tracked(draw, (x0, y), ln, f_title, PAPER, -1.5)
        y += lh

    # Bottom block upward
    f_foot = fonts.mono(24)
    foot_y = H - pad - 64 - 30
    draw.text((x0, foot_y), "dollarbets.lol", font=f_foot, fill=DARK_MUTE_2)
    _draw_tracked(draw, (x1, foot_y), "what does a dollar pay?", f_foot, DARK_MUTE_2, 0, anchor_right=True)

    f_meta = fonts.mono(24, semibold=True)
    platform = m.get("platform", "kalshi") or "kalshi"
    pname = PLATFORM_NAMES.get(platform, platform.title())
    pi = _priced_in(m.get("payout", 0))
    line2 = f"{pi} priced in" if pi else ""
    meta_w = max(_text_w(draw, pname, f_meta), _text_w(draw, line2, f_meta) if line2 else 0)

    f_pays = fonts.mono(30, semibold=True)
    pays_w = _text_w(draw, "$1 pays", f_pays)
    payout_str = format_payout(m.get("payout", 0))
    base_y = foot_y - 46                      # shared baseline for the row
    avail = (x1 - x0) - pays_w - 24 - meta_w - 32
    f_pay, psize = _fit_payout(draw, fonts, payout_str, 180, avail)

    draw.text((x0, base_y), "$1 pays", font=f_pays, fill=DARK_MUTE, anchor="ls")
    _draw_tracked(draw, (x0 + pays_w + 24, base_y), payout_str, f_pay, bright, -0.03 * psize, baseline=True)
    if line2:
        _draw_tracked(draw, (x1, base_y - 6), line2, f_meta, DARK_MUTE_2, 0, anchor_right=True, baseline=True)
        _draw_tracked(draw, (x1, base_y - 42), pname, f_meta, DARK_MUTE_2, 0, anchor_right=True, baseline=True)
    else:
        _draw_tracked(draw, (x1, base_y - 6), pname, f_meta, DARK_MUTE_2, 0, anchor_right=True, baseline=True)

    cap_top = f_pay.getbbox("0", anchor="ls")[1]
    rule_y = base_y + cap_top - 40
    _dashed_h(draw, x0, x1, rule_y, DARK_RULE, width=3)


# ── Public API ─────────────────────────────────────────────────────────────

def render_card(market, variant, output_path, board_date="", fonts_dir=None):
    """Render one 1080×1080 card. Returns True on success, False if fonts or
    Pillow are unavailable (caller falls back to no card, never a broken one)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[share_card] WARNING: Pillow not installed, skipping card")
        return False

    fonts_dir = fonts_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fonts")
    fonts = _Fonts(fonts_dir)
    if not fonts.ok:
        print(f"[share_card] WARNING: no usable fonts in {fonts_dir}, skipping card")
        return False

    img = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)
    if variant == "ticket":
        _render_ticket(img, draw, fonts, market, board_date)
    else:
        _render_tile(img, draw, fonts, market, board_date)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    return True


def safe_ticker(ticker):
    """Same sanitisation generate.py applies to the share directory name."""
    s = re.sub(r"[^A-Za-z0-9_.\-]", "_", ticker or "")
    return s if s.strip(".") else ""


if __name__ == "__main__":
    import argparse
    import json
    import sys

    p = argparse.ArgumentParser(description="Render Dollar Bets share cards from a board JSON")
    p.add_argument("--board", required=True, help="data/boards/YYYY-MM-DD.json")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--fonts", default=None, help="fonts dir (default: ./.fonts)")
    args = p.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from generate import select_filthy_longshot

    with open(args.board) as f:
        data = json.load(f)
    board = data.get("board", [])
    date = os.path.basename(args.board)[:-5]
    hero = select_filthy_longshot(board)
    for i, m in enumerate(board):
        st = safe_ticker(m.get("ticker", ""))
        if not st:
            continue
        variant = "ticket" if i == hero else "tile"
        out = os.path.join(args.out, f"{st}.{variant}.png")
        ok = render_card(m, variant, out, board_date=date, fonts_dir=args.fonts)
        print(("ok   " if ok else "FAIL ") + out)
