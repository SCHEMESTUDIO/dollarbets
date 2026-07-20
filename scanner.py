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
import random
import re
import sys
import hashlib
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_REFERRAL = "e690aa11-1f29-49d1-b27f-d5e6ccf38d9f"
POLYMARKET_API = "https://gamma-api.polymarket.com"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TARGET_PICKS = 10


# Action verbs we treat as "specific predicted actions" — used both by
# score_specificity (for verb-bonus on individual titles) and by the
# entity-verb corpus (for tracking which verbs co-occur with which entities).
#
# Two groups:
#   - institutional/state actions: says, fires, signs, approves, indicts...
#     (in-character for politicians/officials — common)
#   - behavioral/personal actions: dances, wears, rides, kisses, marries...
#     (off-script for institutional figures — when paired with a politician,
#     the (entity, verb) corpus will flag them as surprising)
#
# Module-level so _extract_verbs_from_title can share it.
ACTION_VERBS = {
    # Institutional / state actions
    "say", "says", "mention", "mentions", "operate", "operates",
    "expand", "expands", "launch", "launches", "announce", "announces",
    "sign", "signs", "become", "becomes", "pass", "passes", "fail", "fails",
    "drop", "drops", "rise", "rises", "hit", "hits",
    "appear", "appears", "perform", "performs", "release", "releases",
    "file", "files", "join", "joins", "leave", "leaves",
    "test", "tests", "approve", "approves", "reject", "rejects",
    "endorse", "endorses", "fire", "fires", "resign", "resigns",
    "name", "names", "buy", "buys", "acquire", "acquires", "settle", "settles",
    "issue", "issues", "block", "blocks", "veto", "vetoes",
    "indict", "indicts", "convict", "convicts", "pardon", "pardons",
    # Behavioral / personal actions — signal off-script weirdness when
    # paired with figures we usually see doing institutional things
    "dance", "dances", "wear", "wears", "ride", "rides",
    "kiss", "kisses", "marry", "marries", "divorce", "divorces",
    "cry", "cries", "sing", "sings", "tweet", "tweets",
    "post", "posts", "stream", "streams", "skydive", "skydives",
    "surf", "surfs", "fight", "fights", "punch", "punches",
    "convert", "converts", "baptize", "baptizes",
    "appear", "appears",
    "die", "dies", "survive", "survives",
}

# Words that are commonly capitalized but aren't entity names (sentence-initial
# question words). Used to filter the entity extractor's false-positive on
# titles like "Will the Lakers beat the Warriors?" → entity list excludes Will.
_NOT_AN_ENTITY = {
    "will", "does", "is", "are", "has", "have", "can", "could",
    "would", "should", "what", "who", "when", "where", "how", "why",
    "the", "a", "an", "this", "that", "these", "those",
    "if", "or", "and", "but", "by", "on", "in", "at", "to", "of",
    "us", "uk",  # ambiguous — usually country code, sometimes ourselves; better to drop
}


def kalshi_url(ticker):
    """Build a Kalshi market URL with referral tracking."""
    return f"https://kalshi.com/markets/{ticker}?referral={KALSHI_REFERRAL}"


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


# ── Polymarket API helpers ──────────────────────────────────

def _poly_api_get(path, params=None):
    """Make a GET request to Polymarket's Gamma API."""
    url = f"{POLYMARKET_API}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        url += f"?{qs}"

    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "DollarBets/1.0"
    })

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[scanner:poly] Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"[scanner:poly] API error: {e} ({url})", file=sys.stderr)
            return None
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if attempt < 2:
                print(f"[scanner:poly] Timeout/error (attempt {attempt+1}): {e}", file=sys.stderr)
                time.sleep(2)
                continue
            print(f"[scanner:poly] API error after retries: {e} ({url})", file=sys.stderr)
            return None


def _poly_fetch_sorted(order, max_n, label):
    """Pull active Polymarket markets sorted by `order` (e.g. 'volume',
    'startDate'), descending, up to max_n. Returns a list of market dicts.
    Used by fetch_polymarket_markets to do the two-pass volume+recency crawl.
    """
    results = []
    offset = 0
    limit = 100
    while len(results) < max_n:
        try:
            data = _poly_api_get("/markets", {
                "active": "true",
                "closed": "false",
                "limit": str(limit),
                "offset": str(offset),
                "order": order,
                "ascending": "false",
            })
        except Exception as e:
            print(f"[scanner:poly:{label}] Fetch error at offset {offset}: {e}", file=sys.stderr)
            break
        if not data or not isinstance(data, list):
            break
        results.extend(data)
        if len(data) < limit:
            break
        offset += limit
        time.sleep(0.2)  # respect rate limits
    return results[:max_n]


def fetch_polymarket_markets(max_volume=1500, max_recency=1000):
    """Two-pass crawl: top by volume + top by startDate desc, deduped.

    Why two passes (added 2026-05-16): single volume-sort systematically
    misses the weird/niche markets — they sit below the top-N-by-volume
    cutoff and never enter our candidate pool. The recency pass surfaces
    newly listed markets before they accrue volume, which is where the
    "discover a small but fun market" value happens.

    Gamma API is rate-limited but free of $ cost; the only price is wall
    clock. ~25 API calls total, ~5 seconds extra scan time. No effect on
    Anthropic token spend (quip generation runs once on the final ~10
    selected markets, not per candidate).
    """
    volume_markets = _poly_fetch_sorted("volume", max_volume, "volume")
    recent_markets = _poly_fetch_sorted("startDate", max_recency, "recency")

    seen = set()
    combined = []
    for m in volume_markets + recent_markets:
        cid = m.get("conditionId")
        if cid and cid not in seen:
            seen.add(cid)
            combined.append(m)
        elif not cid:
            # Some markets may be missing conditionId — keep them but they
            # might dedupe against each other. Rare edge case.
            combined.append(m)

    print(
        f"[scanner:poly] Two-pass crawl: {len(volume_markets)} by-volume + "
        f"{len(recent_markets)} by-recency = {len(combined)} unique markets",
        file=sys.stderr,
    )
    return combined


def normalize_poly_market(pm):
    """Convert a Polymarket market dict into a candidate dict
    compatible with the Kalshi-based editorial pipeline.

    Returns a candidate dict or None if the market is unsuitable.
    """
    question = pm.get("question") or ""
    if not question:
        return None

    # Parse outcome prices — outcomePrices is a JSON string like '["0.40","0.60"]'
    prices_raw = pm.get("outcomePrices")
    if not prices_raw:
        return None
    try:
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
        yes_price = float(prices[0])
    except (json.JSONDecodeError, IndexError, ValueError, TypeError):
        return None

    # Filter: price must be between 0 and 1 (exclusive)
    if yes_price <= 0 or yes_price >= 1.0:
        return None

    payout = round(1.0 / yes_price, 2)
    if payout < 1.5:
        return None

    # Volume — require minimum to filter out dead/spam markets
    try:
        volume = float(pm.get("volume") or pm.get("volumeNum") or 0)
    except (ValueError, TypeError):
        volume = 0

    if volume < 1000:
        return None  # Skip low-volume markets

    # Build URL — use parent event slug (from events array) for correct /event/ URL,
    # fall back to market's own slug only if no parent event exists
    events_list = pm.get("events") or []
    event_slug = ""
    if isinstance(events_list, list) and len(events_list) > 0:
        event_slug = events_list[0].get("slug", "")
    slug = pm.get("slug") or ""
    if event_slug:
        market_url = f"https://polymarket.com/event/{event_slug}"
    elif slug:
        market_url = f"https://polymarket.com/event/{slug}"
    else:
        return None

    # Filter out sub-markets: commodity contracts, temperature bins,
    # settlement ranges, etc. — these are parts of larger events
    # and their questions don't make sense as standalone bets
    q_lower = question.lower()
    sub_market_patterns = [
        # Financial/commodity sub-markets
        "settle above", "settle below", "settle between",
        "close above", "close below",
        "price of", "price on", "price be",
        "fail by", "go bankrupt", "basis points",
        "gdp growth", "inflation rate", "interest rate",
        "yield curve", "treasury", "selic rate", "fed funds",
        "no change in the", "rate cut", "rate hike",
        "valuation be between", "valuation be above", "valuation be below",
        "market cap", "revenue be", "earnings per share",
        # Temperature/weather sub-markets
        "highest temperature", "lowest temperature",
        "temperature in", "temperature on",
        "precipitation", "rainfall", "snowfall",
        "mm of rain", "mm of snow", "inches of rain", "inches of snow",
        "millimeters", "wind speed",
        # Range buckets (multi-outcome sub-markets)
        "be between", "be above $", "be below $",
        "between $", "above $", "below $",
        "more than $", "less than $", "at least $",
        "have between", "have more than", "have less than",
        "have above", "have below",
        # Market structure jargon
        "quarterly", "year-over-year", "seasonally adjusted",
        "benchmark", "fiscal", "monetary", "regulatory",
        # Political sub-markets (individual seat/district outcomes)
        "democratic party win the", "republican party win the",
        "win the house seat", "win the senate seat",
        "congressional district",
    ]
    if any(pat in q_lower for pat in sub_market_patterns):
        return None

    # Filter out range-bucket questions: "Will X be between 1.5T and 1.75T?"
    # These are individual outcomes of multi-outcome events
    if re.search(r'between\s+[\d$£€]+.*and\s+[\d$£€]+', q_lower):
        return None

    # Filter out measurement-range questions: "150-160mm", "63-70 degrees"
    if re.search(r'\d+-\d+\s*(mm|cm|°|degrees|inches|mph|kmh)', q_lower):
        return None

    # Map Polymarket tags to Kalshi-style categories
    tags = pm.get("tags") or []
    category = _poly_tags_to_category(tags, question)

    # Close time
    end_date = pm.get("endDate") or pm.get("end_date_iso") or ""

    tier = payout_tier(payout)

    # Build a pseudo-event dict for cultural hook scoring
    event_proxy = {
        "title": question,
        "sub_title": "",
        "category": category,
    }
    hook_score = score_cultural_hook(event_proxy)

    # Tradability scoring — adapt to Polymarket fields
    trad_score = 0
    if volume > 100000:
        trad_score += 10
    elif volume > 10000:
        trad_score += 5
    elif volume < 100:
        trad_score -= 20

    # Freshness — Polymarket doesn't have 24h volume in Gamma API,
    # but we can use overall volume as a proxy and deadline urgency
    fresh_score = 0
    if end_date:
        try:
            close_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            days_left = (close_dt - datetime.now(timezone.utc)).total_seconds() / 86400
            if days_left <= 1:
                fresh_score += 20
            elif days_left <= 3:
                fresh_score += 15
            elif days_left <= 7:
                fresh_score += 10
            elif days_left <= 14:
                fresh_score += 5
            if days_left > 365:
                fresh_score -= 10
        except (ValueError, TypeError):
            pass

    # Lever 6 (specificity) — same signal works for Polymarket titles.
    # Polymarket doesn't get lever 4 (no series concept in opaque conditionId
    # tickers) but it gets lever 1 (via score_cultural_hook) and now lever 6.
    # Lever 7 (entity-verb surprise) also applies — entity extraction is
    # platform-agnostic. Loaded lazily here so we don't burn the I/O on every
    # individual normalize call; the cost is one fs scan per scan run
    # because Python caches the function call inside the same interpreter.
    specificity = score_specificity(question)
    # Soften the tradability ghost-town penalty same way we do for Kalshi
    if specificity >= 15 and trad_score < -5:
        trad_score = -5
    # Note: entity-verb surprise for Polymarket is computed in build_board
    # post-merge so we share the corpus load with Kalshi. Until then leave
    # the per-market score without it; build_board will patch it in.
    editorial_score = (
        hook_score
        + score_payout_drama(payout)
        + fresh_score
        + trad_score
        + specificity
    )

    quip = generate_quip(question, category)

    return {
        "ticker": pm.get("conditionId") or group_slug or slug,
        "title": question,
        "subtitle": "",
        "payout": payout,
        "tier": tier,
        "quip": quip,
        "yes_price": f"{yes_price:.4f}",
        "volume": volume,
        "category": category,
        "close_time": end_date,
        "_specificity": specificity,
        "url": market_url,
        "platform": "polymarket",
        "score": editorial_score,
        # Extra fields for cross-platform dedup
        "_source": "polymarket",
        "_title_lower": question.lower().strip(),
    }


