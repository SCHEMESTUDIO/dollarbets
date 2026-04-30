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


def fetch_polymarket_markets(max_markets=2000):
    """Fetch active markets from Polymarket's Gamma API.

    Caps at max_markets to avoid timeouts and excessive API calls.
    Polymarket has 10,000+ markets — we only need the most liquid ones.
    Sorted by volume descending so we get the best markets first.
    """
    all_markets = []
    offset = 0
    limit = 100

    while len(all_markets) < max_markets:
        try:
            data = _poly_api_get("/markets", {
                "active": "true",
                "closed": "false",
                "limit": str(limit),
                "offset": str(offset),
                "order": "volume",
                "ascending": "false",
            })
        except Exception as e:
            print(f"[scanner:poly] Fetch error at offset {offset}: {e}", file=sys.stderr)
            break

        if not data or not isinstance(data, list):
            break

        all_markets.extend(data)
        print(f"[scanner:poly] Markets page: {len(data)} (total: {len(all_markets)})", file=sys.stderr)

        if len(data) < limit:
            break
        offset += limit
        time.sleep(0.2)  # respect rate limits

    print(f"[scanner:poly] Fetched {len(all_markets)} markets (cap: {max_markets})", file=sys.stderr)
    return all_markets


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

    editorial_score = (
        hook_score
        + score_payout_drama(payout)
        + fresh_score
        + trad_score
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

    # Categories normal people care about
    fun_categories = ["entertainment", "culture", "science", "climate", "weather",
                      "sports", "tech", "world"]
    niche_categories = ["fed", "treasury", "gdp", "inflation", "interest rate",
                        "economics", "financial"]

    for cat in fun_categories:
        if cat in category:
            score += 15
            break

    for cat in niche_categories:
        if cat in category:
            score -= 20
            break

    # Names and topics people actually talk about
    watercooler = [
        "elon", "trump", "taylor swift", "bitcoin", "snow",
        "earthquake", "ufo", "alien", "ai", "robot",
        "tiktok", "record", "first", "ever", "celebrity",
        "kanye", "drake", "super bowl", "oscar", "grammy",
        "olympics", "mars", "moon", "asteroid", "pope",
        "viral", "meme", "scandal", "hurricane", "volcano",
        "spacex", "tesla", "apple", "google", "netflix",
        "nuclear", "war", "peace", "extinct", "banned",
        "nba", "nfl", "mlb", "world cup", "premier league",
    ]
    kw_hits = sum(1 for kw in watercooler if kw in full_text)
    score += min(kw_hits * 8, 20)  # diminishing returns, cap at 20

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

    # Penalize jargon that makes eyes glaze over
    jargon = ["basis points", "yield curve", "quarterly", "index",
              "benchmark", "fiscal", "monetary", "regulatory",
              "seasonally adjusted", "year-over-year", "bps"]
    for kw in jargon:
        if kw in full_text:
            score -= 20
            break

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
    elif volume < 10:
        score -= 20  # ghost town

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
               "scorsese", "prometheus", "hunger games"]
    music = ["miss the earth", "miss my wife", "midwest princess", "running up that hill",
             "them apples", "i'm the problem", "start the fire", "mama said", "somebody once",
             "bohemian", "under pressure", "sound of silence", "shake it off", "long long time"]
    internet_meme = ["diet dr. pepper", "60% of the time", "this is fine", "sir this is",
                     "stonks", "task failed", "suffering from success", "money printer",
                     "imma head out", "it's giving", "understood the assignment",
                     "no thoughts just vibes", "chaotic good", "audacity of hype",
                     "main character", "the meme wrote"]
    books_hist = ["moneyball", "freakonomics", "invisible hand", "hemingway",
                  "art of war", "kafka", "wikipedia edit"]

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
                    "highlight reel", "postgame", "press conference"]
    if any(k in q for k in sports_words):
        return "sports"

    # --- Tone / voice clusters ---
    if any(k in q for k in ["chaos", "chaotic", "unhinged", "cooked", "glitching",
                             "apocalyptic", "unwell", "demolition", "intrusive"]):
        return "chaos_energy"
    if any(k in q for k in ["spreadsheet", "data", "analytics", "math", "chart",
                             "number go up", "algorithm", "stat sheet", "financial"]):
        return "data_nerd"
    if any(k in q for k in ["group chat", "twitter", "reddit", "substack", "podcast",
                             "linkedin", "slack", "reply guys", "discourse", "timeline",
                             "notifications", "screenshot", "browser tab", "op-eds"]):
        return "internet_discourse"
    if any(k in q for k in ["uber driver", "lyft driver", "barber", "cab driver",
                             "coworker", "dad will text", "cousin", "mother-in-law",
                             "partner", "therapist", "your ex"]):
        return "person_has_opinion"
    if any(k in q for k in ["comedy", "lol", "funny", "entertainment", "popcorn",
                             "amusing", "hilarious", "jokes"]):
        return "comedy_framing"
    if any(k in q for k in ["existential", "meaning", "universe", "simulation",
                             "prophecy", "manifesting", "fate", "gods"]):
        return "cosmic_vibes"
    if any(k in q for k in ["dollar", "wallet", "wager", "bet ", "invest",
                             "gambling", "price tag", "spare change", "receipt"]):
        return "meta_wager"
    if any(k in q for k in ["whisper", "quiet", "gentle", "slow", "little",
                             "footnote", "passing", "soft", "plausible",
                             "reasonable", "defensible"]):
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


