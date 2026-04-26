#!/usr/bin/env python3
"""
Dollar Bets — Kalshi Market Scanner (v2: Events-first approach)
1. Fetch all events from Kalshi (titles, categories)
2. Score events for entertainment value
3. Fetch markets for top candidates to get prices
4. Calculate $1 payouts, pick the daily board
"""

import json
import os
import re
import sys
import hashlib
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TARGET_PICKS = 10


# ── API helpers ──────────────────────────────────────────────

def _api_get(path, params=None):
    """Make a GET request to Kalshi's public API."""
    url = f"{KALSHI_API}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        url += f"?{qs}"

    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "DollarBets/1.0"
    })

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[scanner] Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"[scanner] API error: {e} ({url})", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            print(f"[scanner] API error: {e} ({url})", file=sys.stderr)
            return None


def fetch_all_events():
    """Fetch all open events (lightweight — just titles and categories)."""
    all_events = []
    cursor = None

    while True:
        params = {"limit": "200", "status": "open"}
        if cursor:
            params["cursor"] = cursor

        data = _api_get("/events", params)
        if not data:
            break

        events = data.get("events", [])
        all_events.extend(events)

        print(f"[scanner] Events page: {len(events)} (total: {len(all_events)})", file=sys.stderr)

        cursor = data.get("cursor")
        if not cursor or len(events) < 200:
            break

    return all_events


def fetch_markets_for_event(event_ticker):
    """Fetch markets for a specific event."""
    data = _api_get("/markets", {"event_ticker": event_ticker, "limit": "10"})
    if not data:
        return []
    return data.get("markets", [])


# ── Payout calculation ───────────────────────────────────────

def calc_payout(market):
    """
    Calculate what $1 pays out on the YES side.
    Kalshi prices are dollar strings: "0.05" = 5 cents.
    $1 / $0.05 = $20 payout.
    """
    price_str = market.get("yes_ask_dollars") or market.get("last_price_dollars") or "0"
    try:
        price = float(price_str)
    except (ValueError, TypeError):
        return None

    if price <= 0 or price >= 1.0:
        return None

    return round(1.0 / price, 2)


def payout_tier(payout):
    if payout is None:
        return None
    if payout <= 5:
        return "green"
    elif payout <= 10:
        return "yellow"
    elif payout <= 100:
        return "orange"
    elif payout <= 1000:
        return "red"
    else:
        return "purple"


# ── Event scoring ────────────────────────────────────────────

def score_event(event):
    """Score an event for how entertaining/shareable it is."""
    score = 0.0
    title = (event.get("title") or "").lower()
    subtitle = (event.get("sub_title") or "").lower()
    category = (event.get("category") or "").lower()
    full_text = f"{title} {subtitle}"

    # Category bonuses
    fun_categories = ["entertainment", "culture", "science", "climate", "weather",
                      "sports", "tech", "crypto", "world"]
    boring_categories = ["fed", "treasury", "gdp", "inflation", "interest rate",
                         "economics", "financial"]

    for cat in fun_categories:
        if cat in category:
            score += 15
            break

    for cat in boring_categories:
        if cat in category:
            score -= 15
            break

    # Viral keyword bonuses
    viral_keywords = ["elon", "trump", "taylor swift", "bitcoin", "snow",
                      "earthquake", "ufo", "alien", "ai", "robot",
                      "tiktok", "record", "first", "ever", "celebrity",
                      "kanye", "drake", "super bowl", "oscar", "grammy",
                      "olympics", "mars", "moon", "asteroid", "pope",
                      "viral", "meme", "scandal", "hurricane", "volcano",
                      "spacex", "tesla", "apple", "google", "netflix",
                      "nuclear", "war", "peace", "extinct", "banned"]
    for kw in viral_keywords:
        if kw in full_text:
            score += 10
            break

    # Title quality: shorter, punchier titles are better
    if len(title) < 50:
        score += 10
    elif len(title) < 80:
        score += 5
    elif len(title) > 120:
        score -= 10

    # Question marks are engaging
    if "?" in title:
        score += 5

    # Penalize very dry/technical titles
    dry_keywords = ["basis points", "yield curve", "quarterly", "index",
                    "benchmark", "fiscal", "monetary", "regulatory"]
    for kw in dry_keywords:
        if kw in full_text:
            score -= 15
            break

    return score


# ── Quip generation ──────────────────────────────────────────