def _poly_tags_to_category(tags, question):
    """Map Polymarket tags to Kalshi-style categories for consistent scoring."""
    tag_str = " ".join(t.lower() for t in tags) if tags else ""
    q = question.lower()

    mapping = [
        (["politics", "election", "government", "trump", "biden"], "World"),
        (["crypto", "bitcoin", "ethereum", "defi"], "Crypto"),
        (["ai", "artificial intelligence", "llm", "gpt", "model"], "Science and Technology"),
        (["sports", "nba", "nfl", "mlb", "soccer", "football"], "Sports"),
        (["climate", "weather", "temperature", "hurricane"], "Climate and Weather"),
        (["entertainment", "celebrity", "movie", "music", "oscar"], "Entertainment"),
        (["science", "space", "nasa", "mars"], "Science and Technology"),
    ]

    combined = f"{tag_str} {q}"
    for keywords, category in mapping:
        if any(kw in combined for kw in keywords):
            return category

    return "Other"


# ── URL validation ──────────────────────────────────────────

def _validate_url(url):
    """Check if a URL returns a valid page.

    For Polymarket, uses the Gamma API because their SPA returns
    HTTP 200 for ALL routes (even nonexistent ones).
    For other platforms, uses a HEAD request.
    """
    if "polymarket.com/event/" in url:
        return _validate_polymarket_url(url)

    # Non-Polymarket: HEAD request
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "DollarBets/1.0"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status < 400
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, OSError, TimeoutError):
        return True  # Network error — benefit of the doubt


def _validate_polymarket_url(url):
    """Validate a Polymarket event URL via the Gamma API.

    Polymarket is a React SPA — HEAD/GET requests return 200 for
    every route, even pages that show "not found" client-side.
    The only reliable check is to verify the slug exists in their API.
    """
    match = re.search(r'polymarket\.com/event/([^/?#]+)', url)
    if not match:
        return False
    slug = match.group(1)

    # Check events endpoint (covers groupSlug-based URLs)
    try:
        api_url = f"{POLYMARKET_API}/events?slug={slug}&limit=1"
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/json",
            "User-Agent": "DollarBets/1.0"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                print(f"[scanner:validate] Polymarket slug OK (events): {slug}", file=sys.stderr)
                return True
    except (urllib.error.HTTPError, json.JSONDecodeError):
        pass
    except (urllib.error.URLError, OSError, TimeoutError):
        return True  # Network error — benefit of the doubt

    # Fallback: check markets endpoint (covers standalone market slugs)
    try:
        api_url = f"{POLYMARKET_API}/markets?slug={slug}&limit=1"
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/json",
            "User-Agent": "DollarBets/1.0"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                print(f"[scanner:validate] Polymarket slug OK (markets): {slug}", file=sys.stderr)
                return True
    except (urllib.error.HTTPError, json.JSONDecodeError):
        pass
    except (urllib.error.URLError, OSError, TimeoutError):
        return True  # Network error — benefit of the doubt

    # Both checks failed — this slug doesn't resolve
    print(f"[scanner:validate] Polymarket slug NOT FOUND: {slug}", file=sys.stderr)
    return False


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
    if payout <= 3:
        return "green"
    elif payout <= 7:
        return "yellow"
    elif payout <= 15:
        return "orange"
    elif payout <= 50:
        return "red"
    else:
        return "purple"


# ── Editorial scoring ───────────────────────────────────────
#
# Five pillars, scored independently:
#   1. CULTURAL HOOK — would a normal person get why this is interesting?
#   2. PAYOUT DRAMA — does the $1 return make the bet feel alive?
#   3. FRESHNESS — new listing, deadline approaching, or recent price move?
#   4. VARIETY — enforced at board selection, not individual scoring
#   5. TRADABILITY — volume, spread, open interest (scored at market level)
#

def score_cultural_hook(event):
    """Pillar 1: Would a normal person understand why this is funny or interesting?"""
    score = 0.0
    title = (event.get("title") or "").lower()
    subtitle = (event.get("sub_title") or "").lower()
    category = (event.get("category") or "").lower()
    full_text = f"{title} {subtitle}"

    # Category-bucket scoring removed 2026-05-16: bucket labels correlate with
    # mainstream-ness, not with weirdness. Privileging "entertainment / sports
    # / tech" was systematically biasing boards toward the boring middle.
    # Topic-level filtering now lives in the text-based jargon penalty below
    # (which catches hostile content like "basis points" / "GDP" by text, not
    # category) and in the weird/mainstream keyword tiers. A market in
    # category="Other" or "Companies" or "Education" now competes on merit.

    # Lever 1 (2026-05-16): split the flat "watercooler" keyword list into two
    # tiers. The old flat list treated "alien" and "NFL" identically — which is
    # why boards trended mainstream/boring. The weird tier (rare events, specific
    # surprises, things you'd actually screenshot) outweighs the mainstream tier
    # (sports/celebrity proper nouns you see in every headline every day).
    weird_keywords = [
        "alien", "ufo", "asteroid", "meteor", "comet", "eclipse", "tornado",
        "mars", "moon", "pope", "volcano", "hurricane", "earthquake",
        "extinct", "banned", "record", "ever", "first", "scandal", "viral",
        "meme", "nuclear", "peace", "snow", "miracle",
    ]
    mainstream_keywords = [
        "elon", "trump", "taylor swift", "kanye", "drake", "bitcoin",
        "ai", "robot", "tiktok", "celebrity", "super bowl", "oscar",
        "grammy", "olympics", "spacex", "tesla", "apple", "google",
        "netflix", "nba", "nfl", "mlb", "world cup", "premier league",
        "war",
    ]
    # Word-boundary regex so short keywords don't substring-match arbitrary
    # words. Caught 2026-05-16: "war" was matching "Warriors", "ai" was
    # matching "said"/"rail"/"Spain"/"wait" — basically every word with two
    # vowels. Now "war" only matches the word "war".
    def _kw_hit(kw, text):
        return re.search(rf"\b{re.escape(kw)}\b", text)
    weird_hits = sum(1 for kw in weird_keywords if _kw_hit(kw, full_text))
    mainstream_hits = sum(1 for kw in mainstream_keywords if _kw_hit(kw, full_text))
    score += min(weird_hits * 12, 24)        # 2 hits maxes — weird is the lever
    score += min(mainstream_hits * 3, 9)     # 3 hits maxes — mainstream is light seasoning

    # Title readability — shorter = punchier = more shareable
    if len(title) < 50:
        score += 10
    elif len(title) < 80:
        score += 5
    elif len(title) > 120:
        score -= 10

    # Questions are engaging ("Will X happen?")
    if "?" in title:
        score += 5

    # Penalize macro/finance jargon that reads like a Bloomberg headline.
    # Word-boundary regex so "index" doesn't catch "indexed" / "indexing"
    # and "monetary" doesn't catch arbitrary substrings. "index" itself
    # removed 2026-05-16 — was over-broad (matched "Bitcoin Volatility
    # Index", "Hurricane Wind Index" etc., which are perfectly fine markets).
    jargon = [
        "basis points", "yield curve", "quarterly", "benchmark",
        "fiscal", "monetary", "regulatory", "seasonally adjusted",
        "year-over-year", "bps",
    ]
    for kw in jargon:
        # Use word-boundary so short tokens like "bps" don't accidentally
        # match inside longer words. Compiled per-iter is fine for ~10 items.
        if re.search(rf"\b{re.escape(kw)}\b", full_text):
            score -= 20
            break

    # Penalize niche sports/esports jargon. Word-boundary regex so "round "
    # doesn't match "around" / "Roundup" / "groundbreaking". "championship"
    # removed 2026-05-16 — was crushing legitimate major-sport titles
    # ("NFL championship game", "NBA Eastern Conference Championship").
    niche_sports = [
        "handicap", "esports", "bo3", "bo5", "map 1", "map 2",
        "round", "pistol round", "game handicap", "set handicap",
        "corners over", "corners under", "total kills",
        "first blood", "first tower", "flyweight", "bantamweight",
        "main card", "prelim", "serie b", "ligue 2", "2. bundesliga",
        "pisa sc", "eredivisie",
    ]
    niche_hits = sum(
        1 for kw in niche_sports
        if re.search(rf"\b{re.escape(kw)}\b", full_text)
    )
    if niche_hits:
        score -= 25 * niche_hits

    return score


def score_payout_drama(payout):
    """Pillar 2: Does the $1 return make the bet feel alive?
    Sweet spot is 5x-50x. Too low = boring, too high = gimmicky.
    Tiers: green ≤3, yellow 3-7, orange 7-15, red 15-50, purple 50+."""
    if payout is None:
        return -50
    if 7 <= payout <= 50:
        return 25          # the sweet spot — dramatic but credible
    elif 3 <= payout <= 100:
        return 15           # still interesting
    elif 2 <= payout < 3:
        return 5            # fine, low end of green
    elif payout < 2:
        return -15          # too likely, no drama
    elif payout > 500:
        return -10          # extreme lottery ticket
    else:
        return 10           # 100-500 range, solid purple territory
    return 0


def score_freshness(market, event):
    """Pillar 3: New listing, upcoming deadline, or recent activity."""
    score = 0.0
    now = datetime.now(timezone.utc)

    # Deadline urgency — closing within 7 days gets a boost
    close_str = market.get("close_time") or market.get("expiration_time") or ""
    if close_str:
        try:
            close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00"))
            days_left = (close_dt - now).total_seconds() / 86400
            if days_left <= 1:
                score += 20   # resolves TODAY — peak urgency
            elif days_left <= 3:
                score += 15
            elif days_left <= 7:
                score += 10
            elif days_left <= 14:
                score += 5
            # Markets years away feel stale
            if days_left > 365:
                score -= 10
        except (ValueError, TypeError):
            pass

    # Recent volume = people are actively trading this
    try:
        vol_24h = float(market.get("volume_24h_fp") or 0)
    except (ValueError, TypeError):
        vol_24h = 0

    if vol_24h > 5000:
        score += 15    # hot market
    elif vol_24h > 1000:
        score += 10
    elif vol_24h > 100:
        score += 5
    elif vol_24h == 0:
        score -= 10    # dead market, skip

    return score


def score_tradability(market):
    """Pillar 5: Can someone actually trade this without getting ripped off?"""
    score = 0.0

    # Volume — dead markets are bad UX
    try:
        volume = float(market.get("volume_fp") or 0)
    except (ValueError, TypeError):
        volume = 0

    if volume > 10000:
        score += 10
    elif volume > 1000:
        score += 5
    # Low-volume penalty removed 2026-05-16: small markets are the niche-gems
    # James wants surfaced ("Vance says autism", "UT Austin ranking drops").
    # The spread penalty later in this function is the real user-protection
    # signal — wide spread = users get fleeced. Volume alone is a popularity
    # proxy, not a quality signal. The lever-6 specificity reserve relies
    # on this floor being gone.

    # Open interest — are people actually holding positions?
    try:
        oi = float(market.get("open_interest_fp") or 0)
    except (ValueError, TypeError):
        oi = 0

    if oi > 5000:
        score += 10
    elif oi > 500:
        score += 5
    elif oi < 10:
        score -= 10

    # Spread — gap between bid and ask
    try:
        ask = float(market.get("yes_ask_dollars") or 0)
        bid = float(market.get("yes_bid_dollars") or 0)
    except (ValueError, TypeError):
        ask, bid = 0, 0

    if ask > 0 and bid > 0:
        spread = ask - bid
        if spread <= 0.03:
            score += 10   # tight spread, liquid market
        elif spread <= 0.10:
            score += 5
        elif spread > 0.25:
            score -= 15   # ugly spread, someone's getting fleeced

    return score


