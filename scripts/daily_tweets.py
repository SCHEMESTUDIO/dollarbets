#!/usr/bin/env python3
"""
Dollar Bets — daily X posting agent for @dollarbetslol.

Modes:
  --mode run        The scheduled entry point. Ensures a queue exists for the
                    latest board (selecting with Claude if not), then posts the
                    next slot that hasn't gone out. Idempotent: run it as often
                    as you like, it never double-posts and never re-selects.
  --mode select     Pick the day's 3 cards and write the queue file. No posting.
  --mode post       Post one slot from the latest queue (--slot N, or "next").

The queue file at data/social-queue/YYYY-MM-DD.json (keyed by BOARD date, not
run date — the evening slot lands after midnight UTC) is the source of truth:
which 3 cards, what each post says, which slots have posted. Committed to git
as a public record. The Telegram rail reads the same file.

What a post looks like:
  parent  = the quip as the text, the 1080×1080 card as the image, no link
  reply   = the share link (link_mode "reply", the default)
X throttles posts carrying an external URL in the body; the link in a
self-reply keeps the parent eligible for For You and still carries the click.

Slot 3 is always the day's filthy little longshot, on the dark ticket card —
the same hero the board itself leads with.

Env vars:
  ANTHROPIC_API_KEY      required for selection
  X_API_KEY              X app consumer key   (required in LIVE mode)
  X_API_SECRET           X app consumer secret
  X_ACCESS_TOKEN         User-context access token for @dollarbetslol
  X_ACCESS_TOKEN_SECRET  User-context access token secret
  TWEET_LIVE             "1" to actually post. Anything else = dry-run (default).
  TWEET_LINK_MODE        "reply" (default) | "inline" | "none"
                           reply:  URL in a self-reply (2 posts, parent stays link-free)
                           inline: URL in the post body (1 post, throttled reach)
                           none:   no URL, rely on the card + bio link
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
SLOTS = 3

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Utilities ──────────────────────────────────────────────────────────────

def log(msg):
    print(f"[tweets] {msg}", file=sys.stderr)


def utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def safe_ticker(ticker: str) -> str:
    """Mirror generate.py's share-dir sanitization so image URLs line up."""
    s = re.sub(r"[^A-Za-z0-9_.\-]", "_", ticker or "")
    return s if s.strip(".") else ""


def format_payout(p) -> str:
    """Mirror generate.py's format_payout."""
    try:
        v = float(p)
    except (TypeError, ValueError):
        return "?"
    if v >= 1000:
        return f"${v:,.0f}"
    if v == int(v):
        return f"${int(v)}"
    return f"${v:.2f}"


def load_latest_board() -> tuple[str, dict]:
    """Return (date, board_data) for the most recent main-board JSON."""
    files = sorted(BOARDS_DIR.glob("2[0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9].json"))
    if not files:
        raise SystemExit("no main-board JSON files found in data/boards/")
    latest = files[-1]
    with open(latest) as f:
        return latest.stem, json.load(f)


def pick_longshot(board: list[dict]):
    """The board's own hero pick — generate.py owns the rule, we just call it."""
    sys.path.insert(0, str(ROOT))
    try:
        from generate import select_filthy_longshot
    except Exception as e:  # never let the site module break selection
        log(f"could not import select_filthy_longshot ({e}); no forced longshot")
        return None
    return select_filthy_longshot(board)


def load_anti_dupe_tickers() -> set[str]:
    """Tickers already queued in the last N days."""
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

