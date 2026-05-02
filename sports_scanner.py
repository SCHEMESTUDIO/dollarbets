#!/usr/bin/env python3
"""
Dollar Bets — Sports Board Scanner ("Underdogs")

The sports equivalent of scanner.py. Pulls live odds from The Odds API,
scores markets for entertainment value across all payout tiers
(respectable → generational), generates Claude quips, and outputs
board JSON compatible with the existing generate.py pipeline.

Outputs to data/boards/sports-YYYY-MM-DD.json

Usage:
    ODDS_API_KEY=xxx ANTHROPIC_API_KEY=xxx python sports_scanner.py
    ODDS_API_KEY=xxx python sports_scanner.py --no-ai   # skip Claude quips
    python sports_scanner.py --sample                    # use sample data
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
from datetime import datetime, timezone, timedelta

# ── Config ───────────────────────────────────────────────────

ODDS_API = "https://api.the-odds-api.com/v4"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TARGET_PICKS = 10

# Books to pull from — priority order (best deep link support first)
TARGET_BOOKS = [
    "fanduel",
    "draftkings",
    "betmgm",
    "betrivers",
    "bovada",
    "betonlineag",
]

# Preferred book for deep links (used when multiple books have the same market)
DEEP_LINK_PRIORITY = ["fanduel", "draftkings", "betmgm", "betrivers"]

# Sports to scan
SPORTS = [
    "basketball_nba",
    "baseball_mlb",
    "icehockey_nhl",
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "basketball_ncaab",
    "mma_mixed_martial_arts",
    "soccer_usa_mls",
    "soccer_epl",
    "soccer_uefa_champs_league",
]

SPORT_DISPLAY = {
    "basketball_nba": "NBA",
    "baseball_mlb": "MLB",
    "icehockey_nhl": "NHL",
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "NCAAF",
    "basketball_ncaab": "NCAAB",
    "mma_mixed_martial_arts": "MMA",
    "soccer_usa_mls": "MLS",
    "soccer_epl": "EPL",
    "soccer_uefa_champs_league": "UCL",
}


# ── API helpers ──────────────────────────────────────────────

def odds_api_get(path, params=None):
    """GET request to The Odds API with retry and quota tracking."""
    if not ODDS_API_KEY:
        print("[sports] ERROR: ODDS_API_KEY not set", file=sys.stderr)
        return None

    url = f"{ODDS_API}{path}"
    if params is None:
        params = {}
    params["apiKey"] = ODDS_API_KEY
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    url += f"?{qs}"

    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "DollarBets/1.0"
    })

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                remaining = resp.headers.get("x-requests-remaining", "?")
                used = resp.headers.get("x-requests-used", "?")
                print(f"[sports] API quota: {used} used, {remaining} remaining", file=sys.stderr)
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[sports] Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 401:
                print("[sports] ERROR: Invalid API key", file=sys.stderr)
                return None
            if e.code == 422:
                # Sport might not be in season
                print(f"[sports] Sport not available or invalid params", file=sys.stderr)
                return None
            print(f"[sports] API error {e.code}: {url}", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            print(f"[sports] Network error: {e}", file=sys.stderr)
            return None
    return None


# ── Odds math ────────────────────────────────────────────────

def american_to_decimal(american):
    """Convert American odds to decimal odds."""
    if american > 0:
        return (american / 100) + 1
    else:
        return (100 / abs(american)) + 1


def american_to_implied_prob(american):
    """Convert American odds to implied probability."""
    if american < 0:
        return abs(american) / (abs(american) + 100)
    else:
        return 100 / (american + 100)


def decimal_to_payout(decimal_odds):
    """$1 bet → payout at given decimal odds."""
    return round(decimal_odds, 2)


def payout_tier(payout):
    """Same tier system as main board."""
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


# ── Scoring ──────────────────────────────────────────────────

def score_entertainment(market):
    """
    Score a sports market for entertainment value.
    Same philosophy as main scanner's cultural hook + payout drama.
    """
    score = 0.0
    payout = market.get("payout_raw", 1)
    sport = market.get("sport", "")
    market_type = market.get("market_type", "")
    matchup = market.get("matchup", "").lower()
    desc = market.get("description", "").lower()

    # ── Payout drama (same curve as main scanner) ──
    if payout <= 1.5:
        score += 2       # too boring on its own
    elif payout <= 3:
        score += 8       # respectable — solid value
    elif payout <= 7:
        score += 15      # alive — this is interesting
    elif payout <= 15:
        score += 20      # heater territory
    elif payout <= 50:
        score += 18      # filthy — long shot but compelling
    else:
        score += 12      # generational — fun to dream on

    # ── Sport popularity boost ──
    tier1_sports = ["basketball_nba", "americanfootball_nfl"]
    tier2_sports = ["baseball_mlb", "icehockey_nhl", "soccer_epl"]
    if sport in tier1_sports:
        score += 5
    elif sport in tier2_sports:
        score += 3

    # ── Market type variety bonus ──
    if market_type == "h2h":
        score += 3   # moneyline — easiest to understand
    elif market_type == "spreads":
        score += 2
    elif market_type == "totals":
        score += 1

    # ── Underdog bonus — the brand sweet spot ──
    # Underdogs with moderate payouts are the most interesting
    implied_prob = market.get("implied_probability", 0.5)
    if 0.20 <= implied_prob <= 0.45:
        score += 8   # genuine underdog — exciting
    elif 0.10 <= implied_prob < 0.20:
        score += 5   # real long shot
    elif implied_prob < 0.10:
        score += 3   # pray bet — fun but unlikely

    # ── Rivalry / big team boost ──
    big_teams = [
        "lakers", "celtics", "warriors", "knicks", "bulls",
        "cowboys", "chiefs", "eagles", "49ers", "packers",
        "yankees", "dodgers", "red sox", "mets",
        "manchester united", "liverpool", "real madrid", "barcelona",
        "maple leafs", "rangers", "bruins", "canadiens",
    ]
    for team in big_teams:
        if team in matchup:
            score += 3
            break

    # ── Freshness: games starting soon get a boost ──
    commence = market.get("commence_time", "")
    if commence:
        try:
            game_time = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            hours_until = (game_time - datetime.now(timezone.utc)).total_seconds() / 3600
            if 0 < hours_until <= 6:
                score += 8   # tonight's games
            elif 6 < hours_until <= 24:
                score += 5   # tomorrow
            elif 24 < hours_until <= 72:
                score += 2
        except (ValueError, TypeError):
            pass

    return score


# ── Market extraction ────────────────────────────────────────

def fetch_sport_odds(sport_key):
    """Fetch standard odds for a sport (h2h, spreads, totals)."""
    params = {
        "regions": "us,us2",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "includeLinks": "true",
        "includeSids": "true",
        "bookmakers": ",".join(TARGET_BOOKS),
    }
    return odds_api_get(f"/sports/{sport_key}/odds", params) or []


def fetch_event_props(sport_key, event_id):
    """
    Fetch player props + alternate lines for a specific event.
    These are where the big payouts (orange/red/purple tiers) live.
    Costs 1 API credit per call, so use selectively.
    """
    params = {
        "regions": "us",
        "markets": "alternate_spreads,alternate_totals,player_points,player_threes,player_rebounds,player_assists",
        "oddsFormat": "american",
        "includeLinks": "true",
        "bookmakers": ",".join(DEEP_LINK_PRIORITY[:2]),  # just top 2 to save data
    }
    return odds_api_get(f"/sports/{sport_key}/events/{event_id}/odds", params)


def extract_markets(events, sport_key):
    """
    Extract individual bet candidates from events.
    For each event × market × outcome, we create a candidate
    and keep the best-available deep link.
    """
    candidates = []
    sport_display = SPORT_DISPLAY.get(sport_key, sport_key.upper())

    for event in events:
        event_id = event.get("id", "")
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        commence = event.get("commence_time", "")
        matchup = f"{away} @ {home}"

        # Collect all outcomes across bookmakers, pick best odds + best deep link
        # Key: (market_type, outcome_name, point)
        best_by_outcome = {}

        for bookmaker in event.get("bookmakers", []):
            book_key = bookmaker.get("key", "")
            book_title = bookmaker.get("title", "")
            book_link = bookmaker.get("link", "")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")

                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    price = outcome.get("price", 0)
                    point = outcome.get("point")
                    outcome_link = outcome.get("link", "")

                    if price == 0:
                        continue

                    # Skip extreme chalk (< -2000) — too boring even for green tier
                    if price < -2000:
                        continue

                    out_key = (market_key, name, point)
                    decimal_odds = american_to_decimal(price)
                    implied_prob = american_to_implied_prob(price)

                    # Determine deep link quality
                    has_betslip_link = bool(outcome_link and ("betslip" in outcome_link.lower()
                                            or "outcomes=" in outcome_link
                                            or "options=" in outcome_link
                                            or "coupon=" in outcome_link
                                            or "selectionId" in outcome_link))

                    existing = best_by_outcome.get(out_key)
                    # Prefer: best deep link quality, then best odds
                    replace = False
                    if not existing:
                        replace = True
                    elif has_betslip_link and not existing.get("_has_betslip"):
                        replace = True  # upgrade to a book with real deep links
                    elif has_betslip_link == existing.get("_has_betslip") and decimal_odds > existing["decimal_odds"]:
                        replace = True  # same link quality, better odds

                    if replace:
                        # Build description
                        player_desc = outcome.get("description", "")  # player name for props
                        if market_key == "h2h":
                            desc = f"{name} win"
                            if name == home:
                                desc = f"{name} win (home)"
                        elif market_key in ("spreads", "alternate_spreads"):
                            spread_str = f"+{point}" if point and point > 0 else str(point)
                            desc = f"{name} {spread_str}"
                        elif market_key in ("totals", "alternate_totals"):
                            direction = "Over" if name == "Over" else "Under"
                            desc = f"{direction} {point} total points"
                        elif market_key == "player_points":
                            desc = f"{player_desc} {name.lower()} {point} points"
                        elif market_key == "player_threes":
                            desc = f"{player_desc} {name.lower()} {point} threes"
                        elif market_key == "player_rebounds":
                            desc = f"{player_desc} {name.lower()} {point} rebounds"
                        elif market_key == "player_assists":
                            desc = f"{player_desc} {name.lower()} {point} assists"
                        elif market_key.startswith("player_"):
                            stat = market_key.replace("player_", "")
                            desc = f"{player_desc} {name.lower()} {point} {stat}"
                        else:
                            desc = f"{name}"

                        best_by_outcome[out_key] = {
                            "event_id": event_id,
                            "sport": sport_key,
                            "sport_display": sport_display,
                            "home_team": home,
                            "away_team": away,
                            "matchup": matchup,
                            "commence_time": commence,
                            "market_type": market_key,
                            "outcome_name": name,
                            "description": desc,
                            "american_odds": price,
                            "decimal_odds": decimal_odds,
                            "implied_probability": round(implied_prob, 3),
                            "payout_raw": decimal_to_payout(decimal_odds),
                            "bookmaker": book_key,
                            "bookmaker_title": book_title,
                            "deep_link": outcome_link or book_link or "",
                            "point": point,
                            "_has_betslip": has_betslip_link,
                        }

        candidates.extend(best_by_outcome.values())

    return candidates


# ── Board assembly ───────────────────────────────────────────

def build_sports_board(candidates):
    """
    Assemble a 10-pick board from scored candidates.
    Same philosophy as main scanner: tier targets, variety enforcement.
    """
    # Score everything
    for c in candidates:
        c["score"] = score_entertainment(c)
        c["tier"] = payout_tier(c["payout_raw"])

    # Sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    board = []
    tier_counts = {"green": 0, "yellow": 0, "orange": 0, "red": 0, "purple": 0}
    # Sports odds skew shorter than prediction markets, so we shift targets:
    # More greens/yellows available, but we still WANT reds/purples for drama
    tier_targets = {"green": 3, "yellow": 3, "orange": 2, "red": 1, "purple": 1}
    sport_counts = {}
    market_type_counts = {}
    used_events = set()

    SPORT_CAP = 4       # max picks from one sport
    MARKET_TYPE_CAP = 5  # max picks of one market type

    def can_add(c, strict_tiers=True):
        tier = c["tier"]
        sport = c["sport"]
        mtype = c["market_type"]

        if strict_tiers and tier_counts.get(tier, 0) >= tier_targets.get(tier, 1):
            return False
        if sport_counts.get(sport, 0) >= SPORT_CAP:
            return False
        if market_type_counts.get(mtype, 0) >= MARKET_TYPE_CAP:
            return False
        # One pick per event
        if c["event_id"] in used_events:
            return False
        return True

    def add_to_board(c):
        board.append(c)
        tier_counts[c["tier"]] = tier_counts.get(c["tier"], 0) + 1
        sport_counts[c["sport"]] = sport_counts.get(c["sport"], 0) + 1
        market_type_counts[c["market_type"]] = market_type_counts.get(c["market_type"], 0) + 1
        used_events.add(c["event_id"])

    # Pass 1: fill tier targets
    for c in candidates:
        if can_add(c, strict_tiers=True):
            add_to_board(c)
        if len(board) >= TARGET_PICKS:
            break

    # Pass 2: backfill if needed
    if len(board) < TARGET_PICKS:
        for c in candidates:
            if c in board:
                continue
            if can_add(c, strict_tiers=False):
                add_to_board(c)
            if len(board) >= TARGET_PICKS:
                break

    # Sort by payout (smallest to largest, matching main board)
    board.sort(key=lambda c: c["payout_raw"])

    return board


# ── Format for output ────────────────────────────────────────

def format_board_entry(candidate):
    """Convert a candidate to the standard board JSON format."""
    payout = candidate["payout_raw"]
    tier = candidate["tier"]

    # Generate a stable ticker
    raw = f"{candidate['event_id']}-{candidate['market_type']}-{candidate['outcome_name']}-{candidate.get('point', '')}"
    ticker = f"SB-{hashlib.md5(raw.encode()).hexdigest()[:8].upper()}"

    # Placeholder quip (replaced by AI later)
    quip = _hash_quip(candidate["description"])

    return {
        "ticker": ticker,
        "title": candidate["description"],
        "payout": payout,
        "tier": tier,
        "quip": quip,
        "yes_price": f"{candidate['implied_probability']:.2f}",
        "category": candidate["sport_display"],
        "platform": candidate["bookmaker"],
        "platform_display": candidate["bookmaker_title"],
        "url": candidate["deep_link"],
        "close_time": candidate["commence_time"],
        "sport": candidate["sport"],
        "sport_display": candidate["sport_display"],
        "matchup": candidate["matchup"],
        "market_type": candidate["market_type"],
        "american_odds": candidate["american_odds"],
        "implied_probability": candidate["implied_probability"],
        "has_deep_link": candidate.get("_has_betslip", False),
        "_source": "odds_api",
    }


# ── Quip generation ──────────────────────────────────────────

# Fallback quips (hash-based, replaced by Claude when available)
SPORTS_FALLBACK_QUIPS = [
    "the math checks out",
    "load management for your wallet",
    "another day at the office",
    "rent money",
    "the safe play",
    "business as usual",
    "steady hands",
    "water is wet",
    "bread and butter",
    "checking all the boxes",
    "the spreadsheet special",
    "routine maintenance",
    "the fundamentals",
    "paint drying, but profitable",
    "set it and forget it",
    "as sure as gravity",
    "the boring middle",
    "clock in, cash out",
    "the due diligence play",
    "autopilot engaged",
    "like bringing a calculator to a knife fight",
    "the house always wins, but today so do you",
    "vibes say yes",
    "chaos theory in action",
    "somewhere a stats nerd is screaming",
    "the audacity of hope",
    "stranger things have happened",
    "YOLO but with a spreadsheet",
    "calling the long shot from the parking lot",
    "fortune favours the bold (and occasionally the reckless)",
]


def _hash_quip(title):
    """Deterministic quip from title hash. Placeholder for Claude override."""
    h = int(hashlib.md5(title.encode()).hexdigest(), 16)
    return SPORTS_FALLBACK_QUIPS[h % len(SPORTS_FALLBACK_QUIPS)]


def generate_quips_ai(board):
    """
    Use Claude to generate editorial quips for each sports pick.
    Same approach as main scanner's match_quips_ai() but sports-tuned.
    """
    if not ANTHROPIC_API_KEY:
        print("[sports] No ANTHROPIC_API_KEY — using fallback quips", file=sys.stderr)
        return board

    market_lines = []
    for i, m in enumerate(board):
        odds_str = f"+{m['american_odds']}" if m['american_odds'] > 0 else str(m['american_odds'])
        market_lines.append(
            f'{i+1}. "{m["matchup"]} — {m["title"]}" '
            f'(${m["payout"]:.2f} payout on $1, odds: {odds_str}, '
            f'sport: {m.get("sport_display", "")}, '
            f'tier: {m["tier"]}, '
            f'implied prob: {m["implied_probability"]*100:.0f}%)'
        )

    prompt = f"""You are the editorial voice of Dollar Bets — a daily sports betting board with a Craigslist/Drudge aesthetic. This is the "Underdogs" board — sports bets only.