def score_specificity(title):
    """Pillar 6 (added 2026-05-16): detect 'question-shape specificity' — the
    signal that distinguishes a market someone *crafted* from one that came
    out of a template. Examples that should score high:
      - "Vance says autism on Fox News today"           (entity + action + show + time)
      - "Waymo operates in Detroit this year"           (corp + specific city + time)
      - "UT Austin ranking drops this year"             (specific school + change + time)
      - "Major meteor hits earth before 2030"           (singular event + deadline)
      - "SNL says alien on Weekend Update this week"    (show + word + segment + time)

    Examples that should score low:
      - "Bitcoin above 100k by year end"                (template — same shape every day)
      - "Lakers beat Warriors tonight"                  (template — vs. game)
      - "Will the Fed cut rates?"                       (generic macro template)

    Returns 0..20. Combines proper-noun density, time-window phrasing, action
    verb presence, and a length sweet spot. The signals are noisy individually
    but additively strong. NB: noisy enough that we still pair it with lever 4
    (series-recurrence penalty) — a generic NBA-game title can rack up proper
    nouns but its KXNBAGAME series will be docked for daily repetition.
    """
    import re
    if not title:
        return 0

    score = 0
    words = title.split()
    n_words = len(words)

    # Proper-noun density. Counts ALL capitalized words including word 0 —
    # otherwise "Waymo operates in Detroit" loses a point because Waymo is
    # sentence-initial. Title-case headlines from Kalshi don't typically
    # capitalize prepositions/articles, so isupper() reliably catches named
    # entities. Threshold of 3 minimizes false positives from generic
    # sports titles ("Lakers beat Warriors") which already get docked via
    # lever 4 series-recurrence anyway.
    proper_nouns = sum(1 for w in words if w and w[0].isalpha() and w[0].isupper())
    if proper_nouns >= 3:
        score += 10
    elif proper_nouns >= 2:
        score += 5

    title_l = title.lower()

    # Time-window phrases — concrete deadline = specific question
    time_patterns = [
        r"\bthis (week|month|year|weekend)\b",
        r"\btonight\b",
        r"\bby (?:end of |the end of )?(?:20)?\d{2,4}\b",
        r"\bbefore (?:20)?\d{2,4}\b",
        r"\bby (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b",
        r"\bin (?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
    ]
    if any(re.search(p, title_l) for p in time_patterns):
        score += 5

    # Action verbs — narrow predicted action vs. generic win/lose template.
    # Module-level ACTION_VERBS set (defined near the top of this file) so
    # the entity-verb corpus can reuse the same vocabulary.
    tokens = set(re.findall(r"\b[a-z]+\b", title_l))
    if tokens & ACTION_VERBS:
        score += 5

    # Length sweet spot — long enough to be specific, short enough to be punchy
    if 6 <= n_words <= 14:
        score += 5
    elif n_words >= 25:
        score -= 5  # rambling Polymarket-style legal-disclosure titles

    return max(0, min(score, 20))


# ── Quip library ────────────────────────────────────────────

ALL_QUIPS = [
    # === UNIVERSAL ===
    "the audacity of this market", "technically possible, spiritually unlikely",
    "the math is mathing", "somebody's thesis just died",
    "the simulation is glitching", "the internet remains undefeated",
    "this one sparks joy", "screenshotted for the archives",
    "a niche concern, nationally", "the prophecy demands it",
    "someone will be unbearable about this", "the discourse is already exhausting",
    "filed under controlled chaos", "a beautiful waste of a dollar",
    "the wrong people are excited about this", "this has thanksgiving dinner energy",
    "suspiciously specific", "everyone has an opinion, nobody has data",
    "there will be a podcast about this", "the group chat will not recover",
    "not even close to the weirdest bet here", "the spreadsheet guys are thriving",
    "this is someone's entire personality", "unironically compelling",
    "the timeline will have opinions", "tell your uber driver",
    "chaotic neutral energy", "peak late capitalism entertainment",
    "deeply funny or deeply concerning", "a victimless wager",
    "the algorithm brought you here", "buckle up or log off",
    "file this under entertainment expenses", "the cowards won't bet this",
    "a prayer and a dollar", "the news cycle is unwell",
    "your coworker has opinions about this one", "somebody made a spreadsheet",
    "the linkedin posts write themselves", "this will be on a quiz",
    "the reply guys are mobilizing", "an argument waiting to happen",
    "the interns are watching", "your dad will text you about this",
    "someone's already writing the substack", "the betting gods demand entertainment",
    "objectively nobody's business, subjectively everyone's",
    "already a reddit thread", "the kind of thing you google at 2am",
    "brought to you by idle curiosity", "overheard at every airport bar",
    "the pub quiz question of the future", "a solvable problem no one will solve",
    "everyone's an expert suddenly", "the op-eds are loading",
    "technically not gambling, technically", "the wikipedia page will be contentious",
    "someone's career depends on this", "mentioned in passing, obsessed about privately",
    "your fantasy league is shaking", "a question nobody asked but everyone answered",
    "the takes are already bad", "surprisingly divisive at dinner parties",
    "this is how you lose an afternoon", "a perfectly reasonable thing to bet on",
    "the podcasters are circling", "someone's PowerPoint just got more interesting",
    "this has wedding speech potential", "the hot take industrial complex is ready",
    "a slow news day's best friend", "your notifications will be about this",
    "the kind of news that interrupts lunch", "politely apocalyptic",
    "the betting equivalent of comfort food", "an entire personality in one wager",
    "your barber has a take on this", "the office slack channel is about to erupt",
    "a thing you'll pretend you predicted",
    "your uber driver has a position on this",
    "somebody's newsletter just found its hook",
    "the wrong meeting is about to run long",
    "a conversation starter nobody asked for",
    "your cousin's boyfriend is confident about this",
    "this will be misquoted by thursday",
    "a strong opinion held loosely",
    "the comment section will be educational",
    "someone just opened a new browser tab",
    "this is why people have trust issues",
    "your financial advisor doesn't want to know",
    "the bookmarks folder is growing",
    "not the hill, but definitely a hill",
    "a reasonable dollar, an unreasonable outcome",
    "the people who care really care",
    "the quiet part said loudly, for a dollar",
    "somebody's bluffing and it might be you",
    "the gym bros are divided", "forwarded without context",
    "this is the plot of a movie nobody made",
    "the groupthink is forming", "your most unserious investment",
    "someone is making this their whole week",
    "the kind of bet you explain poorly at parties",
    "historians will not care but twitter will",
    "a footnote in someone's memoir",
    "the morning news but make it fun",
    "confidently wagered, nervously refreshed",
    "an opinion you didn't know you had",
    "the market for chaos is bullish",
    "your ex has thoughts about this", "a dollar well wasted",
    "someone's screenshot folder just got heavier",
    "this is between you and your search history",
    "your therapist doesn't need to know about this",
    "casually existential", "your most informed guess",
    "the stakes are low but the drama is high",
    "someone's conspiracy theory just got funding",
    "a matter of public fascination",
    "the wrong crowd is paying attention",
    "a gentle wager against common sense",
    "the betting slip of a curious mind",
    "this is going on the fridge at work",
    "a matter of intense casual interest",
    "your cab driver was right about this one",
    "someone's retirement toast just got material",
    "the most interesting dollar you'll spend today",
    "a thing that sounds fake but has a market",
    "the quiet scandal of a well-placed dollar",
    "someone's going to claim they knew all along",
    "a footnote that refuses to stay small",
    "the watercooler is going to be insufferable",
    "the sort of thing that ends up in a documentary",
    "the internet is about to have feelings",
    "a thing that will age either well or terribly",
    "the most fun you can have for a dollar, legally",
    "this has after-hours trading energy",
    "your mother-in-law has a theory",
    "a wager that punches above its weight class",
    "someone is going to get this tattooed if it hits",
    "your most defensible bad decision",
    "a controlled demolition of your spare change",
    "the barbershop debate of the week",
    "this is the plot twist nobody budgeted for",
    "a thing you'll explain badly to your partner",
    "the betting equivalent of a side quest",
    "someone's about to be very right or very quiet",
    "a perfectly timed distraction from real life",
    "a one-dollar referendum on the state of things",
    "the sort of bet that makes you check your phone",
    "someone's going to bring this up at thanksgiving",
    "a thing that shouldn't be this interesting but is",
    "the most democratic use of a dollar",
    "this is getting brought up at the reunion",
    "a slow-burning argument with a price tag",
    "somebody just set a calendar reminder for this",
    "your lyft driver's analysis was surprisingly sound",
    "the only market where vibes are a valid indicator",
    "someone's going to frame the receipt",
    "a wager for the perpetually curious",
    "this has emergency press conference energy",
    "the sort of thing that splits a friend group",
    "the kind of bet that ages like a screenshot",
    "a one-dollar ticket to the discourse",
    "someone's mood board just got weirder",
    "the rare bet where losing is also entertaining",
    # === ORIGINALS ===
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
    "imagine the group chat", "included for comedy only",
    "a rumour old enough to rent a car", "grim little climate scratcher",
    "total unknown, national delusion, total perfection",
    "your mortgage broker just lit a candle", "america presses continue",
    "may the bracket gods be merciful", "dangerous aura",
    "intrusive thoughts won today",
    "the main character of the internet", "posting through it",
    "this man does not sleep", "elon being elon",
    "democracy in 4K", "the swifties already know",
    "emotionally devastating if true", "she planned this",
    "your uber driver called it", "the chart has a plan",
    "the red planet awaits", "elon's working on it",
    "one small bet for man", "space is the place",
    "holy speculation", "the conclave vibes are immaculate",
    "white smoke or cope", "the weather app is lying again",
    "dress accordingly", "nature doesn't negotiate",
    "the golden state of denial", "only in california",
    "the vibes are seismic", "cable news will be unwatchable",
    "this is the timeline we chose", "sports are scripted anyway",
    "the math checks out, barely", "your bracket is already busted",
    "just for the group chat", "silicon valley is at it again",
    "the planet is running a fever", "you can't make this up",
    "history doesn't repeat but it rhymes",
    "mother nature's got range", "pack an umbrella and a prayer",
    "laser eyes optional", "the chart looks like a heartbeat",
    "hodl or fold",
    # === POP CULTURE REFERENCES ===
    # Film / TV
    "the Prometheus school of running away from things",
    "directed by the Coen brothers, apparently",
    "this has Succession finale energy",
    "a Wes Anderson montage of a wager",
    "the Michael Scott of prediction markets",
    "somehow Palpatine returned",
    "the prestige, but for your dollar",
    "we're gonna need a bigger bet",
    "the Truman Show but for markets",
    "directed by Christopher Nolan, scored by anxiety",
    "the Bear kitchen energy is palpable",
    "a mid-credits scene kind of reveal",
    "the Office fire drill but for traders",
    "the Nic Cage movie writes itself",
    "a post-credits scene for sure",
    "curb your enthusiasm theme plays",
    "the Always Sunny title card goes here",
    "directed by God, edited by chaos",
    "this is the Bad Place",
    "a Scorsese runtime kind of bet",
    # Music / lyrics
    "I miss the earth so much, I miss my wife",
    "the Rise and Fall of a Midwest Princess",
    "running up that hill with no problems",
    "how do you like them apples",
    "it's me, hi, I'm the problem",
    "we didn't start the fire but we bet on it",
    "mama said knock it out of the park",
    "somebody once told me the odds were stacked",
    "bohemian rhapsody but for spreadsheets",
    "under pressure, pushing down on me",
    "the sound of silence, statistically",
    # Internet / memes
    "the diet Dr. Pepper of prediction markets",
    "60% of the time, it works every time",
    "this is fine dot jpg",
    "the meme wrote itself and then listed",
    "sir this is a Wendy's",
    "you vs the bet she told you not to worry about",
    "the stonks meme but unironically",
    "main character syndrome, market edition",
    "task failed successfully",
    "suffering from success",
    "Money printer go brrrr",
    "ight imma head out",
    "the butterfly effect but with a dollar",
    "it's giving uncertainty",
    "understood the assignment, barely",
    "no thoughts just vibes and a dollar",
    "chaotic good, financially neutral",
    "the audacity of hype",
    # Books / history / general culture
    "the Moneyball of terrible decisions",
    "a Freakonomics chapter waiting to happen",
    "the invisible hand is trembling",
    "the Hemingway school of short positions",
    "art of war but for a dollar",
    "kafka would have placed this bet",
    "extremely normal and not at all unhinged",
    "the Wikipedia edit war is already underway",
    "outrageously plausible",
    "probably gravy",
    "short the club",
    "can't say you didn't see it coming",
    "fanboys writing congress as we speak",
    # === SPORTS ===
    "load management for your wallet", "the poster dunk of prediction markets",
    "someone's parlay just got interesting",
    "the analytics guys versus the eye test guys",
    "your fantasy lineup is sweating", "garbage time entertainment",
    "the hot take furnace is operational",
    "someone's shoe deal depends on this", "the stat nerds are typing",
    "a deep bench bet", "this has game 7 energy",
    "your league's group chat is in shambles",
    "the couch scouts have assembled",
    "someone's survivor pool just got complicated",
    "your bookie's bookie is watching",
    "the tailgate discourse is heating up",
    "a fourth quarter kind of bet",
    "someone just adjusted their mock draft",
    "a pick six of a wager", "someone's prop bet just got personal",
    "a seventh inning stretch of the imagination",
    "the sabermetrics crowd is mobilizing",
    "a small ball bet with big ball dreams",
    "a perfectly placed bunt of a wager", "this has rain delay energy",
    "a walk-off bet if it lands", "VAR would like a word",
    "your local has picked sides", "the post-match interview writes itself",
    "this has champions league anthem energy",
    "a power play for your dollar", "this has overtime energy",
    "a slapshot of a wager", "the press box is buzzing",
    "the message board is going to be unreadable",
    "a quality loss of a dollar", "the boosters are placing calls",
    "this has rivalry week energy", "your diploma just felt this",
    "a fourth-and-goal kind of bet", "the NIL implications are unclear",
    "your bracket is already in hospice", "the Cinderella story is loading",
    "someone's office pool just got interesting",
    "a buzzer beater of a dollar bet",
    "one shining moment of financial irresponsibility",
    "somebody filled out eight brackets for this",
    "the stat sheet tells a different story",
    "someone's dynasty league is panicking",
    "a garbage time bet with real stakes",
    "the ref is not going to help you here",
    "your sports bar just got louder", "a bench player of a bet",
    "the press conference is going to be good",
    "someone's career high depends on this",
    "the highlight reel is pending",
    "your pick 'em league will remember this",
    "a timeout called on common sense",
    "the postgame handshake line of wagers",
]