def generate_quip(title, category):
    """Generate a short, funny editorial quip for a market."""
    title_lower = title.lower()
    category_lower = category.lower()

    quip_pools = {
        "weather": [
            "emotionally correct", "the weather app is lying again",
            "dress accordingly", "mother nature's got range",
            "pack an umbrella and a prayer",
        ],
        "crypto": [
            "number go up technology", "your uber driver called it",
            "laser eyes optional", "the chart looks like a heartbeat",
            "hodl or fold",
        ],
        "politic": [
            "democracy is a spectator sport", "the timeline is undefeated",
            "certified popcorn moment", "stranger than fiction, again",
            "cable news will be unwatchable",
        ],
        "election": [
            "democracy is a spectator sport", "certified popcorn moment",
            "the timeline is undefeated", "stranger than fiction, again",
        ],
        "entertainment": [
            "the culture demands it", "manifesting on main",
            "the stans already know", "this is the timeline we chose",
            "emotionally invested",
        ],
        "sport": [
            "analytics vs. vibes", "sports are scripted anyway",
            "the math checks out, barely", "your bracket is already busted",
            "just for the group chat",
        ],
        "tech": [
            "the future is now, apparently", "silicon valley is at it again",
            "this timeline is cooked", "the algorithm provides",
            "move fast, bet things",
        ],
        "science": [
            "peer-reviewed chaos", "nature doesn't care about your plans",
            "science is just spicy guessing", "the data is concerning",
            "statistically improbable, emotionally certain",
        ],
        "climate": [
            "emotionally correct", "the planet is running a fever",
            "nature doesn't negotiate", "the data is concerning",
        ],
        "world": [
            "stranger than fiction", "the timeline is undefeated",
            "you can't make this up", "history doesn't repeat but it rhymes",
        ],
    }

    default_pool = [
        "emotionally correct", "just for lols", "comedy listing",
        "it's happened before and it'll happen again",
        "the vibes are off but the math works",
        "this is not financial advice, it's a dare",
        "chaos theory in action", "the universe has a sense of humor",
        "stranger things have happened", "you heard it here first",
        "respectable nonsense", "annoyingly plausible",
        "the market has spoken", "bet with your heart, lose with your wallet",
    ]

    # Keyword overrides
    if "elon" in title_lower or "musk" in title_lower:
        pool = ["the main character of the internet", "posting through it",
                "this man does not sleep", "elon being elon"]
    elif "trump" in title_lower:
        pool = ["certified popcorn moment", "the timeline is undefeated",
                "stranger than fiction, again", "democracy in 4K"]
    elif "taylor" in title_lower or "swift" in title_lower:
        pool = ["the swifties already know", "manifesting on main",
                "emotionally devastating if true", "she planned this"]
    elif "bitcoin" in title_lower or "btc" in title_lower:
        pool = ["number go up technology", "your uber driver called it",
                "the chart has a plan"]
    elif "mars" in title_lower:
        pool = ["the red planet awaits", "elon's working on it",
                "one small bet for man", "space is the place"]
    elif "pope" in title_lower:
        pool = ["holy speculation", "the conclave vibes are immaculate",
                "white smoke or cope"]
    elif "snow" in title_lower or "rain" in title_lower:
        pool = ["emotionally correct", "the weather app is lying again",
                "dress accordingly", "nature doesn't negotiate"]
    elif "california" in title_lower:
        pool = ["the golden state of denial", "only in california",
                "the vibes are seismic"]
    else:
        # Match by category
        pool = default_pool
        for key in quip_pools:
            if key in category_lower or key in title_lower:
                pool = quip_pools[key]
                break

    # Deterministic pick based on title hash
    h = int(hashlib.md5(title.encode()).hexdigest(), 16)
    return pool[h % len(pool)]


ALL_QUIPS = [
    "emotionally correct", "just for lols", "comedy listing",
    "it's happened before and it'll happen again",
    "the vibes are off but the math works",
    "this is not financial advice, it's a dare",
    "chaos theory in action", "the universe has a sense of humor",
    "stranger things have happened", "you heard it here first",
    "respectable nonsense", "annoyingly plausible",
    "the market has spoken", "bet with your heart, lose with your wallet",
    "the timeline is undefeated", "certified popcorn moment",
    "the culture demands it", "manifesting on main",
    "the future is now, apparently", "the algorithm provides",
    "peer-reviewed chaos", "the data is concerning",
    "nature doesn't care about your plans", "analytics vs. vibes",
    "this timeline is cooked", "move fast, bet things",
    "emotionally invested", "science is just spicy guessing",
    "stranger than fiction, again", "the stans already know",
    "number go up technology", "democracy is a spectator sport",
    "statistically improbable, emotionally certain",
]