You have TWO jobs for each bet:
1. REWRITE THE TITLE — turn raw odds data into a punchy, declarative editorial headline
2. WRITE A QUIP — a short, wry, one-line editorial comment

TITLE REWRITING RULES:
- Frame as a declarative statement: "Lakers upset OKC tonight", not "Will the Lakers beat OKC?"
- Pick the side that makes the best Dollar Bets headline — favourites winning is boring unless the context is interesting
- For spreads: work the number in naturally — "Celtics cover 6.5 against Philly" not "Boston Celtics -6.5"
- For totals: make it vivid — "Rockets-Mavs goes over 220" or "defensive slugfest stays under 195"
- Replace dates with "tonight", "tomorrow", etc
- Keep it punchy: 3-10 words ideal
- Include the team name(s) — this is sports, people need to know who's playing

QUIP RULES:
- 3-12 words. No period at the end. Natural casing
- Name a specific thing: a player, a meme, a cultural reference, a song, a movie. Concrete > abstract
- For green tier (near-locks): breezy, understated — "rent money", "the math checks out"
- For yellow/orange tier (interesting value): sharp observation, pop culture riff
- For red/purple tier (long shots): go big — committed bits, dramatic references, absurdist energy
- Every quip must be specific to THIS bet. If it could apply to 5 different bets, throw it out
- Reference the specific teams, players, or situation when possible — sport-literate quips land harder
- NEVER comment on betting itself or the difficulty of predictions
- NEVER use vague irony. Commit to the bit