SPORTS_QUIPS = [q for q in ALL_QUIPS[ALL_QUIPS.index("load management for your wallet"):]]

KEYWORD_POOLS = {
    "elon|musk": ["the main character of the internet", "posting through it",
                   "this man does not sleep", "elon being elon"],
    "trump": ["certified popcorn moment", "the timeline is undefeated",
              "stranger than fiction, again", "democracy in 4K"],
    "taylor|swift": ["the swifties already know", "manifesting on main",
                     "emotionally devastating if true", "she planned this"],
    "bitcoin|btc|crypto": ["number go up technology", "your uber driver called it",
                           "the chart has a plan", "hodl or fold", "laser eyes optional"],
    "mars": ["the red planet awaits", "elon's working on it",
             "one small bet for man", "space is the place"],
    "pope": ["holy speculation", "the conclave vibes are immaculate",
             "white smoke or cope"],
    "snow|rain|weather|hurricane|tornado": ["emotionally correct", "the weather app is lying again",
                                            "dress accordingly", "nature doesn't negotiate",
                                            "mother nature's got range", "pack an umbrella and a prayer"],
    "california|earthquake": ["the golden state of denial", "only in california",
                              "the vibes are seismic"],
    "volcano|eruption|climate": ["grim little climate scratcher", "the planet is running a fever",
                                 "nature doesn't care about your plans"],
}


def generate_quip(title, category):
    """Pick a quip from the 350+ library, with keyword and category matching."""
    title_lower = title.lower()
    category_lower = category.lower()

    # Step 1: Check keyword overrides
    for keywords, pool in KEYWORD_POOLS.items():
        if any(kw in title_lower for kw in keywords.split("|")):
            h = int(hashlib.md5(title.encode()).hexdigest(), 16)
            return pool[h % len(pool)]

    # Step 2: Sports category gets sports pool + universal
    if "sport" in category_lower or any(kw in title_lower for kw in [
        "nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball",
        "baseball", "hockey", "premier league", "champions league",
        "playoff", "championship", "tournament", "bracket", "draft",
        "world cup", "super bowl", "world series", "stanley cup",
    ]):
        pool = SPORTS_QUIPS + ALL_QUIPS[:150]  # sports + universal
    else:
        pool = ALL_QUIPS

    # Step 3: Deterministic pick based on title hash
    h = int(hashlib.md5(title.encode()).hexdigest(), 16)
    return pool[h % len(pool)]


def _reroll_quip(title, category, used_quips):
    """Pick a quip that hasn't been used yet."""
    for salt in range(1, 50):
        salted = f"{title}_{salt}"
        h = int(hashlib.md5(salted.encode()).hexdigest(), 16)
        candidate = ALL_QUIPS[h % len(ALL_QUIPS)]
        if candidate not in used_quips:
            return candidate
    for q in ALL_QUIPS:
        if q not in used_quips:
            return q
    return "a buck says maybe"


def load_style_guide():
    """Load the editorial style guide (generated by analyze_taste.py)."""
    guide_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "style-guide.json"
    )
    try:
        with open(guide_path) as f:
            guide = json.load(f)
        version = guide.get("meta", {}).get("version", "?")
        n_principles = len(guide.get("principles", []))
        print(f"[scanner] Style guide v{version}: {n_principles} principles", file=sys.stderr)
        return guide
    except (FileNotFoundError, json.JSONDecodeError):
        print("[scanner] No style guide found — using pool-only mode", file=sys.stderr)
        return None


def build_style_guide_section(guide):
    """Format the style guide as prompt context."""
    if not guide:
        return ""

    sections = []

    # Voice
    voice = guide.get("voice_notes", "")
    if voice:
        sections.append(f"EDITORIAL VOICE: {voice}")

    # Principles
    principles = guide.get("principles", [])
    if principles:
        lines = []
        for p in principles:
            applies = ", ".join(p.get("examples_for", []))
            lines.append(f'- {p["principle"]} — Technique: {p["technique"]}'
                        + (f" (applies to: {applies})" if applies else ""))
        sections.append("EDITORIAL PRINCIPLES (learned from editor corrections):\n" + "\n".join(lines))

    # Anti-patterns
    avoid = guide.get("avoid", [])
    if avoid:
        lines = [f'- {a["pattern"]} — Why: {a["why"]}' for a in avoid]
        sections.append("AVOID THESE PATTERNS:\n" + "\n".join(lines))

    return "\n\n".join(sections)


