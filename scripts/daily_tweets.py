#!/usr/bin/env python3
"""
Dollar Bets — daily X/Twitter posting agent.

Two modes:
  --mode select     Pick 3 cards from today's board (with Claude), write queue file.
                    Also posts slot 1 if --post-slot 1 is passed.
  --mode post       Post a specific slot from today's queue file.

The queue file at data/social-queue/YYYY-MM-DD.json is the source of truth for
which 3 cards we picked, what the tweet text is, and which slots have already
posted. It's committed to git so we have a public record.

Env vars:
  ANTHROPIC_API_KEY      required for --mode select
  X_API_KEY              X app consumer key   (required in LIVE mode)
  X_API_SECRET           X app consumer secret
  X_ACCESS_TOKEN         User-context access token for the posting account
  X_ACCESS_TOKEN_SECRET  User-context access token secret
  TWEET_LIVE             "1" to actually post. Anything else = dry-run (default).
  TWEET_LINK_MODE        "inline" (default) | "reply" | "none"
                           inline: URL in tweet body (1 post, drives clicks)
                           reply:  URL in self-reply (2 posts, marginal reach gain)
                           none:   no URL, rely on image watermark + bio link
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # site/
BOARDS_DIR = ROOT / "data" / "boards"
QUEUE_DIR = ROOT / "data" / "social-queue"  # shared between X + Telegram
SITE_URL = "https://www.dollarbets.lol"
ANTI_DUPE_DAYS = 14

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Utilities ──────────────────────────────────────────────────────────────

def log(msg):
    print(f"[tweets] {msg}", file=sys.stderr)


def utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def safe_ticker(ticker: str) -> str:
    """Mirror generate.py's share-dir sanitization so OG image URLs line up."""
    s = re.sub(r"[^A-Za-z0-9_.\-]", "_", ticker or "")
    return s if s.strip(".") else ""


def format_payout(p) -> str:
    """Mirror generate.py's format_payout. $1 → $X.XX style."""
    try:
        v = float(p)
    except (TypeError, ValueError):
        return "?"
    if v >= 100:
        return f"${v:,.0f}"
    return f"${v:.2f}"


def load_latest_board() -> tuple[str, dict]:
    """Return (date, board_data) for the most recent main-board JSON."""
    files = sorted(BOARDS_DIR.glob("2[0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9].json"))
    if not files:
        raise SystemExit("no main-board JSON files found in data/boards/")
    latest = files[-1]
    date = latest.stem
    with open(latest) as f:
        return date, json.load(f)