def match_quips_ai(board):
    """Generate quips for each bet using the style guide + pool as tone reference.
    Falls back to hash-based quips from the pool if the API call fails.

    Hybrid approach:
    - Style guide provides editorial principles and creative direction
    - Pool quips provide tone/voice anchoring (what Dollar Bets sounds like)
    - Claude generates fresh quips that follow the principles and match the voice
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

    # Build market list
    market_lines = []
    for i, m in enumerate(board):
        market_lines.append(
            f'{i+1}. "{m["title"]}" '
            f'(${m["payout"]} payout, category: {m.get("category", "n/a")}, '
            f'tier: {m.get("tier", "n/a")})'
        )

    # If no style guide exists yet, fall back to pool-picking mode
    if not guide:
        return _match_from_pool(board, market_lines)

    # Hybrid generation mode
    prompt = f"""You are the editorial voice of Dollar Bets — a daily prediction market board with a Craigslist/Drudge aesthetic. You write quips: short, wry, one-line editorial comments that sit under each bet.

{guide_section}

VOICE REFERENCE — here are example quips that capture the Dollar Bets tone. Your generated quips should feel like they belong alongside these, but do NOT copy them:
{pool_lines}

TODAY'S BETS (write one quip each):
{chr(10).join(market_lines)}

Rules:
- Write exactly {len(board)} quips, one per bet, in order
- Each quip should be 3-12 words. No period at the end. Natural casing (capitalize proper nouns, song titles, etc — but don't title-case everything)
- Name a specific thing: a film, a song lyric, a meme, a product, a person. Concrete references > abstract metaphors
- For near-certain bets (green tier), understate it — breezy acceptance, not analysis
- For high-payout bets (orange/red/purple tier), go bigger — song lyrics, extended references, committed bits
- Every quip must feel unique to THIS specific bet. If it could apply to 5 different bets, throw it out
- Do NOT repeat the same joke structure across multiple quips
- NEVER write quips that comment on betting itself, the difficulty of predicting, or the community of bettors
- NEVER use vague irony that hedges without committing to a specific reference or stance
- NEVER use alarmed or earnest metaphors for serious topics — the voice is dry and flat, seriousness comes through specificity
- NEVER recycle a formula you've used before — every quip is a unique editorial slot
- Return a JSON array of {len(board)} strings

Respond with ONLY the JSON array. Example: ["quip one", "quip two", ...]"""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
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
            quips = json.loads(text)

            if isinstance(quips, list) and len(quips) == len(board):
                # Validate: all strings, non-empty
                if all(isinstance(q, str) and q.strip() for q in quips):
                    for i, q in enumerate(quips):
                        board[i]["quip"] = q.strip()
                    print(f"[scanner] Generated {len(board)} custom quips", file=sys.stderr)
                    return board
                else:
                    print("[scanner] Some generated quips were empty, falling back", file=sys.stderr)
            else:
                count = len(quips) if isinstance(quips, list) else "non-list"
                print(f"[scanner] Got {count} quips for {len(board)} bets, falling back", file=sys.stderr)

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
        # All five pillars combined
        editorial_score = (
            hook_score                              # cultural hook
            + score_payout_drama(payout)            # payout drama
            + score_freshness(best_market, event)   # freshness
            + score_tradability(best_market)         # tradability
        )

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
            "url": kalshi_url(event.get('series_ticker', event_ticker)),
            "score": editorial_score,
            "_source": "kalshi",
        })

    print(f"[scanner] {len(candidates)} Kalshi candidates with valid prices", file=sys.stderr)

    # Step 2b: Merge Polymarket candidates (cross-platform dedup)
    if poly_candidates:
        candidates = dedup_cross_platform(candidates, poly_candidates)
    else:
        print("[scanner] No Polymarket candidates to merge", file=sys.stderr)

    # Step 3: Daily rotation — "newspaper" selection
    QUALITY_FLOOR = 15
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

    # Interleave: ~4 headliners, ~3 solid, ~3 deep cuts
    shuffled_pool = []
    h, s, d = 0, 0, 0
    pattern = ["head", "head", "solid", "head", "solid", "deep", "head", "solid", "deep", "deep"]
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
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1
        platform_counts[plat] = platform_counts.get(plat, 0) + 1

    # Pass 1: fill each tier up to its target
    for m in shuffled_pool:
        if m.get("ticker") in used_tickers:
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