def _load_custom_clusters():
    """Load editor-defined clusters from data/custom-clusters.json."""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "custom-clusters.json"
    )
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("clusters", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# Cache at module level so we don't re-read the file on every classify call
_CUSTOM_CLUSTERS = _load_custom_clusters()


def classify_quip(quip):
    """Assign a quip to one of ~15+ archetype clusters based on content signals.

    Checks editor-defined custom clusters (from taste analysis) first,
    then falls back to hardcoded clusters.
    """
    q = quip.lower()

    # --- Custom clusters (from taste analysis) take priority ---
    for cluster in _CUSTOM_CLUSTERS:
        if any(k.lower() in q for k in cluster.get("keywords", [])):
            return cluster["id"]

    # --- Specific-reference clusters ---
    film_tv = ["directed by", "coen", "succession", "wes anderson", "michael scott",
               "palpatine", "prestige", "truman show", "nolan", "the bear", "credits",
               "office fire", "nic cage", "curb your", "always sunny", "bad place",
               "scorsese", "prometheus", "hunger games",
               # added 2026-05-10 — Anchorman quote and meta-film phrasings
               "60% of the time", "told in one part"]
    music = ["miss the earth", "miss my wife", "midwest princess", "running up that hill",
             "them apples", "i'm the problem", "start the fire", "mama said", "somebody once",
             "bohemian", "under pressure", "sound of silence", "shake it off", "long long time",
             # added 2026-05-10 — Rocket Man w/ comma, Charli XCX, Home on the Range parody
             "a long, long time", "brat era", "drone on the range"]
    internet_meme = ["diet dr. pepper", "this is fine", "sir this is",
                     "stonks", "task failed", "suffering from success", "money printer",
                     "imma head out", "it's giving", "understood the assignment",
                     "no thoughts just vibes", "chaotic good", "audacity of hype",
                     "main character", "the meme wrote",
                     # added 2026-05-10 — wikipedia stub format meme
                     "wikipedia page", "under construction"]
    # NB: removed "60% of the time" from internet_meme — it's an Anchorman quote
    # (film_tv_reference) per editor's cluster_review on 2026-05-10
    books_hist = ["moneyball", "freakonomics", "invisible hand", "hemingway",
                  "art of war", "kafka", "wikipedia edit",
                  # added 2026-05-10 — Moneyball with a space
                  "money ball"]

    if any(k in q for k in film_tv):
        return "film_tv_reference"
    if any(k in q for k in music):
        return "music_reference"
    if any(k in q for k in internet_meme):
        return "internet_meme"
    if any(k in q for k in books_hist):
        return "books_history"

    # --- Sports cluster ---
    sports_words = ["parlay", "fantasy", "garbage time", "hot take", "stat nerd",
                    "game 7", "mock draft", "prop bet", "sabermetric", "slapshot",
                    "overtime", "buzzer", "bracket", "dynasty league", "bench player",
                    "touchdown", "VAR", "champions league", "pick 'em", "rivalry week",
                    "bookie", "tailgate", "walk-off", "power play", "shoe deal",
                    "load management", "poster dunk", "deep bench", "pick six",
                    "small ball", "bunt", "rain delay", "fourth quarter", "press box",
                    "boosters", "NIL", "cinderella", "office pool", "ref is not",
                    "highlight reel", "postgame", "press conference",
                    # added 2026-05-10 — covers eye-test debate, named athletes,
                    # market-vernacular sports framing
                    "eye test", "league history", "short the club", "alonso",
                    "see spurs go"]
    if any(k in q for k in sports_words):
        return "sports"

    # --- Tone / voice clusters ---
    if any(k in q for k in ["chaos", "chaotic", "unhinged", "cooked", "glitching",
                             "apocalyptic", "unwell", "demolition", "intrusive",
                             # added 2026-05-10 — absurdist parallel construction
                             # ("in other news: ...") + escalation patterns
                             "in other", "tears of crypto", "ends in human",
                             "trump island", "with opinions about your"]):
        return "chaos_energy"
    if any(k in q for k in ["spreadsheet", "data", "analytics", "math", "chart",
                             "number go up", "algorithm", "stat sheet", "financial"]):
        return "data_nerd"
    if any(k in q for k in ["group chat", "twitter", "reddit", "substack", "podcast",
                             "linkedin", "slack", "reply guys", "discourse", "timeline",
                             "notifications", "screenshot", "browser tab", "op-eds",
                             # added 2026-05-10 — collective-online-behavior framing
                             "fanboys"]):
        return "internet_discourse"
    if any(k in q for k in ["uber driver", "lyft driver", "barber", "cab driver",
                             "coworker", "dad will text", "cousin", "mother-in-law",
                             "partner", "therapist", "your ex",
                             # added 2026-05-10 — first/second-person reader-implication
                             "back when i was a kid", "i'll pay anything",
                             "could you pick", "the day i bring"]):
        return "person_has_opinion"
    if any(k in q for k in ["comedy", "lol", "funny", "entertainment", "popcorn",
                             "amusing", "hilarious", "jokes",
                             # added 2026-05-10 — comedian-as-stand-in framing
                             "will ferrell"]):
        return "comedy_framing"
    if any(k in q for k in ["existential", "meaning", "universe", "simulation",
                             "prophecy", "manifesting", "fate", "gods"]):
        return "cosmic_vibes"
    if any(k in q for k in ["dollar", "wallet", "wager", "bet ", "invest",
                             "gambling", "price tag", "spare change", "receipt"]):
        return "meta_wager"
    if any(k in q for k in ["whisper", "quiet", "gentle", "slow", "little",
                             "footnote", "passing", "soft", "plausible",
                             "reasonable", "defensible",
                             # added 2026-05-10 — dry biographical / quiet inevitability
                             "see it coming", "more love for", "spent twenty years"]):
        return "understated"
    if any(k in q for k in ["energy", "aura", "vibes", "mood", "feeling",
                             "emotional", "spirit"]):
        return "vibes_check"

    return "general_wit"


def build_pool_sample():
    """Pick a diverse sample of pool quips using cluster-based random sampling.

    Groups all quips into ~15 archetype clusters (pop culture refs, sports,
    chaos energy, data nerd, etc.), then samples ~2 from each cluster so
    the tone anchors always represent the full range of voice. Uses the
    current date as seed so each day is different but reproducible.
    """
    import random
    from datetime import date

    # Cluster all quips
    clusters = {}
    for quip in ALL_QUIPS:
        label = classify_quip(quip)
        clusters.setdefault(label, []).append(quip)

    # Date-seeded RNG — different each day, reproducible within a day
    rng = random.Random(date.today().isoformat())

    sample_size = 30
    per_cluster = max(sample_size // len(clusters), 1)
    sample = []

    # First pass: guaranteed minimum from each cluster
    for label in sorted(clusters.keys()):
        pool = clusters[label]
        n = min(per_cluster, len(pool))
        sample.extend(rng.sample(pool, n))

    # Second pass: fill remaining slots from largest clusters
    remaining = sample_size - len(sample)
    if remaining > 0:
        available = [(label, [q for q in quips if q not in sample])
                     for label, quips in clusters.items()]
        available = [(l, qs) for l, qs in available if qs]
        available.sort(key=lambda x: -len(x[1]))
        for label, pool in available:
            if remaining <= 0:
                break
            pick = min(1, remaining, len(pool))
            sample.extend(rng.sample(pool, pick))
            remaining -= pick

    rng.shuffle(sample)
    return sample


def _load_recent_series_recurrence(days_back=7):
    """Lever 4: count how many times each Kalshi series_ticker has shown up on
    main boards in the last N days (today excluded). A series in the ticker is
    the prefix before the first dash — e.g. KXBTCPRICE-26MAY16-12000 → series
    KXBTCPRICE. Recurrent series are the structural-repetition pattern James
    flagged: same-shaped daily question with different surface details (BTC
    price every day, generic election every day, etc.).

    Polymarket tickers are opaque condition IDs with no series structure, so
    Polymarket markets get no recurrence penalty here. They still get penalized
    via title-similarity dedup and the novelty bonus instead.
    """
    import glob
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    boards_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards")
    if not os.path.isdir(boards_dir):
        return Counter()

    today_utc = datetime.now(timezone.utc).date()
    counts = Counter()
    for i in range(1, days_back + 1):
        d = (today_utc - timedelta(days=i)).isoformat()
        path = os.path.join(boards_dir, f"{d}.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        for m in data.get("board", []):
            ticker = m.get("ticker") or ""
            # Kalshi tickers start with KX...; Polymarket are 0x-hex
            if not ticker.startswith("KX"):
                continue
            series = ticker.split("-", 1)[0]
            counts[series] += 1
    return counts


# Words that show up in basically every headline — useless for novelty detection.
_NOVELTY_STOPWORDS = {
    "this", "that", "than", "with", "from", "will", "have", "been", "were",
    "they", "them", "what", "when", "where", "into", "about", "before", "after",
    "today", "tonight", "week", "month", "year", "team", "wins", "beat", "beats",
    "over", "under", "their", "time", "last", "first", "next", "game", "season",
    "final", "finals", "home", "away", "play", "plays", "good", "best", "most",
    "more", "series", "match", "league", "tournament", "round", "score", "win",
    "lose", "loss", "point", "points", "goal", "goals", "race", "make", "makes",
    "take", "takes", "year",
}


def _load_recent_title_vocab(days_back=30):
    """Lever 5: extract the set of content words used in recent board titles.
    A market today whose title introduces words NOT in this set gets a novelty
    bump — that's how truly-specific framings (e.g. "Trump in a yarmulke") rise
    above template-recycled ones (e.g. "Lakers beat Warriors tonight").
    """
    import glob, re
    from datetime import datetime, timedelta, timezone

    boards_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards")
    if not os.path.isdir(boards_dir):
        return set()

    today_utc = datetime.now(timezone.utc).date()
    words = set()
    for i in range(1, days_back + 1):
        d = (today_utc - timedelta(days=i)).isoformat()
        for path in glob.glob(os.path.join(boards_dir, f"*{d}.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
            except Exception:
                continue
            for m in data.get("board", []):
                title = (m.get("title") or "").lower()
                for w in re.findall(r"[a-z]+", title):
                    if len(w) >= 4 and w not in _NOVELTY_STOPWORDS:
                        words.add(w)
    return words


def _score_recurrence_penalty(ticker, recent_series_counts):
    """Lever 4 penalty: stack -8 per prior appearance of this Kalshi series,
    capped at -24 (3+ prior days). Returns 0 for Polymarket / unknown tickers.
    Keep modest — over-penalty would *exclude* sports/crypto entirely rather
    than just rotating them. Tune after observing real boards.
    """
    if not ticker or not ticker.startswith("KX"):
        return 0
    series = ticker.split("-", 1)[0]
    prior = recent_series_counts.get(series, 0)
    if prior <= 0:
        return 0
    return -min(prior * 8, 24)


def _score_novelty_bonus(title, recent_title_vocab):
    """Lever 5 bonus: reward titles whose content words don't appear in any
    recent board. +10 if ≥60% of content words are novel, +5 if any novel.
    Returns 0 if no content words or vocab is empty (cold start)."""
    import re
    if not recent_title_vocab:
        return 0
    title_l = (title or "").lower()
    content = [w for w in re.findall(r"[a-z]+", title_l)
               if len(w) >= 4 and w not in _NOVELTY_STOPWORDS]
    if not content:
        return 0
    novel = [w for w in content if w not in recent_title_vocab]
    if not novel:
        return 0
    if len(novel) >= len(content) * 0.6:
        return 10
    return 5


def _extract_entities_from_title(title):
    """Crude named-entity extraction by capitalization. Returns a list of
    lowercased entity strings (multi-word entities joined with spaces).

    Heuristic:
      - Run together consecutive capitalized words: "UT Austin" → "ut austin"
      - Strip punctuation from each word
      - Filter sentence-initial question words ("Will", "Does") via _NOT_AN_ENTITY
      - Drop single-letter capitals and pure-numeric tokens

    Imperfect but useful: catches Trump, UT Austin, Elon Musk, Stade Rennais,
    Fox News etc. while filtering out "Will" / "The" / "A" sentence starters.
    Returns lowercased so the corpus key-space doesn't fragment on case.
    """
    if not title:
        return []
    import re as _re
    words = title.split()
    entities = []
    current = []
    for w in words:
        clean = _re.sub(r"[^A-Za-z0-9'-]", "", w)
        if not clean:
            if current:
                entities.append(" ".join(current))
                current = []
            continue
        if (clean[0].isupper() and len(clean) > 1
                and clean.lower() not in _NOT_AN_ENTITY):
            current.append(clean.lower())
        else:
            if current:
                entities.append(" ".join(current))
                current = []
    if current:
        entities.append(" ".join(current))
    return entities


def _extract_verbs_from_title(title):
    """Pull action verbs out of a title (lowercased). Uses module-level
    ACTION_VERBS so both score_specificity and the entity-verb corpus
    operate on the same vocabulary."""
    if not title:
        return []
    tokens = set(re.findall(r"\b[a-z]+\b", title.lower()))
    return list(tokens & ACTION_VERBS)


def _corpus_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "corpus")


def dump_corpus_snapshot(events, poly_markets):
    """Write today's crawl titles to data/corpus/YYYY-MM-DD.json so that
    future scans can compute entity-verb co-occurrence over a rolling
    window. Idempotent — overwriting the file is fine, today's data is
    deterministically reproducible from the same crawl.

    This is the *raw* crawl, not the filtered candidates. We want the full
    breadth so an emerging entity can be detected before it ever ranks high
    enough to enter the candidate pool.
    """
    cdir = _corpus_dir()
    os.makedirs(cdir, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(cdir, f"{date}.json")

    titles = []
    for e in events or []:
        t = (e.get("title") or "").strip()
        if t:
            titles.append({"text": t, "platform": "kalshi"})
    for p in poly_markets or []:
        t = (p.get("question") or "").strip()
        if t:
            titles.append({"text": t, "platform": "polymarket"})

    with open(path, "w") as f:
        json.dump({"date": date, "titles": titles}, f)
    print(f"[scanner] Corpus snapshot: {len(titles)} titles -> {path}", file=sys.stderr)


def _load_entity_verb_corpus(days_back=30):
    """Read corpus snapshots from the last N days (today EXCLUDED — we
    don't want today's scan to be its own history) and build:
      - entity_counter: how many markets each entity has appeared in
      - pair_counter: how many markets each (entity, verb) pair has appeared in
      - days_loaded: how many days of corpus we actually found

    Returns (entity_counter, pair_counter, days_loaded). All-zero counters
    and days_loaded=0 if the corpus dir doesn't exist yet (cold start).
    """
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    cdir = _corpus_dir()
    entity_counter = Counter()
    pair_counter = Counter()
    days_loaded = 0
    if not os.path.isdir(cdir):
        return entity_counter, pair_counter, days_loaded

    today = datetime.now(timezone.utc).date()
    for i in range(1, days_back + 1):
        d = (today - timedelta(days=i)).isoformat()
        path = os.path.join(cdir, f"{d}.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        days_loaded += 1
        for t in data.get("titles", []):
            title = t.get("text") or ""
            entities = _extract_entities_from_title(title)
            verbs = _extract_verbs_from_title(title)
            seen_entities_in_title = set()
            for e in entities:
                if e in seen_entities_in_title:
                    continue  # don't double-count an entity that appears twice
                seen_entities_in_title.add(e)
                entity_counter[e] += 1
                for v in verbs:
                    pair_counter[(e, v)] += 1
    return entity_counter, pair_counter, days_loaded


# Cold-start floor: don't activate entity-verb surprise scoring until we have
# at least this many days of corpus to compare against. With less, "every pair
# is surprising" → everything gets boosted → signal is meaningless.
_ENTITY_VERB_MIN_DAYS = 7
# An entity must have appeared in at least this many markets in the corpus
# window to count as "established enough that a new verb pairing is surprising."
_ENTITY_FAME_FLOOR = 3


def _score_entity_verb_surprise(title, entity_counter, pair_counter, days_loaded):
    """Score the surprise of pairing a known entity with a rare-for-them verb.

    +12 when an entity has appeared ≥ _ENTITY_FAME_FLOOR times in the corpus
    but the (entity, this verb) pair appears 0 times — the off-brand action
    case (Trump+dances when Trump-anything is common but Trump-dances never).
    +6 when the pair appears 1-2 times — emerging unusual pattern.
    0 otherwise (entity is new, or pair is well-established).

    Returns 0 during cold start (insufficient corpus). Takes max across all
    (entity, verb) combinations in the title.
    """
    if days_loaded < _ENTITY_VERB_MIN_DAYS:
        return 0
    entities = _extract_entities_from_title(title)
    verbs = _extract_verbs_from_title(title)
    if not entities or not verbs:
        return 0
    best = 0
    for e in entities:
        ecount = entity_counter.get(e, 0)
        if ecount < _ENTITY_FAME_FLOOR:
            continue  # entity not famous enough yet; this isn't a surprise
        for v in verbs:
            pcount = pair_counter.get((e, v), 0)
            if pcount == 0:
                best = max(best, 12)
            elif pcount <= 2:
                best = max(best, 6)
    return best


def _load_recent_quip_anti_corpus(days_back=7, max_verbatim=40, max_formulas=20):
    """Read recent board files and build a 'do not echo' anti-corpus.

    Per-board, Claude is told not to repeat structures, but it has no memory
    across days, so the same formulas keep returning (e.g. on 2026-05-09..15:
    "tuesday energy" 5x; "[player] can't carry the whole city of [team]" 7x;
    "has entered the chat" 3x).

    This loads all quips from the last `days_back` days of board JSON, finds
    verbatim repeats and frequent 4-grams, and returns a compact prompt
    section. If no boards or the dir is missing, returns an empty string —
    caller treats the section as optional.
    """
    import glob, re
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    boards_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards")
    if not os.path.isdir(boards_dir):
        return ""

    today_utc = datetime.now(timezone.utc).date()
    recent_dates = [(today_utc - timedelta(days=i)).isoformat() for i in range(days_back)]

    quips = []
    for d in recent_dates:
        for path in glob.glob(os.path.join(boards_dir, f"*{d}.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
            except Exception:
                continue
            for m in data.get("board", []):
                q = (m.get("quip") or "").strip()
                if q:
                    quips.append(q)

    if not quips:
        return ""

    # Verbatim block-list — every quip that has shipped in the window AT ALL,
    # not just 2x+ repeats. Lowered from c >= 2 to c >= 1 on 2026-05-16 after
    # observing "outrageously plausible" return the next day under the 2x rule
    # (it had appeared once, so it wasn't blocked, then got generated again).
    # Sort most-repeated first so the heaviest offenders are guaranteed into
    # the prompt's 40-item cap.
    whole = Counter(quips)
    verbatim = sorted(
        [q for q, c in whole.items() if c >= 1],
        key=lambda q: (-whole[q], q),
    )[:max_verbatim]

    # Recurring 4-grams — captures formula recycling across different surface
    # words. Dedupe quips first so a 2x-repeated quip's n-grams don't all
    # masquerade as "formulas." We want patterns that span DIFFERENT quips.
    def tokens(s):
        return re.findall(r"[a-z0-9']+", s.lower())
    unique_quips = list({q for q in quips})
    ngrams = Counter()
    for q in unique_quips:
        seen_in_q = set()
        t = tokens(q)
        for i in range(len(t) - 3):
            g = " ".join(t[i:i + 4])
            if g not in seen_in_q:
                seen_in_q.add(g)
                ngrams[g] += 1
    formulas = [ng for ng, c in ngrams.most_common(50) if c >= 2][:max_formulas]

    if not verbatim and not formulas:
        return ""

    lines = ["", "ANTI-CORPUS — phrasings that already shipped in the last "
             f"{days_back} days. Do NOT echo any of these. Find a new angle."]
    if verbatim:
        lines.append("Verbatim quips already used:")
        for q in verbatim:
            lines.append(f'  - "{q}"')
    if formulas:
        lines.append("Recurring 4-word patterns (these are formula skeletons — "
                     "the surface words may differ but the shape is burned):")
        for ng in formulas:
            lines.append(f'  - "{ng}"')
    return "\n".join(lines)


def match_quips_ai(board):
    """Generate quips for each bet using the style guide + pool as tone reference.
    Falls back to hash-based quips from the pool if the API call fails.

    Hybrid approach:
    - Style guide provides editorial principles and creative direction
    - Pool quips provide tone/voice anchoring (what Dollar Bets sounds like)
    - Claude generates fresh quips that follow the principles and match the voice
    - Recent-board anti-corpus suppresses cross-day formula recycling
    """
    if not ANTHROPIC_API_KEY:
        print("[scanner] No ANTHROPIC_API_KEY set, keeping hash-based quips", file=sys.stderr)
        return board

    # Load style guide (may be None if not enough overrides yet)
    guide = load_style_guide()
    guide_section = build_style_guide_section(guide)

    # Sample pool quips as voice anchors
    pool_sample = build_pool_sample()
    pool_lines = "\n".join(f"- {q}" for q in pool_sample)

    # Recent-board anti-corpus — phrases/formulas Claude shipped in the last 7
    # days that it should now retire. Empty string if no boards on disk yet.
    anti_corpus = _load_recent_quip_anti_corpus(days_back=7)

    # Build market list with context for title rewriting.
    # yes_outcome is the *explicit* label of what the YES side resolves to —
    # without it Claude can describe the opposite outcome on sports vs. markets
    # (e.g., naming the marquee club when the YES is the underdog).
    market_lines = []
    for i, m in enumerate(board):
        yes_price = m.get("yes_price", "?")
        yes_outcome = m.get("yes_sub_title") or ""
        yes_clause = f'YES_RESOLVES_TO: "{yes_outcome}", ' if yes_outcome else ""
        market_lines.append(
            f'{i+1}. "{m["title"]}" '
            f'(${m["payout"]} payout, yes_price: {yes_price}, '
            f'{yes_clause}'
            f'category: {m.get("category", "n/a")}, '
            f'tier: {m.get("tier", "n/a")}, '
            f'platform: {m.get("platform", "kalshi")})'
        )

    # If no style guide exists yet, fall back to pool-picking mode
    if not guide:
        return _match_from_pool(board, market_lines)

    # Hybrid generation mode
    prompt = f"""You are the editorial voice of Dollar Bets — a daily prediction market board with a Craigslist/Drudge aesthetic.

You have TWO jobs for each bet:
1. REWRITE THE TITLE — turn raw market titles into punchy, declarative editorial headlines
2. WRITE A QUIP — a short, wry, one-line editorial comment that sits under the title

{guide_section}

TITLE REWRITING RULES:
- The payout shown is always for the YES outcome. Your title MUST describe the YES outcome as the bet — never the NO side, never the other team, never a creative reframe that flips which side wins. If YES_RESOLVES_TO is given, the title must agree with it. Getting this wrong means the headline sells one bet while the link buys the opposite — a trust-breaking inversion (see 2026-05-15 Marseille/Rennais incident).
- For sports vs. markets specifically: the side named in YES_RESOLVES_TO is the side that wins in your title. If YES_RESOLVES_TO says "Stade Rennais", the headline is about Rennais winning, even if Marseille is the more famous club. No editorial liberty here.
- NEVER phrase as a question. Always declarative: "Will X happen?" becomes "X is happening". "Raptors beat the Cavs tonight", not "Will the Raptors beat the Cavaliers?"
- Replace specific dates with common language: "today", "tonight", "this week", "this month", "this year", "on election day", etc. People can see exact details on the platform
- Drop unnecessary detail, ticker codes, time ranges, and jargon. Give people shorthand
- For "Will X do Y?" markets: make it declarative — "X does Y" or "X to do Y"
- Keep it punchy. Shorter is better. 3-10 words ideal
- The title should make sense on its own without needing the quip

VOICE REFERENCE — here are example quips that capture the Dollar Bets tone. Your generated quips should feel like they belong alongside these, but do NOT copy them:
{pool_lines}

TODAY'S BETS (rewrite title + write quip for each):
{chr(10).join(market_lines)}

QUIP RULES:
- Each quip should be 3-12 words. No period at the end. Natural casing (capitalize proper nouns, song titles, etc — but don't title-case everything)
- Name a specific thing: a film, a song lyric, a meme, a product, a person. Concrete references > abstract metaphors
- For near-certain bets (green tier), understate it — breezy acceptance, not analysis
- For high-payout bets (orange/red/purple tier), go bigger — song lyrics, extended references, committed bits
- Every quip must feel unique to THIS specific bet. If it could apply to 5 different bets, throw it out

INTRA-BOARD PUNCHWORD RULE (added 2026-05-16 after a board shipped with "gravy" in two quips):
- No two quips in THIS BATCH may share a punchline word. A "punchline word" is the distinctive content word that carries the joke — a proper noun ("Oppenheimer"), a vivid noun ("yarmulke"), a slang term ("gravy", "szn"), or a distinctive verb ("haunting", "tanking"). Filler words (the, a, this, will) don't count.
- BEFORE returning your JSON, scan your N quips against each other word-by-word. If two quips share a punchword, rewrite one of them with a different punch.
- Example FAIL: quip 1 = "probably gravy, geologically speaking" + quip 3 = "fine, sure, gravy" → "gravy" used twice → rewrite one.
- Example PASS: quip 1 = "Bejeweled, Vatican edit" + quip 3 = "Oppenheimer but the sequel has a happy ending" → no shared punchword → ship both.

PLACEHOLDER PHRASES TO AVOID (these read as low-effort, used as filler when a real joke wouldn't come):
- "outrageously plausible" — applies to any green-tier bet; not earning its slot
- "fine, sure, whatever" / "fine, sure, gravy" — placeholder cadence
- "probably gravy" — same energy
- "the audacity of this market" — wallpaper; reach for something specific instead
- "Crazier things have happened" — even worse; cliché
- If you find yourself reaching for one of these, the bet probably deserves a more specific reference. Use the pool quips above as voice anchors, not as fallbacks to copy.

- Do NOT repeat the same joke structure across multiple quips
- NEVER write quips that comment on betting itself, the difficulty of predicting, or the community of bettors
- NEVER use vague irony that hedges without committing to a specific reference or stance
- NEVER use alarmed or earnest metaphors for serious topics — the voice is dry and flat, seriousness comes through specificity
- NEVER recycle a formula you've used before — every quip is a unique editorial slot
{anti_corpus}

Return a JSON array of {len(board)} objects, each with "title" and "quip" keys.
Example: [{{"title": "Raptors beat the Cavs tonight", "quip": "fine, sure, whatever"}}]

Respond with ONLY the JSON array."""

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
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
        print("[scanner] Generating quips (hybrid mode)...", file=sys.stderr)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            result = json.loads(raw)
            text = result["content"][0]["text"].strip()

            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
                text = text.strip()

            print(f"[scanner] Claude response: {text[:120]}...", file=sys.stderr)
            entries = json.loads(text)

            if isinstance(entries, list) and len(entries) == len(board):
                # Handle both new format (objects with title+quip) and legacy (plain strings)
                if all(isinstance(e, dict) and e.get("title") and e.get("quip") for e in entries):
                    for i, e in enumerate(entries):
                        board[i]["title"] = e["title"].strip()
                        board[i]["quip"] = e["quip"].strip()
                    print(f"[scanner] Generated {len(board)} titles + quips", file=sys.stderr)
                    return board
                elif all(isinstance(e, str) and e.strip() for e in entries):
                    # Legacy fallback: plain quip strings
                    for i, q in enumerate(entries):
                        board[i]["quip"] = q.strip()
                    print(f"[scanner] Generated {len(board)} quips (legacy format)", file=sys.stderr)
                    return board
                else:
                    print("[scanner] Unexpected entry format, falling back", file=sys.stderr)
            else:
                count = len(entries) if isinstance(entries, list) else "non-list"
                print(f"[scanner] Got {count} entries for {len(board)} bets, falling back", file=sys.stderr)

    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else "no body"
        print(f"[scanner] Generation HTTP {e.code}: {err_body[:200]}, falling back", file=sys.stderr)
    except Exception as e:
        print(f"[scanner] Generation failed: {type(e).__name__}: {e}, falling back", file=sys.stderr)

    # Fallback: pick from pool
    return _match_from_pool(board, market_lines)


def _match_from_pool(board, market_lines):
    """Original pool-picking mode — used as fallback when generation fails
    or when no style guide exists yet."""
    if not ANTHROPIC_API_KEY:
        return board

    quip_lines = [f"{i}. {q}" for i, q in enumerate(ALL_QUIPS)]

    prompt = f"""You are the editorial voice of Dollar Bets, a daily board of prediction market wagers with a Craigslist aesthetic and dry internet humor.

Your job: pick the single best quip from the numbered pool below for each of today's bets. The quip should feel like an insider comment — wry, observational, culturally aware. The best pairings are slightly oblique, not literal.

TODAY'S BETS:
{chr(10).join(market_lines)}

QUIP POOL (pick by number):
{chr(10).join(quip_lines)}

Rules:
- Return a JSON array of {len(board)} integers — the quip index for each bet, in order
- Every index must be unique (no quip used twice)
- Pick quips that are funny *because of* the pairing, not just generically funny
- Do NOT pick the most obvious/literal match — go for the pairing that makes someone smirk

Respond with ONLY the JSON array of integers. Example: [42, 7, 183, 91, ...]"""

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 200,
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
        print("[scanner] Matching quips from pool (fallback mode)...", file=sys.stderr)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            result = json.loads(raw)
            text = result["content"][0]["text"].strip()

            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
                text = text.strip()

            indices = json.loads(text)

            if isinstance(indices, list) and len(indices) == len(board):
                seen = set()
                valid = True
                for idx in indices:
                    if not isinstance(idx, int) or idx < 0 or idx >= len(ALL_QUIPS) or idx in seen:
                        valid = False
                        break
                    seen.add(idx)

                if valid:
                    for i, idx in enumerate(indices):
                        board[i]["quip"] = ALL_QUIPS[idx]
                    print(f"[scanner] Pool-matched quips for {len(board)} markets", file=sys.stderr)

    except Exception as e:
        print(f"[scanner] Pool matching failed: {e}, keeping hash-based quips", file=sys.stderr)

    return board


# ── Cross-platform dedup ────────────────────────────────────

def _normalize_title(title):
    """Normalize a market title for fuzzy matching."""
    t = title.lower().strip()
    # Remove common filler words and punctuation
    t = re.sub(r'[?!.,;:\'"()\[\]{}]', '', t)
    t = re.sub(r'\b(will|the|a|an|in|on|at|to|for|of|be|by|before|after|this|that)\b', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _title_similarity(a, b):
    """Simple word-overlap similarity between two normalized titles.
    Returns a float 0-1 where 1 = perfect match."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def dedup_cross_platform(kalshi_candidates, poly_candidates, similarity_threshold=0.55):
    """Merge Kalshi and Polymarket candidates, keeping the better payout
    when the same market exists on both platforms.

    Returns a single merged list of candidates.
    """
    merged = []
    poly_matched = set()

    # Index Polymarket candidates by normalized title
    poly_index = []
    for i, pc in enumerate(poly_candidates):
        norm = _normalize_title(pc["title"])
        poly_index.append((i, norm, pc))

    for kc in kalshi_candidates:
        k_norm = _normalize_title(kc["title"])

        # Find best Polymarket match
        best_match = None
        best_sim = 0
        best_idx = -1
        for pi, pn, pc in poly_index:
            if pi in poly_matched:
                continue
            sim = _title_similarity(k_norm, pn)
            if sim > best_sim:
                best_sim = sim
                best_match = pc
                best_idx = pi

        if best_sim >= similarity_threshold and best_match:
            # Same market on both platforms — pick better payout for users
            poly_matched.add(best_idx)
            if best_match["payout"] > kc["payout"]:
                # Polymarket has better odds — use it but keep the higher score
                winner = best_match.copy()
                winner["score"] = max(kc["score"], best_match["score"])
                winner["_dedup"] = f"poly wins ({best_match['payout']} > {kc['payout']})"
                merged.append(winner)
                print(f"[scanner:dedup] '{kc['title'][:50]}' — Polymarket wins "
                      f"(${best_match['payout']} vs ${kc['payout']})", file=sys.stderr)
            else:
                # Kalshi has better or equal odds
                kc_copy = kc.copy()
                kc_copy["score"] = max(kc["score"], best_match["score"])
                kc_copy["_dedup"] = f"kalshi wins ({kc['payout']} >= {best_match['payout']})"
                merged.append(kc_copy)
                print(f"[scanner:dedup] '{kc['title'][:50]}' — Kalshi wins "
                      f"(${kc['payout']} vs ${best_match['payout']})", file=sys.stderr)
        else:
            # Kalshi-only market
            merged.append(kc)

    # Add unmatched Polymarket markets
    for pi, pn, pc in poly_index:
        if pi not in poly_matched:
            merged.append(pc)

    kalshi_count = sum(1 for m in merged if m.get("_source") != "polymarket")
    poly_count = sum(1 for m in merged if m.get("_source") == "polymarket")
    dedup_count = sum(1 for m in merged if "_dedup" in m)
    print(f"[scanner:dedup] Merged: {len(merged)} candidates "
          f"({kalshi_count} Kalshi, {poly_count} Poly, {dedup_count} cross-platform picks)",
          file=sys.stderr)

    return merged


# ── Board assembly ───────────────────────────────────────────

def build_board(events, poly_candidates=None):
    """Editorial board assembly — like a newspaper editor picking the front page.

    Args:
        events: Kalshi events list (fetched from Kalshi API)
        poly_candidates: Optional pre-normalized Polymarket candidates
    """

    # Step 1: Cultural hook pre-screen
    # Score all events on "would a normal person care?" before we burn API calls
    scored_events = []
    for e in events:
        hook = score_cultural_hook(e)
        scored_events.append((hook, e))

    scored_events.sort(key=lambda x: x[0], reverse=True)

    # Lever 4 + 5 prep — load these once per build_board call so the per-market
    # scoring loop can apply recurrence penalty and novelty bonus cheaply.
    recent_series_counts = _load_recent_series_recurrence(days_back=7)
    recent_title_vocab = _load_recent_title_vocab(days_back=30)
    if recent_series_counts:
        top_recurring = recent_series_counts.most_common(5)
        print(f"[scanner] Recurring series in last 7d: {top_recurring}", file=sys.stderr)
    if recent_title_vocab:
        print(f"[scanner] Novelty vocab loaded: {len(recent_title_vocab)} content words from last 30d", file=sys.stderr)

    # Lever 7 (added 2026-05-16): entity-verb co-occurrence surprise. Captures
    # the "Trump dances to YMCA" pattern — famous entity paired with an
    # off-brand verb. Cold-start safe: returns 0 until corpus has ≥7 days.
    entity_counter, pair_counter, corpus_days = _load_entity_verb_corpus(days_back=30)
    if corpus_days >= _ENTITY_VERB_MIN_DAYS:
        top_entities = entity_counter.most_common(5)
        print(f"[scanner] Entity-verb corpus: {corpus_days} days, "
              f"{len(entity_counter)} entities, {len(pair_counter)} pairs. "
              f"Top entities: {top_entities}", file=sys.stderr)
    else:
        print(f"[scanner] Entity-verb corpus: {corpus_days} days loaded — "
              f"cold-start floor is {_ENTITY_VERB_MIN_DAYS}, surprise score disabled",
              file=sys.stderr)

    # Step 2: Fetch markets for top ~100 events to get prices + tradability data
    top_n = min(100, len(scored_events))
    print(f"[scanner] Fetching prices for top {top_n} events...", file=sys.stderr)

    candidates = []
    for i, (hook_score, event) in enumerate(scored_events[:top_n]):
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

        # Pick ONE market per event — best combination of payout drama + tradability
        def market_rank(item):
            m, payout, vol = item
            return score_payout_drama(payout) + score_tradability(m)

        valid_markets.sort(key=market_rank, reverse=True)
        best_market, payout, volume = valid_markets[0]

        tier = payout_tier(payout)
        category = event.get("category", "")

        # Build display title
        event_title = event.get("title", "")
        market_title = best_market.get("title", "")
        if len(valid_markets) > 1 and market_title:
            display_title = market_title
        else:
            display_title = event_title or market_title

        quip = generate_quip(display_title, category)

        # === COMPOSITE EDITORIAL SCORE ===
        # Pillars + lever 4 (series-recurrence penalty) + lever 5 (novelty
        # bonus) + lever 6 (specificity score). Lever 6 also softens the
        # tradability penalty: low-volume + high-specificity is a "niche gem,"
        # not a quality failure, and the old -20 penalty was killing exactly
        # the markets we want (Vance/SNL/Waymo/meteor — all low-volume).
        recurrence_penalty = _score_recurrence_penalty(
            best_market.get("ticker", ""), recent_series_counts
        )
        novelty_bonus = _score_novelty_bonus(display_title, recent_title_vocab)
        specificity = score_specificity(display_title)
        ev_surprise = _score_entity_verb_surprise(
            display_title, entity_counter, pair_counter, corpus_days
        )
        trad = score_tradability(best_market)
        if specificity >= 15 and trad < -5:
            # Cap the ghost-town penalty for high-specificity markets at -5
            # instead of letting it sink to -20/-30. Keeps weird gems alive
            # without throwing the gate wide open for genuinely dead markets.
            trad = -5
        editorial_score = (
            hook_score * 2                          # cultural hook (2x weight — most important signal)
            + score_payout_drama(payout)            # payout drama
            + score_freshness(best_market, event)   # freshness
            + trad                                  # tradability (softened for specific markets)
            + recurrence_penalty                    # lever 4: -8 per prior day same Kalshi series ran, cap -24
            + novelty_bonus                         # lever 5: +5/+10 for titles with content words absent from last 30d
            + specificity                           # lever 6: +0..20 for proper-noun density + time window + action verb + length
            + ev_surprise                           # lever 7: +6/+12 entity-verb surprise (famous entity + verb we never see them paired with)
        )

        candidates.append({
            "ticker": best_market.get("ticker", ""),
            "title": display_title,
            "subtitle": event.get("sub_title", ""),
            # yes_sub_title is the human-readable label of what YES resolves to
            # (e.g., "Stade Rennais" for a sub-market `…-REN`). Critical for the
            # title-rewrite prompt: without it Claude can describe the wrong side
            # of a sports vs. market and the headline ends up contradicting the
            # actual bet (see 2026-05-15 Marseille/Rennais inversion).
            "yes_sub_title": best_market.get("yes_sub_title", ""),
            "no_sub_title": best_market.get("no_sub_title", ""),
            "payout": payout,
            "tier": tier,
            "quip": quip,
            "yes_price": best_market.get("yes_ask_dollars", "0"),
            "volume": volume,
            "category": category,
            "close_time": best_market.get("close_time") or best_market.get("expiration_time", ""),
            "url": kalshi_url(event.get('series_ticker', event_ticker)),
            "score": editorial_score,
            "_specificity": specificity,
            "_source": "kalshi",
        })

    print(f"[scanner] {len(candidates)} Kalshi candidates with valid prices", file=sys.stderr)

    # Step 2b: Merge Polymarket candidates (cross-platform dedup)
    if poly_candidates:
        # Patch in entity-verb surprise + record _specificity onto poly
        # candidates here so they share the corpus load with Kalshi. The
        # normalize step ran without corpus access.
        for pc in poly_candidates:
            ev = _score_entity_verb_surprise(
                pc.get("title", ""), entity_counter, pair_counter, corpus_days
            )
            if ev:
                pc["score"] = pc.get("score", 0) + ev
        candidates = dedup_cross_platform(candidates, poly_candidates)
    else:
        print("[scanner] No Polymarket candidates to merge", file=sys.stderr)

    # Step 3: Daily rotation — "newspaper" selection
    QUALITY_FLOOR = 30
    eligible = [c for c in candidates if c["score"] >= QUALITY_FLOOR]
    eligible.sort(key=lambda x: x["score"], reverse=True)

    if len(eligible) < TARGET_PICKS:
        eligible = sorted(candidates, key=lambda x: x["score"], reverse=True)

    print(f"[scanner] {len(eligible)} eligible candidates above quality floor", file=sys.stderr)

    # Date-seeded shuffle for daily variety
    today_seed = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rng = random.Random(today_seed)

    # Split into quality tiers: headliners / solid / deep cuts
    third = max(len(eligible) // 3, 1)
    headliners = eligible[:third]
    solid = eligible[third:third*2]
    deep_cuts = eligible[third*2:]

    rng.shuffle(headliners)
    rng.shuffle(solid)
    rng.shuffle(deep_cuts)

    # Interleave: ~5 headliners, ~4 solid, ~1 deep cut (wildcard)
    shuffled_pool = []
    h, s, d = 0, 0, 0
    pattern = ["head", "head", "solid", "head", "solid", "head", "solid", "head", "solid", "deep"]
    for slot in pattern:
        if slot == "head" and h < len(headliners):
            shuffled_pool.append(headliners[h]); h += 1
        elif slot == "solid" and s < len(solid):
            shuffled_pool.append(solid[s]); s += 1
        elif slot == "deep" and d < len(deep_cuts):
            shuffled_pool.append(deep_cuts[d]); d += 1
    remaining = headliners[h:] + solid[s:] + deep_cuts[d:]
    rng.shuffle(remaining)
    shuffled_pool.extend(remaining)

    # Step 4: Pick board with VARIETY enforcement
    # Target mix: 3 green, 3 yellow, 2 orange, 1 red, 1 purple = 10 total
    # Three passes: fill tier targets, then backfill gaps, both with platform balance
    # - Category caps (max 2 per Kalshi category — no "7 crypto ticks")
    # - Platform balance (max 7 from either platform — guarantees 30%+ mix)
    # - Quip dedup
    CATEGORY_CAP = 2
    PLATFORM_CAP = 7  # max from any single platform (ensures at least 30% mix)

    board = []
    used_quips = set()
    tier_counts = {"green": 0, "yellow": 0, "orange": 0, "red": 0, "purple": 0}
    tier_targets = {"green": 3, "yellow": 3, "orange": 2, "red": 1, "purple": 1}
    category_counts = {}
    platform_counts = {"kalshi": 0, "polymarket": 0}
    used_tickers = set()
    used_titles = set()  # prevent same question appearing twice (e.g. Kalshi price tiers)

    def _can_add(m, enforce_tier_target=True):
        """Check if a market can be added to the board."""
        tier = m["tier"]
        cat = (m.get("category") or "other").lower().strip()
        plat = m.get("platform") or m.get("_source") or "kalshi"

        if enforce_tier_target:
            if tier_counts.get(tier, 0) >= tier_targets.get(tier, 1):
                return False
        if category_counts.get(cat, 0) >= CATEGORY_CAP:
            return False
        if platform_counts.get(plat, 0) >= PLATFORM_CAP:
            return False
        return True

    def _add_to_board(m):
        """Add a market to the board and update counters."""
        tier = m["tier"]
        cat = (m.get("category") or "other").lower().strip()
        plat = m.get("platform") or m.get("_source") or "kalshi"

        quip = m["quip"]
        if quip in used_quips:
            quip = _reroll_quip(m["title"], m["category"], used_quips)
            m["quip"] = quip
        used_quips.add(quip)

        board.append(m)
        used_tickers.add(m.get("ticker"))
        used_titles.add(_normalize_title(m.get("title", "")))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1
        platform_counts[plat] = platform_counts.get(plat, 0) + 1

    def _is_title_dupe(m):
        """Check if a market's title is too similar to one already on the board."""
        norm = _normalize_title(m.get("title", ""))
        for existing in used_titles:
            if _title_similarity(norm, existing) >= 0.55:
                return True
        return False

    # Pass 0: SPECIFICITY RESERVE — reserve up to 2 slots for the highest-
    # specificity markets regardless of composite score. These are the
    # "weird and wonderful" framings (Vance/SNL/Waymo/meteor pattern):
    # specific entity + narrow action + concrete time window. The composite
    # editorial_score alone systematically loses these to sports/celebrity
    # markets that have higher volume and category bonuses.
    #
    # Constraints kept: category cap, title-dedup. Skipped: tier targets,
    # quality floor (a specificity-15 market scoring 28 is still worth one
    # of 10 slots — that's the whole point of the reserve).
    #
    # Pull from the full candidates pool sorted by _specificity, not just
    # `eligible`, so genuinely-niche markets that fail QUALITY_FLOOR can
    # still earn a slot here. Requires _specificity >= 12 (meaning at
    # least 2-3 specificity signals fired).
    SPECIFICITY_RESERVE_SLOTS = 2
    SPECIFICITY_MIN = 12
    weird_pool = sorted(
        [c for c in candidates if c.get("_specificity", 0) >= SPECIFICITY_MIN],
        key=lambda c: (-c.get("_specificity", 0), -c.get("score", 0)),
    )
    specificity_added = 0
    for m in weird_pool:
        if specificity_added >= SPECIFICITY_RESERVE_SLOTS:
            break
        if m.get("ticker") in used_tickers:
            continue
        if _is_title_dupe(m):
            continue
        # Reserve pass ignores tier targets but still respects category cap
        if not _can_add(m, enforce_tier_target=False):
            continue
        _add_to_board(m)
        specificity_added += 1
    if specificity_added:
        titles = [m["title"][:60] for m in board[-specificity_added:]]
        print(f"[scanner] Specificity reserve filled {specificity_added}/{SPECIFICITY_RESERVE_SLOTS}: {titles}",
              file=sys.stderr)
    else:
        print(f"[scanner] No candidates met specificity threshold ({SPECIFICITY_MIN}) — reserve empty", file=sys.stderr)

    # Pass 1: fill each tier up to its target
    for m in shuffled_pool:
        if m.get("ticker") in used_tickers:
            continue
        if _is_title_dupe(m):
            continue
        if not _can_add(m, enforce_tier_target=True):
            continue
        _add_to_board(m)
        if len(board) >= TARGET_PICKS:
            break

    # Pass 2: if any tier slots went unfilled, backfill from remaining candidates
    if len(board) < TARGET_PICKS:
        for m in shuffled_pool:
            if m.get("ticker") in used_tickers:
                continue
            if _is_title_dupe(m):
                continue
            if not _can_add(m, enforce_tier_target=False):
                continue
            _add_to_board(m)
            if len(board) >= TARGET_PICKS:
                break

    print(f"[scanner] Board platform mix (pre-validation): {platform_counts}", file=sys.stderr)

    # Step 5: Validate Polymarket URLs via Gamma API
    # (Polymarket is an SPA — HTTP status is always 200, so we check the API)
    validated_board = []
    kalshi_backfill = [m for m in shuffled_pool
                       if m.get("ticker") not in used_tickers
                       and (m.get("platform") or m.get("_source") or "kalshi") == "kalshi"]

    backfill_idx = 0
    poly_checked = 0
    poly_passed = 0
    poly_failed = 0
    for m in board:
        plat = m.get("platform") or m.get("_source") or "kalshi"
        if plat == "polymarket":
            url = m.get("url", "")
            poly_checked += 1
            if url and not _validate_url(url):
                poly_failed += 1
                print(f"[scanner:validate] DEAD LINK: {url} — swapping for Kalshi", file=sys.stderr)
                # Swap in next available Kalshi candidate
                while backfill_idx < len(kalshi_backfill):
                    replacement = kalshi_backfill[backfill_idx]
                    backfill_idx += 1
                    quip = replacement["quip"]
                    if quip in used_quips:
                        quip = _reroll_quip(replacement["title"], replacement["category"], used_quips)
                        replacement["quip"] = quip
                    used_quips.add(quip)
                    validated_board.append(replacement)
                    break
                continue
            else:
                poly_passed += 1
                print(f"[scanner:validate] OK: {url}", file=sys.stderr)
        validated_board.append(m)

    board = validated_board
    print(f"[scanner:validate] Polymarket URLs checked: {poly_checked}, "
          f"passed: {poly_passed}, failed: {poly_failed}", file=sys.stderr)

    # Recount after validation
    final_kalshi = sum(1 for m in board if (m.get("platform") or m.get("_source") or "kalshi") == "kalshi")
    final_poly = sum(1 for m in board if (m.get("platform") or m.get("_source") or "kalshi") == "polymarket")
    print(f"[scanner] Board platform mix (final): kalshi={final_kalshi}, polymarket={final_poly}", file=sys.stderr)

    # Sort: smallest to largest payout
    board.sort(key=lambda x: x["payout"])

    # AI quip matching — pick best quip from pool for each bet
    board = match_quips_ai(board)

    # Clean up internal fields before output
    for m in board:
        m.pop("_source", None)
        m.pop("_title_lower", None)
        m.pop("_dedup", None)

    return board


# ── Main ─────────────────────────────────────────────────────

def main():
    use_sample = "--sample" in sys.argv

    if use_sample:
        print("[scanner] Using sample data", file=sys.stderr)
        board = pick_sample_board()
    else:
        # Fetch from both platforms in parallel (sequential for simplicity)
        print("[scanner] Fetching events from Kalshi...", file=sys.stderr)
        events = fetch_all_events()

        print("[scanner] Fetching markets from Polymarket...", file=sys.stderr)
        poly_candidates = []
        poly_raw = []
        try:
            poly_raw = fetch_polymarket_markets()
            for pm in poly_raw:
                candidate = normalize_poly_market(pm)
                if candidate:
                    poly_candidates.append(candidate)
            print(f"[scanner:poly] {len(poly_candidates)} valid Polymarket candidates", file=sys.stderr)
        except Exception as e:
            print(f"[scanner:poly] FAILED — falling back to Kalshi only: {e}", file=sys.stderr)
            poly_candidates = []

        # Dump today's crawl titles to the corpus so future scans can compute
        # entity-verb co-occurrence over a rolling window. Best-effort —
        # corpus failure shouldn't crash the scan.
        try:
            dump_corpus_snapshot(events, poly_raw)
        except Exception as e:
            print(f"[scanner] Corpus dump failed (non-fatal): {e}", file=sys.stderr)

        if not events and not poly_candidates:
            print("[scanner] No markets from either platform, falling back to sample", file=sys.stderr)
            board = pick_sample_board()
        elif not events:
            print("[scanner] No Kalshi events, using Polymarket only", file=sys.stderr)
            board = build_board([], poly_candidates=poly_candidates)
        else:
            print(f"[scanner] {len(events)} Kalshi events found", file=sys.stderr)
            board = build_board(events, poly_candidates=poly_candidates)

    # Count platform mix for logging
    kalshi_on_board = sum(1 for m in board if m.get("platform") != "polymarket")
    poly_on_board = sum(1 for m in board if m.get("platform") == "polymarket")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_count": len(board),
        "source": "kalshi+polymarket",
        "platform_mix": {"kalshi": kalshi_on_board, "polymarket": poly_on_board},
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
            "url": kalshi_url(m['ticker']),
            "score": 50,
        })
    scored.sort(key=lambda x: x["payout"])
    return scored[:TARGET_PICKS]


if __name__ == "__main__":
    main()
