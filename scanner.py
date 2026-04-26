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
    Sweet spot is 5x-100x. Too low = boring, too high = gimmicky."""
    if payout is None:
        return -50
    if 10 <= payout <= 50:
        return 25          # the sweet spot — dramatic but credible
    elif 5 <= payout <= 100:
        return 15           # still interesting
    elif 3 <= payout <= 200:
        return 5            # fine
    elif payout <= 2:
        return -15          # too likely, no drama
    elif payout > 1000:
        return -10          # lottery ticket — fun once, not 7 times
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


def match_quips_ai(board):
    """Use Claude to pick the best quip from our curated pool for each bet.
    Falls back to the existing hash-based quips if the API call fails."""
    if not ANTHROPIC_API_KEY:
        print("[scanner] No ANTHROPIC_API_KEY set, keeping hash-based quips", file=sys.stderr)
        return board

    # Build numbered quip pool (send all quips with indices)
    quip_lines = [f"{i}. {q}" for i, q in enumerate(ALL_QUIPS)]

    # Build market list
    market_lines = []
    for i, m in enumerate(board):
        market_lines.append(f"{i+1}. \"{m['title']}\" (${m['payout']} payout, category: {m.get('category', 'n/a')})")

    prompt = f"""You are the editorial voice of Dollar Bets, a daily board of prediction market wagers with a Craigslist aesthetic and dry internet humor.

Your job: pick the single best quip from the numbered pool below for each of today's bets. The quip should feel like an insider comment — wry, observational, culturally aware. The best pairings are slightly oblique, not literal. A bet about snow doesn't need a weather quip — it might need "the vibes are off but the math works."

TODAY'S BETS:
{chr(10).join(market_lines)}

QUIP POOL (pick by number):
{chr(10).join(quip_lines)}

Rules:
- Return a JSON array of {len(board)} integers — the quip index for each bet, in order
- Every index must be unique (no quip used twice)
- Pick quips that are funny *because of* the pairing, not just generically funny
- Prefer quips that a reader would screenshot and share
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
        print("[scanner] Calling Claude API for quip matching...", file=sys.stderr)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            result = json.loads(raw)
            text = result["content"][0]["text"].strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
                text = text.strip()
            print(f"[scanner] Claude response: {text[:120]}...", file=sys.stderr)
            indices = json.loads(text)

            if isinstance(indices, list) and len(indices) == len(board):
                # Validate: all ints, in range, unique
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
                    print(f"[scanner] AI matched quips for {len(board)} markets", file=sys.stderr)
                else:
                    print(f"[scanner] AI returned invalid indices, keeping hash-based quips", file=sys.stderr)
            else:
                print(f"[scanner] AI returned {len(indices) if isinstance(indices, list) else 'non-list'} for {len(board)} markets, keeping hash-based quips", file=sys.stderr)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else "no body"
        print(f"[scanner] AI quip match HTTP {e.code}: {err_body[:200]}, keeping hash-based quips", file=sys.stderr)
    except Exception as e:
        print(f"[scanner] AI quip match failed: {type(e).__name__}: {e}, keeping hash-based quips", file=sys.stderr)

    return board


# ── Board assembly ───────────────────────────────────────────

def build_board(events):
    """Editorial board assembly — like a newspaper editor picking the front page."""

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
            "url": f"https://kalshi.com/markets/{event.get('series_ticker', event_ticker)}",
            "score": editorial_score,
        })

    print(f"[scanner] {len(candidates)} candidates with valid prices", file=sys.stderr)

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
    # - Payout tier limits (don't let one color dominate)
    # - Category caps (max 2 per Kalshi category — no "7 crypto ticks")
    # - Quip dedup
    CATEGORY_CAP = 2

    board = []
    used_quips = set()
    tier_counts = {"green": 0, "yellow": 0, "orange": 0, "red": 0, "purple": 0}
    tier_limits = {"green": 3, "yellow": 3, "orange": 3, "red": 2, "purple": 2}
    category_counts = {}

    for m in shuffled_pool:
        tier = m["tier"]
        cat = (m.get("category") or "other").lower().strip()

        # Enforce payout tier diversity
        if tier_counts.get(tier, 0) >= tier_limits.get(tier, 3):
            continue

        # Enforce category diversity
        if category_counts.get(cat, 0) >= CATEGORY_CAP:
            continue

        # Ensure unique quip
        quip = m["quip"]
        if quip in used_quips:
            quip = _reroll_quip(m["title"], m["category"], used_quips)
            m["quip"] = quip
        used_quips.add(quip)

        board.append(m)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1

        if len(board) >= TARGET_PICKS:
            break

    # Sort: smallest to largest payout
    board.sort(key=lambda x: x["payout"])

    # AI quip matching — pick best quip from pool for each bet
    board = match_quips_ai(board)

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