def load_anti_dupe_tickers() -> set[str]:
    """Return tickers we've already tweeted in the last N days."""
    tickers: set[str] = set()
    if not QUEUE_DIR.exists():
        return tickers
    cutoff = datetime.now(timezone.utc) - timedelta(days=ANTI_DUPE_DAYS)
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            d = datetime.strptime(f.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if d < cutoff:
            continue
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        for s in data.get("selections", []):
            t = s.get("ticker")
            if t:
                tickers.add(t)
    return tickers


# ── Claude selection ───────────────────────────────────────────────────────

SELECTION_PROMPT = """You are picking 3 cards from today's Dollar Bets board to tweet from @dollarbets.

Dollar Bets voice: dry, specific, slightly oblique. The reader is in on the joke. \
Drudge/Craigslist energy, not a polished startup. The quip already carries the voice — \
you're just picking which 3 are most tweetable, not rewriting them.

What makes a card tweetable (in order of weight):
1. The quip lands on its own without needing a screenshot of the headline
2. The market itself is weird/specific/culturally legible — something a stranger \
   would screenshot or reply to
3. The payout is interesting (small odds = surprising "wait that's cheap", large \
   odds = "wait you'd pay that for a dollar?")
4. NOT a near-duplicate of recently tweeted markets (anti-dupe list below)

DO NOT pick cards where the quip is bland, the market is generic, or the topic \
overlaps recently-tweeted picks.

TODAY'S BOARD ({date}):
{markets}

RECENTLY TWEETED (last {anti_dupe_days} days) — avoid topical near-duplicates:
{anti_dupe}

Return a JSON array of exactly 3 objects, ranked best-first:
[
  {{"ticker": "...", "rank": 1, "reason": "one short sentence on why this lands"}},
  {{"ticker": "...", "rank": 2, "reason": "..."}},
  {{"ticker": "...", "rank": 3, "reason": "..."}}
]

Respond with ONLY the JSON array. Tickers must match exactly from the board above."""


def call_claude_for_selection(board: list[dict], date: str, anti_dupe: set[str]) -> list[dict]:
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY not set — can't run --mode select")

    market_lines = []
    for i, m in enumerate(board, 1):
        market_lines.append(
            f"{i}. ticker={m.get('ticker')}\n"
            f"   title: {m.get('title','')}\n"
            f"   quip:  {m.get('quip','')}\n"
            f"   $1 pays {format_payout(m.get('payout'))}  | "
            f"platform={m.get('platform','?')} category={m.get('category','?')}"
        )

    if anti_dupe:
        anti_str = "\n".join(f"- {t}" for t in sorted(anti_dupe))
    else:
        anti_str = "(none yet)"

    prompt = SELECTION_PROMPT.format(
        date=date,
        markets="\n\n".join(market_lines),
        anti_dupe=anti_str,
        anti_dupe_days=ANTI_DUPE_DAYS,
    )

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 800,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    log("calling Claude for selection...")
    with urllib.request.urlopen(req, timeout=45) as resp:
        result = json.loads(resp.read().decode())
    text = result["content"][0]["text"].strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    picks = json.loads(text)
    if not isinstance(picks, list) or len(picks) != 3:
        raise SystemExit(f"Claude returned {len(picks) if isinstance(picks, list) else 'non-list'} picks, expected 3")

    valid_tickers = {m.get("ticker") for m in board}
    for p in picks:
        if p.get("ticker") not in valid_tickers:
            raise SystemExit(f"Claude picked ticker not on the board: {p.get('ticker')!r}")
    return picks


# ── Tweet building ─────────────────────────────────────────────────────────

# X counts every URL as 23 chars (t.co shortening) regardless of real length.
TCO_LEN = 23
TWEET_MAX = 280


def build_tweet_text(market: dict, link_mode: str) -> tuple[str, str | None]:
    """Return (main_tweet_text, reply_tweet_text_or_none).

    link_mode:
      - "inline": URL in the main tweet body
      - "reply":  URL becomes a self-reply
      - "none":   no URL anywhere
    """
    ticker = market.get("ticker", "")
    quip = (market.get("quip") or "").strip()
    title = (market.get("title") or "").strip()
    payout = format_payout(market.get("payout"))

    safe = safe_ticker(ticker)
    share_url = f"{SITE_URL}/share/{safe}/?utm_source=x&utm_medium=daily_card"

    # Body without the URL — used as the main tweet in all modes
    body = f'"{quip}"\n\n$1 pays {payout} — {title}'

    if link_mode == "inline":
        main = f"{body}\n\n{share_url}"
        # Length budget: real string length minus URL length plus 23
        if length_with_tco(main) > TWEET_MAX:
            # Truncate the title until it fits; quip is sacred
            main = truncate_to_fit(body, share_url)
        return main, None

    if link_mode == "reply":
        main = body
        if len(main) > TWEET_MAX:
            main = truncate_body(quip, payout, title)
        reply = f"link: {share_url}"
        return main, reply

    # link_mode == "none"
    main = body
    if len(main) > TWEET_MAX:
        main = truncate_body(quip, payout, title)
    return main, None


def length_with_tco(text: str) -> int:
    """Real X length: every URL counts as 23 chars."""
    url_re = re.compile(r"https?://\S+")
    urls = url_re.findall(text)
    real_url_chars = sum(len(u) for u in urls)
    return len(text) - real_url_chars + TCO_LEN * len(urls)


def truncate_body(quip: str, payout: str, title: str) -> str:
    """Title is the only sacrificial part. Quip and payout always stay."""
    base = f'"{quip}"\n\n$1 pays {payout} — '
    budget = TWEET_MAX - len(base) - 1  # 1 for ellipsis
    if budget < 10:
        return base.rstrip(" —")  # quip + payout only
    return base + title[:budget].rstrip() + "…"


def truncate_to_fit(body: str, url: str) -> str:
    """Shrink body until body + \\n\\n + URL fits the 280-char tweet limit."""
    overhead = 2 + TCO_LEN  # \n\n + shortened url
    target = TWEET_MAX - overhead
    if len(body) <= target:
        return f"{body}\n\n{url}"
    # Find last ' — ' and trim the title after it
    if " — " in body:
        head, tail = body.rsplit(" — ", 1)
        budget = target - len(head) - len(" — ") - 1
        if budget >= 10:
            return f"{head} — {tail[:budget].rstrip()}…\n\n{url}"
    # Last resort: hard cut
    return f"{body[:target-1].rstrip()}…\n\n{url}"


# ── Queue file management ──────────────────────────────────────────────────

def build_telegram_caption_html(market: dict, share_url: str) -> str:
    """Telegram caption — HTML mode. Max 1024 chars, but we stay well under.

    Telegram HTML mode only supports: <b> <i> <u> <s> <a> <code> <pre>
    Anything else must be HTML-escaped. Title + quip come from external APIs and
    AI generation, so always escape — never trust them as safe HTML.
    """
    import html as _html
    title = _html.escape((market.get("title") or "").strip())
    quip = _html.escape((market.get("quip") or "").strip())
    payout = format_payout(market.get("payout"))
    return (
        f"<b>{title}</b>\n\n"
        f"“<i>{quip}</i>”\n\n"
        f"$1 pays {payout}\n\n"
        f"<a href=\"{share_url}\">see the card →</a>"
    )


def build_queue_entry(market: dict, rank: int, reason: str, link_mode: str) -> dict:
    main, reply = build_tweet_text(market, link_mode)
    safe = safe_ticker(market.get("ticker", ""))
    share_url = f"{SITE_URL}/share/{safe}/"
    image_url = f"{SITE_URL}/share/{safe}/og.png"
    return {
        "ticker": market.get("ticker"),
        "rank": rank,
        "selection_reason": reason,
        "title": market.get("title"),
        "quip": market.get("quip"),
        "payout": market.get("payout"),
        "platform": market.get("platform"),
        "share_url": share_url,
        "image_url": image_url,
        # Pre-rendered content per channel, locked at selection time so the
        # queue file is a complete audit log of what's planned.
        "content": {
            "x_tweet_text": main,
            "x_reply_text": reply,
            "x_link_mode": link_mode,
            "telegram_caption_html": build_telegram_caption_html(market, share_url),
        },
        # Per-platform post state. Each platform updates only its own slot.
        "posts": {
            "x": {"posted": False, "posted_at": None, "tweet_id": None, "reply_tweet_id": None},
            "telegram_channel": {"posted": False, "posted_at": None, "message_id": None},
            "telegram_group": {"posted": False, "posted_at": None, "message_id": None},
        },
    }


def write_queue_file(date: str, payload: dict) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"{date}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    log(f"wrote queue file: {path}")
    return path


def read_queue_file(date: str) -> dict:
    path = QUEUE_DIR / f"{date}.json"
    if not path.exists():
        raise SystemExit(f"no queue file for {date} — run --mode select first")
    return json.loads(path.read_text())


# ── X / Twitter posting ────────────────────────────────────────────────────

def download_image(url: str, dest: Path) -> bool:
    log(f"downloading image: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "dollarbets-tweet-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        log(f"image fetch HTTP {e.code} for {url}")
        return False
    except Exception as e:
        log(f"image fetch failed ({type(e).__name__}): {e}")
        return False
    if not data or len(data) < 1000:
        log(f"image payload too small ({len(data)} bytes) — refusing to post")
        return False
    # PNG magic bytes — refuse anything else (e.g. a 200-disguised HTML 404 page)
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        log(f"image payload not a PNG (first bytes {data[:8]!r}) — refusing to post")
        return False
    dest.write_bytes(data)
    return True


def post_tweet_live(text: str, image_path: Path, in_reply_to_id: str | None = None) -> str:
    """Post via tweepy. Returns the new tweet ID. Raises on failure."""
    import tweepy  # imported lazily so dry-runs don't need the dep

    api_key = os.environ["X_API_KEY"]
    api_secret = os.environ["X_API_SECRET"]
    access_token = os.environ["X_ACCESS_TOKEN"]
    access_secret = os.environ["X_ACCESS_TOKEN_SECRET"]

    # Media upload still goes through v1.1 auth (OAuth 1.0a user context)
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
    api_v1 = tweepy.API(auth)
    media_id = None
    if image_path and image_path.exists():
        media = api_v1.media_upload(filename=str(image_path))
        media_id = media.media_id_string

    # Tweet creation uses v2
    client = tweepy.Client(
        consumer_key=api_key, consumer_secret=api_secret,
        access_token=access_token, access_token_secret=access_secret,
    )
    kwargs = {"text": text}
    if media_id:
        kwargs["media_ids"] = [media_id]
    if in_reply_to_id:
        kwargs["in_reply_to_tweet_id"] = in_reply_to_id

    resp = client.create_tweet(**kwargs)
    tid = resp.data["id"]
    log(f"posted tweet id={tid}")
    return str(tid)


def post_slot(date: str, slot: int) -> None:
    """Post the Nth slot (1-indexed) from today's queue to X."""
    queue = read_queue_file(date)
    selections = queue.get("selections", [])
    if slot < 1 or slot > len(selections):
        raise SystemExit(f"slot {slot} out of range (queue has {len(selections)} entries)")
    entry = selections[slot - 1]
    x_state = entry.setdefault("posts", {}).setdefault("x", {})
    if x_state.get("posted"):
        log(f"slot {slot} already posted to X (id={x_state.get('tweet_id')}) — skipping")
        return

    content = entry.get("content", {})
    tweet_text = content.get("x_tweet_text")
    reply_text = content.get("x_reply_text")
    link_mode = content.get("x_link_mode", "inline")
    if not tweet_text:
        raise SystemExit(f"slot {slot} missing content.x_tweet_text — queue file is malformed")

    live = os.environ.get("TWEET_LIVE") == "1"
    img_path = QUEUE_DIR / f"{date}-slot{slot}.png"
    image_ok = download_image(entry["image_url"], img_path)
    if not image_ok:
        raise SystemExit(f"slot {slot} image fetch failed — aborting post")

    print("=" * 60)
    print(f"SLOT {slot}  [X]  ({'LIVE' if live else 'DRY-RUN'})")
    print(f"image: {entry['image_url']}  ({img_path.stat().st_size} bytes)")
    print(f"link mode: {link_mode}")
    print("-- tweet text --")
    print(tweet_text)
    print(f"-- length: {length_with_tco(tweet_text)} / {TWEET_MAX} --")
    if reply_text:
        print("-- reply text --")
        print(reply_text)
    print("=" * 60)

    if not live:
        log("TWEET_LIVE != 1 — not posting. Run with TWEET_LIVE=1 to go live.")
        _safe_unlink(img_path)
        return

    tweet_id = post_tweet_live(tweet_text, img_path, in_reply_to_id=None)
    x_state["posted"] = True
    x_state["posted_at"] = datetime.now(timezone.utc).isoformat()
    x_state["tweet_id"] = tweet_id

    if reply_text:
        reply_id = post_tweet_live(reply_text, None, in_reply_to_id=tweet_id)
        x_state["reply_tweet_id"] = reply_id

    write_queue_file(date, queue)
    _safe_unlink(img_path)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"could not clean up {path}: {e}")


# ── Top-level commands ─────────────────────────────────────────────────────

def cmd_select(date_arg: str | None, link_mode: str, also_post_slot: int | None) -> None:
    date, data = load_latest_board()
    if date_arg and date_arg != date:
        log(f"warning: requested {date_arg} but latest board is {date}; using {date}")

    board = data.get("board", [])
    if len(board) < 3:
        raise SystemExit(f"board only has {len(board)} markets — need at least 3 to pick from")

    anti_dupe = load_anti_dupe_tickers()
    log(f"loaded {len(board)} markets, anti-dupe set has {len(anti_dupe)} tickers")

    picks = call_claude_for_selection(board, date, anti_dupe)
    by_ticker = {m.get("ticker"): m for m in board}

    selections = []
    for p in picks:
        m = by_ticker[p["ticker"]]
        selections.append(build_queue_entry(
            market=m,
            rank=p.get("rank"),
            reason=(p.get("reason") or "").strip(),
            link_mode=link_mode,
        ))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "board_date": date,
        "link_mode": link_mode,
        "selections": selections,
    }
    write_queue_file(date, payload)
    for s in selections:
        log(f"  rank {s['rank']}: {s['ticker']}  ({s['selection_reason']})")

    if also_post_slot:
        post_slot(date, also_post_slot)


def cmd_post(date_arg: str | None, slot: int) -> None:
    date = date_arg or utc_today()
    post_slot(date, slot)


def main() -> None:
    p = argparse.ArgumentParser(description="Dollar Bets daily X poster")
    p.add_argument("--mode", choices=["select", "post"], required=True)
    p.add_argument("--date", help="YYYY-MM-DD (defaults to UTC today)")
    p.add_argument("--slot", type=int, help="1-indexed slot (1, 2, or 3)")
    p.add_argument("--also-post-slot", type=int,
                   help="In select mode, also post this slot after selecting")
    p.add_argument("--link-mode", default=os.environ.get("TWEET_LINK_MODE", "inline"),
                   choices=["inline", "reply", "none"])
    args = p.parse_args()

    if args.mode == "select":
        cmd_select(args.date, args.link_mode, args.also_post_slot)
    else:
        if not args.slot:
            raise SystemExit("--mode post requires --slot")
        cmd_post(args.date, args.slot)


if __name__ == "__main__":
    main()