def _reroll_quip(title, category, used_quips):
    """Pick a quip that hasn't been used yet."""
    # Try generating one normally first with a salt
    for salt in range(1, 20):
        salted = f"{title}_{salt}"
        h = int(hashlib.md5(salted.encode()).hexdigest(), 16)
        candidate = ALL_QUIPS[h % len(ALL_QUIPS)]
        if candidate not in used_quips:
            return candidate
    # Fallback: find any unused quip
    for q in ALL_QUIPS:
        if q not in used_quips:
            return q
    return "a buck says maybe"


def generate_ai_quips(board):
    """Use Claude to generate unique, funny quips for all board markets at once."""
    if not ANTHROPIC_API_KEY:
        print("[scanner] No ANTHROPIC_API_KEY set, using fallback quips", file=sys.stderr)
        return board

    # Build the prompt with all markets
    market_lines = []
    for i, m in enumerate(board):
        market_lines.append(f"{i+1}. \"{m['title']}\" — $1 pays ${m['payout']}")

    prompt = f"""You write the editorial quips for Dollar Bets, a daily board of the internet's most entertaining prediction market wagers. Each quip appears in italics below the bet title and payout.

Here are today's {len(board)} bets:

{chr(10).join(market_lines)}

Write one quip for each bet. Rules:
- Each quip must be 2-8 words, all lowercase, no period at the end
- Tone: dry wit, internet-native, slightly unhinged but never try-hard
- No quip should repeat within today's board. Across different days a quip can recur, but aim for freshness
- Reference the specific bet when possible, not generic commentary
- Think Twitter reply guy energy meets Bloomberg terminal operator
- Examples of the vibe: "posting through it", "the timeline is undefeated", "emotionally invested", "your uber driver called it", "the conclave vibes are immaculate", "imagine the group chat", "included for comedy only", "a rumour old enough to rent a car", "grim little climate scratcher", "total unknown, national delusion, total perfection", "your mortgage broker just lit a candle", "america presses continue", "may the bracket gods be merciful", "dangerous aura", "intrusive thoughts won today"

Respond with ONLY a JSON array of strings, one quip per bet, in the same order. No other text."""

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
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

    try:
        print(f"[scanner] Calling Claude API for quips...", file=sys.stderr)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            result = json.loads(raw)
            text = result["content"][0]["text"].strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
                text = text.strip()
            print(f"[scanner] Claude response: {text[:100]}...", file=sys.stderr)
            quips = json.loads(text)
            if isinstance(quips, list) and len(quips) == len(board):
                for i, q in enumerate(quips):
                    board[i]["quip"] = q.strip().rstrip(".")
                print(f"[scanner] AI quips generated for {len(board)} markets", file=sys.stderr)
            else:
                print(f"[scanner] AI returned {len(quips)} quips for {len(board)} markets, keeping fallbacks", file=sys.stderr)
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else "no body"
        print(f"[scanner] AI quip HTTP {e.code}: {body[:200]}, keeping fallbacks", file=sys.stderr)
    except Exception as e:
        print(f"[scanner] AI quip generation failed: {type(e).__name__}: {e}, keeping fallbacks", file=sys.stderr)

    return board


# ── Board assembly ───────────────────────────────────────────