SELECTION_PROMPT = """You are picking {n} cards from today's Dollar Bets board to post from @dollarbetslol on X.

Dollar Bets voice: dry, specific, slightly oblique. The reader is in on the joke. \
Drudge/Craigslist energy, not a polished startup. The quip already carries the voice — \
you're just picking which {n} are most postable, not rewriting them.

Each post is the quip as the text and a card image showing the market title and the \
payout. So the quip has to land as a standalone line above a picture of the wager.

What makes a card postable (in order of weight):
1. The quip lands on its own, without the title — it will sit above the card, not inside it
2. The market itself is weird/specific/culturally legible — something a stranger \
would screenshot or reply to
3. The payout is interesting (small odds = "wait that's cheap", large \
odds = "wait you'd pay that for a dollar?")
4. NOT a near-duplicate of recently posted markets (anti-dupe list below)

DO NOT pick cards where the quip is bland, the market is generic, or the topic \
overlaps recently-posted picks.

TODAY'S BOARD ({date}):
{markets}

RECENTLY POSTED (last {anti_dupe_days} days) — avoid topical near-duplicates:
{anti_dupe}

Return a JSON array of exactly {n} objects, ranked best-first:
[
  {{"ticker": "...", "rank": 1, "reason": "one short sentence on why this lands"}}{more}
]

Respond with ONLY the JSON array. Tickers must match exactly from the board above."""