TODAY'S PICKS:
{chr(10).join(market_lines)}

Return a JSON array of {len(board)} objects, each with "title" and "quip" keys.
Example: [{{"title": "Jets somehow beat the Chiefs", "quip": "the brussel sprouts of the league finally season themselves"}}]

Respond with ONLY the JSON array."""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
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
        print("[sports] Generating quips via Claude...", file=sys.stderr)
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode()
            result = json.loads(raw)
            text = result["content"][0]["text"].strip()

            # Strip markdown code fence if present
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
                text = text.strip()

            entries = json.loads(text)

            if isinstance(entries, list) and len(entries) == len(board):
                if all(isinstance(e, dict) and e.get("title") and e.get("quip") for e in entries):
                    for i, e in enumerate(entries):
                        board[i]["title"] = e["title"].strip()
                        board[i]["quip"] = e["quip"].strip()
                    print(f"[sports] Generated {len(board)} titles + quips", file=sys.stderr)
                    return board

            print(f"[sports] WARN: Claude output didn't match expected format, keeping fallbacks", file=sys.stderr)
            return board

    except Exception as e:
        print(f"[sports] Claude quip generation failed: {e}", file=sys.stderr)
        return board


# ── Main ─────────────────────────────────────────────────────

def main():
    no_ai = "--no-ai" in sys.argv
    use_sample = "--sample" in sys.argv

    if use_sample:
        print("[sports] Sample mode not yet implemented — use live API", file=sys.stderr)
        return

    if not ODDS_API_KEY:
        print("[sports] ERROR: Set ODDS_API_KEY environment variable", file=sys.stderr)
        print("[sports] Get a free key at https://the-odds-api.com/", file=sys.stderr)
        sys.exit(1)

    # Step 1: Detect active sports
    print("[sports] Detecting active sports...", file=sys.stderr)
    sports_data = odds_api_get("/sports", {"all": "false"})
    if not sports_data:
        print("[sports] ERROR: Couldn't fetch sports list", file=sys.stderr)
        sys.exit(1)

    active_sports = [s["key"] for s in sports_data if s.get("active") and s["key"] in SPORTS]
    print(f"[sports] Active: {active_sports}", file=sys.stderr)

    if not active_sports:
        print("[sports] No active sports found in our list", file=sys.stderr)
        sys.exit(1)

    # Step 2: Fetch standard odds for each sport (h2h, spreads, totals)
    all_candidates = []
    all_events_by_sport = {}  # track for prop fetching
    for sport in active_sports:
        print(f"\n[sports] Scanning {SPORT_DISPLAY.get(sport, sport)}...", file=sys.stderr)
        events = fetch_sport_odds(sport)
        if not events:
            print(f"[sports] No events for {sport}", file=sys.stderr)
            continue
        print(f"[sports] {len(events)} events found", file=sys.stderr)

        all_events_by_sport[sport] = events
        candidates = extract_markets(events, sport)
        print(f"[sports] {len(candidates)} market candidates extracted", file=sys.stderr)
        all_candidates.extend(candidates)
        time.sleep(0.3)

    print(f"\n[sports] Standard candidates: {len(all_candidates)}", file=sys.stderr)

    # Step 2b: Check if we need props/alternates for higher tiers
    # Count how many orange/red/purple candidates we have
    high_tier_count = sum(1 for c in all_candidates if payout_tier(c["payout_raw"]) in ("orange", "red", "purple"))
    print(f"[sports] High-tier candidates (orange+): {high_tier_count}", file=sys.stderr)

    # Always fetch props — standard markets almost never produce red/purple tiers
    if True:  # was: high_tier_count < 4
        # Fetch props and alternate lines for top events to fill higher tiers
        # Pick up to 5 events from the most popular sports (save API credits)
        prop_sports = [s for s in ["basketball_nba", "baseball_mlb", "icehockey_nhl",
                                    "americanfootball_nfl"] if s in all_events_by_sport]
        prop_events_to_check = []
        for sport in prop_sports:
            events = all_events_by_sport[sport]
            # Prefer events starting soonest
            for ev in sorted(events, key=lambda e: e.get("commence_time", ""))[:3]:
                prop_events_to_check.append((sport, ev))
            if len(prop_events_to_check) >= 5:
                break

        print(f"\n[sports] Fetching props for {len(prop_events_to_check)} events...", file=sys.stderr)
        for sport, event in prop_events_to_check:
            event_id = event.get("id", "")
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            print(f"[sports]   Props: {away} @ {home}", file=sys.stderr)

            prop_data = fetch_event_props(sport, event_id)
            if prop_data:
                # The event-level endpoint returns a single event dict, not a list
                prop_events = [prop_data] if isinstance(prop_data, dict) else prop_data
                prop_candidates = extract_markets(prop_events, sport)
                # Only keep the interesting ones (yellow+ payout)
                prop_high = [c for c in prop_candidates if c["payout_raw"] >= 3.0]
                print(f"[sports]   → {len(prop_high)} high-payout props found", file=sys.stderr)
                all_candidates.extend(prop_high)
            time.sleep(0.3)

    print(f"\n[sports] Total candidates (with props): {len(all_candidates)}", file=sys.stderr)

    if not all_candidates:
        print("[sports] No candidates found — no board to build", file=sys.stderr)
        sys.exit(1)

    # Step 3: Build the board
    board_raw = build_sports_board(all_candidates)
    print(f"[sports] Board assembled: {len(board_raw)} picks", file=sys.stderr)

    # Step 4: Format entries
    board = [format_board_entry(c) for c in board_raw]

    # Step 5: AI quip generation
    if not no_ai:
        board = generate_quips_ai(board)
    else:
        print("[sports] Skipping AI quips (--no-ai flag)", file=sys.stderr)

    # Step 6: Clean up internal fields
    for m in board:
        m.pop("_source", None)
        m.pop("_has_betslip", None)

    # Step 7: Log summary
    tier_summary = {}
    sport_summary = {}
    deep_link_count = 0
    for m in board:
        tier_summary[m["tier"]] = tier_summary.get(m["tier"], 0) + 1
        sd = m.get("sport_display", "?")
        sport_summary[sd] = sport_summary.get(sd, 0) + 1
        if m.get("has_deep_link"):
            deep_link_count += 1

    print(f"\n[sports] ═══ BOARD SUMMARY ═══", file=sys.stderr)
    print(f"[sports] Tiers: {tier_summary}", file=sys.stderr)
    print(f"[sports] Sports: {sport_summary}", file=sys.stderr)
    print(f"[sports] Deep links: {deep_link_count}/{len(board)}", file=sys.stderr)
    print(f"[sports] ═══════════════════════", file=sys.stderr)

    for i, m in enumerate(board):
        link_icon = "🔗" if m.get("has_deep_link") else "📎"
        print(f"[sports] {i+1}. [{m['tier']}] {m['title']}", file=sys.stderr)
        print(f"         ${m['payout']:.2f} | {m['matchup']} | {m['sport_display']} | {link_icon} {m['platform_display']}", file=sys.stderr)
        print(f"         \"{m['quip']}\"", file=sys.stderr)

    # Output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "board_type": "sports",
        "board_name": "underdogs",
        "market_count": len(board),
        "source": "odds_api",
        "tier_mix": tier_summary,
        "sport_mix": sport_summary,
        "board": board,
    }

    json.dump(output, sys.stdout, indent=2)
    print(f"\n[sports] Done — {len(board)} picks", file=sys.stderr)


if __name__ == "__main__":
    main()