def build_board(events):
    """Score events, fetch prices for top candidates, build the board."""

    # Step 1: Score all events
    scored_events = []
    for e in events:
        s = score_event(e)
        scored_events.append((s, e))

    scored_events.sort(key=lambda x: x[0], reverse=True)

    # Step 2: Fetch markets for top ~50 events to get prices
    top_n = min(50, len(scored_events))
    print(f"[scanner] Fetching prices for top {top_n} events...", file=sys.stderr)

    candidates = []
    for i, (event_score, event) in enumerate(scored_events[:top_n]):
        event_ticker = event.get("event_ticker", "")
        markets = fetch_markets_for_event(event_ticker)
        time.sleep(0.3)  # throttle to avoid 429s

        if (i + 1) % 10 == 0:
            print(f"[scanner]   ...{i+1}/{top_n} events checked", file=sys.stderr)

        # Filter to real markets (no MVE parlays), with valid prices
        valid_markets = []
        for m in markets:
            if m.get("mve_collection_ticker"):
                continue
            payout = calc_payout(m)
            if payout is None or payout < 1.5:
                continue
            try:
                volume = float(m.get("volume_fp") or 0)
            except (ValueError, TypeError):
                volume = 0
            valid_markets.append((m, payout, volume))

        if not valid_markets:
            continue

        # Pick ONE market per event — the one with the best payout in the sweet spot
        # Prefer 10x-100x range, then by volume
        def market_rank(item):
            m, payout, vol = item
            sweet = 30 if 10 <= payout <= 100 else (20 if 5 <= payout <= 1000 else 10)
            return sweet + min(vol / 1000, 20)

        valid_markets.sort(key=market_rank, reverse=True)
        best_market, payout, volume = valid_markets[0]

        tier = payout_tier(payout)
        category = event.get("category", "")

        # Build a good title: for multi-market events, use the specific
        # market title (it's more descriptive). For single-market events,
        # prefer the event title (cleaner).
        event_title = event.get("title", "")
        market_title = best_market.get("title", "")

        if len(valid_markets) > 1 and market_title:
            # Multi-market event — use the specific market title
            # e.g. "Will Phil Lord & Christopher Miller win Best Director?"
            display_title = market_title
        else:
            display_title = event_title or market_title

        quip = generate_quip(display_title, category)

        # Boost event score with market-level signals
        market_score = event_score
        if volume > 10000:
            market_score += 15
        elif volume > 1000:
            market_score += 10
        elif volume > 100:
            market_score += 5
        elif volume < 10:
            market_score -= 10

        if 10 <= payout <= 100:
            market_score += 20
        elif 5 <= payout <= 1000:
            market_score += 10

        candidates.append({
            "ticker": best_market.get("ticker", ""),
            "title": display_title,
            "subtitle": event.get("sub_title", ""),
            "payout": payout,
            "tier": tier,
            "quip": quip,
            "yes_price": best_market.get("yes_ask_dollars", "0"),
            "volume": volume,
            "category": category,
            "close_time": best_market.get("close_time") or best_market.get("expiration_time", ""),
            "url": f"https://kalshi.com/markets/{event.get('series_ticker', event_ticker)}",
            "score": market_score,
        })

    print(f"[scanner] {len(candidates)} candidates with valid prices", file=sys.stderr)

    # Step 3: Pick top markets with tier diversity
    candidates.sort(key=lambda x: x["score"], reverse=True)

    board = []
    used_quips = set()
    tier_counts = {"green": 0, "yellow": 0, "orange": 0, "red": 0, "purple": 0}
    tier_limits = {"green": 3, "yellow": 3, "orange": 3, "red": 2, "purple": 2}

    for m in candidates:
        tier = m["tier"]
        if tier_counts.get(tier, 0) < tier_limits.get(tier, 3):
            # Ensure unique quip — re-roll if duplicate
            quip = m["quip"]
            if quip in used_quips:
                quip = _reroll_quip(m["title"], m["category"], used_quips)
                m["quip"] = quip
            used_quips.add(quip)
            board.append(m)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if len(board) >= TARGET_PICKS:
            break

    # Sort: smallest to largest payout
    board.sort(key=lambda x: x["payout"])

    return board


# ── Main ─────────────────────────────────────────────────────

def main():
    use_sample = "--sample" in sys.argv

    if use_sample:
        print("[scanner] Using sample data", file=sys.stderr)
        board = pick_sample_board()
    else:
        print("[scanner] Fetching events from Kalshi...", file=sys.stderr)
        events = fetch_all_events()
        if not events:
            print("[scanner] No events fetched, falling back to sample", file=sys.stderr)
            board = pick_sample_board()
        else:
            print(f"[scanner] {len(events)} events found", file=sys.stderr)
            board = build_board(events)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_count": len(board),
        "source": "kalshi",
        "board": board,
    }

    json.dump(output, sys.stdout, indent=2)
    print(f"\n[scanner] Board: {len(board)} markets selected", file=sys.stderr)


def pick_sample_board():
    """Build board from sample data for testing."""
    from _sample_data import SAMPLE_MARKETS
    # Score and pick from sample data
    scored = []
    used_quips = set()
    for m in SAMPLE_MARKETS:
        yes_price = m.get("yes_ask", 0)
        if yes_price <= 0 or yes_price >= 100:
            continue
        payout = round(1.0 / (yes_price / 100.0), 2)
        if payout < 1.5:
            continue
        tier = payout_tier(payout)
        quip = generate_quip(m["title"], m.get("category", ""))
        # Dedup quips — re-roll if already used
        if quip in used_quips:
            quip = _reroll_quip(m["title"], m.get("category", ""), used_quips)
        used_quips.add(quip)
        scored.append({
            "ticker": m["ticker"],
            "title": m["title"],
            "subtitle": m.get("subtitle", ""),
            "payout": payout,
            "tier": tier,
            "quip": quip,
            "yes_price": yes_price,
            "volume": m.get("volume", 0),
            "category": m.get("category", ""),
            "close_time": m.get("close_time", ""),
            "url": f"https://kalshi.com/markets/{m['ticker']}",
            "score": 50,
        })
    scored.sort(key=lambda x: x["payout"])
    return scored[:TARGET_PICKS]


if __name__ == "__main__":
    main()