def call_claude_for_selection(board: list[dict], date: str, anti_dupe: set[str], n: int) -> list[dict]:
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY not set — can't select")

    market_lines = []
    for i, m in enumerate(board, 1):
        market_lines.append(
            f"{i}. ticker={m.get('ticker')}\n"
            f"   title: {m.get('title','')}\n"
            f"   quip:  {m.get('quip','')}\n"
            f"   $1 pays {format_payout(m.get('payout'))}  | "
            f"platform={m.get('platform','?')} category={m.get('category','?')}"
        )

    anti_str = "\n".join(f"- {t}" for t in sorted(anti_dupe)) if anti_dupe else "(none yet)"
    more = "".join(f',\n  {{"ticker": "...", "rank": {k}, "reason": "..."}}' for k in range(2, n + 1))

    prompt = SELECTION_PROMPT.format(
        n=n, date=date, markets="\n\n".join(market_lines),
        anti_dupe=anti_str, anti_dupe_days=ANTI_DUPE_DAYS, more=more,
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

    log(f"calling Claude for {n} picks...")
    with urllib.request.urlopen(req, timeout=45) as resp:
        result = json.loads(resp.read().decode())
    text = result["content"][0]["text"].strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    picks = json.loads(text)
    if not isinstance(picks, list) or len(picks) != n:
        raise SystemExit(f"Claude returned {len(picks) if isinstance(picks, list) else 'non-list'} picks, expected {n}")

    valid_tickers = {m.get("ticker") for m in board}
    for p in picks:
        if p.get("ticker") not in valid_tickers:
            raise SystemExit(f"Claude picked ticker not on the board: {p.get('ticker')!r}")
    return picks


# ── Post text ──────────────────────────────────────────────────────────────

# X counts every URL as 23 chars (t.co shortening) regardless of real length.
TCO_LEN = 23
TWEET_MAX = 280


def share_url_for(market: dict, utm: bool = True) -> str:
    safe = safe_ticker(market.get("ticker", ""))
    url = f"{SITE_URL}/share/{safe}/"
    return url + "?utm_source=x&utm_medium=daily_card" if utm else url


def build_tweet_text(market: dict, link_mode: str) -> tuple[str, str | None]:
    """Return (main_text, reply_text_or_none).

    The card image carries the title and the payout, so the text is the quip
    alone. Saying the number twice reads as an ad; the quip alone reads as a
    person. Title is the fallback if a market has no quip.
    """
    quip = (market.get("quip") or "").strip()
    title = (market.get("title") or "").strip()
    body = quip or title
    if len(body) > TWEET_MAX:
        body = body[:TWEET_MAX - 1].rstrip() + "…"

    url = share_url_for(market)

    if link_mode == "inline":
        main = f"{body}\n\n{url}"
        if length_with_tco(main) > TWEET_MAX:
            cut = TWEET_MAX - (2 + TCO_LEN) - 1
            main = f"{body[:cut].rstrip()}…\n\n{url}"
        return main, None

    if link_mode == "reply":
        return body, f"the odds, and the rest of today’s board → {url}"

    return body, None


def length_with_tco(text: str) -> int:
    """Real X length: every URL counts as 23 chars."""
    urls = re.findall(r"https?://\S+", text)
    return len(text) - sum(len(u) for u in urls) + TCO_LEN * len(urls)


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


def build_queue_entry(market: dict, rank: int, reason: str, link_mode: str, variant: str) -> dict:
    main, reply = build_tweet_text(market, link_mode)
    safe = safe_ticker(market.get("ticker", ""))
    share_url = f"{SITE_URL}/share/{safe}/"
    return {
        "ticker": market.get("ticker"),
        "rank": rank,
        "selection_reason": reason,
        "title": market.get("title"),
        "quip": market.get("quip"),
        "payout": market.get("payout"),
        "platform": market.get("platform"),
        "tier": market.get("tier"),
        "card_variant": variant,                            # "tile" | "ticket"
        "share_url": share_url,
        "image_url": f"{SITE_URL}/share/{safe}/card.png",   # 1080×1080 post image
        "og_image_url": f"{SITE_URL}/share/{safe}/og.png",  # 1200×630 link preview
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


def queue_path(date: str) -> Path:
    return QUEUE_DIR / f"{date}.json"


def write_queue_file(date: str, payload: dict) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = queue_path(date)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    log(f"wrote queue file: {path}")
    return path


def read_queue_file(date: str) -> dict:
    path = queue_path(date)
    if not path.exists():
        raise SystemExit(f"no queue file for {date} — run --mode select first")
    return json.loads(path.read_text())


def latest_queue_date() -> str | None:
    if not QUEUE_DIR.exists():
        return None
    files = sorted(QUEUE_DIR.glob("2[0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9].json"))
    return files[-1].stem if files else None


def next_unposted_slot(queue: dict) -> int | None:
    for i, entry in enumerate(queue.get("selections", []), 1):
        if not entry.get("posts", {}).get("x", {}).get("posted"):
            return i
    return None


# ── X posting ──────────────────────────────────────────────────────────────

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


def post_tweet_live(text: str, image_path: Path | None, in_reply_to_id: str | None = None) -> str:
    """Post via tweepy. Returns the new tweet ID. Raises on failure."""
    import tweepy  # imported lazily so dry-runs don't need the dep

    api_key = os.environ["X_API_KEY"]
    api_secret = os.environ["X_API_SECRET"]
    access_token = os.environ["X_ACCESS_TOKEN"]
    access_secret = os.environ["X_ACCESS_TOKEN_SECRET"]

    # Media upload goes through v1.1 (OAuth 1.0a user context)
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
    api_v1 = tweepy.API(auth)
    media_id = None
    if image_path and image_path.exists():
        media = api_v1.media_upload(filename=str(image_path))
        media_id = media.media_id_string

    # Post creation uses v2
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
    """Post the Nth slot (1-indexed) from the queue for `date` to X."""
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
    link_mode = content.get("x_link_mode", "reply")
    if not tweet_text:
        raise SystemExit(f"slot {slot} missing content.x_tweet_text — queue file is malformed")

    live = os.environ.get("TWEET_LIVE") == "1"
    img_path = QUEUE_DIR / f"{date}-slot{slot}.png"
    if not download_image(entry["image_url"], img_path):
        raise SystemExit(f"slot {slot} image fetch failed — aborting post")

    print("=" * 60)
    print(f"SLOT {slot}  [X]  ({'LIVE' if live else 'DRY-RUN'})  card={entry.get('card_variant', '?')}")
    print(f"image: {entry['image_url']}  ({img_path.stat().st_size} bytes)")
    print(f"link mode: {link_mode}")
    print("-- post text --")
    print(tweet_text)
    print(f"-- length: {length_with_tco(tweet_text)} / {TWEET_MAX} --")
    if reply_text:
        print("-- reply text --")
        print(reply_text)
    print("=" * 60)

    if not live:
        log("TWEET_LIVE != 1 — not posting. Set TWEET_LIVE=1 to go live.")
        _safe_unlink(img_path)
        return

    tweet_id = post_tweet_live(tweet_text, img_path, in_reply_to_id=None)
    x_state["posted"] = True
    x_state["posted_at"] = datetime.now(timezone.utc).isoformat()
    x_state["tweet_id"] = tweet_id
    # Record the parent before attempting the reply, so a reply failure can't
    # leave a posted parent unrecorded (which would double-post next run).
    write_queue_file(date, queue)

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

def ensure_queue(link_mode: str) -> str:
    """Select for the latest board if no queue exists for it. Returns board date."""
    date, data = load_latest_board()
    if queue_path(date).exists():
        log(f"queue for board {date} already exists — not re-selecting")
        return date

    board = data.get("board", [])
    if len(board) < SLOTS:
        raise SystemExit(f"board only has {len(board)} markets — need at least {SLOTS}")

    anti_dupe = load_anti_dupe_tickers()
    log(f"board {date}: {len(board)} markets, anti-dupe set has {len(anti_dupe)} tickers")

    # Slot 3 is the board's own hero unless it went out in the last 14 days.
    hero_idx = pick_longshot(board)
    hero = board[hero_idx] if hero_idx is not None else None
    if hero and hero.get("ticker") in anti_dupe:
        log(f"longshot {hero.get('ticker')} already posted recently — Claude picks all {SLOTS}")
        hero = None

    pool = [m for m in board if m is not hero]
    n_claude = SLOTS - (1 if hero else 0)
    picks = call_claude_for_selection(pool, date, anti_dupe, n_claude)
    by_ticker = {m.get("ticker"): m for m in pool}

    selections = []
    for p in picks:
        selections.append(build_queue_entry(
            market=by_ticker[p["ticker"]], rank=p.get("rank"),
            reason=(p.get("reason") or "").strip(), link_mode=link_mode, variant="tile",
        ))
    if hero:
        selections.append(build_queue_entry(
            market=hero, rank=SLOTS,
            reason="today's filthy little longshot — the board's own hero pick",
            link_mode=link_mode, variant="ticket",
        ))

    write_queue_file(date, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "board_date": date,
        "link_mode": link_mode,
        "selections": selections,
    })
    for s in selections:
        log(f"  slot {s['rank']} [{s['card_variant']}]: {s['ticker']}  ({s['selection_reason']})")
    return date


def cmd_run(link_mode: str) -> None:
    date = ensure_queue(link_mode)
    queue = read_queue_file(date)
    slot = next_unposted_slot(queue)
    if slot is None:
        log(f"all {len(queue.get('selections', []))} slots for board {date} already posted — nothing to do")
        return
    post_slot(date, slot)


def cmd_post(date_arg: str | None, slot_arg: str) -> None:
    date = date_arg or latest_queue_date()
    if not date:
        raise SystemExit("no queue files yet — run --mode select first")
    if slot_arg == "next":
        slot = next_unposted_slot(read_queue_file(date))
        if slot is None:
            log(f"all slots for {date} already posted")
            return
    else:
        slot = int(slot_arg)
    post_slot(date, slot)


def main() -> None:
    p = argparse.ArgumentParser(description="Dollar Bets daily X poster")
    p.add_argument("--mode", choices=["run", "select", "post"], required=True)
    p.add_argument("--date", help="queue date (YYYY-MM-DD); default = latest queue file")
    p.add_argument("--slot", help='1-indexed slot, or "next"')
    p.add_argument("--link-mode", default=os.environ.get("TWEET_LINK_MODE", "reply"),
                   choices=["inline", "reply", "none"])
    args = p.parse_args()

    if args.mode == "run":
        cmd_run(args.link_mode)
    elif args.mode == "select":
        ensure_queue(args.link_mode)
    else:
        if not args.slot:
            raise SystemExit('--mode post requires --slot N or --slot next')
        cmd_post(args.date, args.slot)


if __name__ == "__main__":
    main()
