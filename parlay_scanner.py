#!/usr/bin/env python3
"""
Dollar Bets — Parlay Scanner (v1: "Another Day at the Office")

Pulls sports odds from The Odds API, builds parlay cards from
near-certain outcomes, calculates combined $1 payouts, and
outputs JSON compatible with the existing board format.

Deep links to sportsbook bet slips where available.

Usage:
    ODDS_API_KEY=xxx python parlay_scanner.py [--sport basketball_nba] [--dry-run]
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from itertools import combinations

# ── Config ───────────────────────────────────────────────────

ODDS_API = "https://api.the-odds-api.com/v4"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# Books to pull odds from (free tier available)
# Priority order: books most likely to have deep links first
TARGET_BOOKS = [
    "fanduel",
    "betmgm",
    "betrivers",
    "draftkings",   # paid tier only — will gracefully skip if unavailable
    "bovada",
    "betonlineag",
]

# Sports to scan (The Odds API sport keys)
# Focus on major US sports for parlay content
SPORTS = [
    "basketball_nba",
    "baseball_mlb",
    "icehockey_nhl",
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "basketball_ncaab",
    "mma_mixed_martial_arts",
    "soccer_usa_mls",
]

# Markets to pull for parlay legs
MARKETS = ["h2h", "spreads", "totals", "player_props"]

# Parlay configuration
MIN_LEGS = 2
MAX_LEGS = 4
# Implied probability threshold — only use legs where one side is very likely
# e.g. 0.75 means we only pick outcomes with >= 75% implied probability
HEAVY_FAVORITE_THRESHOLD = 0.55  # lowered to include moderate favorites for spicier combos
# Target combined payout range for parlays ($1 → $X)
MIN_COMBINED_PAYOUT = 1.50  # at least +50% return
MAX_COMBINED_PAYOUT = 25.00  # allow spicy combos for the combo meal

# Quips for "another day at the office" parlays
OFFICE_QUIPS = [
    "another day at the office",
    "rent money",
    "the sun also rises",
    "water is wet",
    "as sure as gravity",
    "clock in, cash out",
    "business as usual",
    "like taking candy from a vending machine",
    "the boring middle",
    "steady hands",
    "autopilot engaged",
    "just showing up",
    "the safe bet",
    "tuesday energy",
    "paint drying, but profitable",
    "checking all the boxes",
    "routine maintenance",
    "the fundamentals",
    "no surprises here",
    "bread and butter",
]


# ── API helpers ──────────────────────────────────────────────

def odds_api_get(path, params=None):
    """Make a GET request to The Odds API."""
    if not ODDS_API_KEY:
        print("[parlay] ERROR: ODDS_API_KEY not set", file=sys.stderr)
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
                # Track remaining quota from headers
                remaining = resp.headers.get("x-requests-remaining", "?")
                used = resp.headers.get("x-requests-used", "?")
                print(f"[parlay] API quota: {used} used, {remaining} remaining", file=sys.stderr)
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[parlay] Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 401:
                print("[parlay] ERROR: Invalid API key", file=sys.stderr)
                return None
            if e.code == 422:
                print(f"[parlay] WARN: Invalid params ({url})", file=sys.stderr)
                return None
            print(f"[parlay] API error {e.code}: {e} ({url})", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            print(f"[parlay] Network error: {e}", file=sys.stderr)
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
    """$1 bet payout at given decimal odds."""
    return round(decimal_odds, 2)


def parlay_decimal_odds(legs):
    """Multiply decimal odds of each leg for combined parlay odds."""
    combined = 1.0
    for leg in legs:
        combined *= leg["decimal_odds"]
    return combined


# ── Fetch & parse ────────────────────────────────────────────

def fetch_odds_for_sport(sport_key, markets="h2h,spreads,totals"):
    """
    Fetch odds for a sport with deep links included.
    Returns list of events with bookmaker odds.
    """
    params = {
        "regions": "us,us2",
        "markets": markets,
        "oddsFormat": "american",
        "includeLinks": "true",
        "includeSids": "true",
        "bookmakers": ",".join(TARGET_BOOKS),
    }
    data = odds_api_get(f"/sports/{sport_key}/odds", params)
    if not data:
        return []
    return data


def extract_legs_from_event(event, sport_key):
    """
    Extract potential parlay legs from an event.
    Only picks heavy favorites (high implied probability).
    Returns list of leg dicts.
    """
    legs = []
    event_id = event.get("id", "")
    home = event.get("home_team", "")
    away = event.get("away_team", "")
    commence = event.get("commence_time", "")
    event_link = ""

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
                outcome_sid = outcome.get("sid", "")

                if price == 0:
                    continue

                implied_prob = american_to_implied_prob(price)
                decimal_odds = american_to_decimal(price)

                # Only take heavy favorites
                if implied_prob < HEAVY_FAVORITE_THRESHOLD:
                    continue

                # Skip outcomes that need a point but didn't ship one in the
                # bookmaker payload. Some books return spreads/totals without
                # a locked line, and `point > 0` against None used to raise
                # TypeError that killed the whole scan (no enclosing try/except).
                if market_key in ("spreads", "totals") and point is None:
                    continue

                # Build human-readable description
                if market_key == "h2h":
                    desc = f"{name} wins"
                elif market_key == "spreads":
                    spread_str = f"+{point}" if point > 0 else str(point)
                    desc = f"{name} {spread_str}"
                elif market_key == "totals":
                    direction = "Over" if name == "Over" else "Under"
                    desc = f"{direction} {point}"
                else:
                    desc = f"{name}"

                leg = {
                    "event_id": event_id,
                    "sport": sport_key,
                    "home_team": home,
                    "away_team": away,
                    "commence_time": commence,
                    "bookmaker": book_key,
                    "bookmaker_title": book_title,
                    "market": market_key,
                    "outcome_name": name,
                    "description": desc,
                    "matchup": f"{away} @ {home}",
                    "american_odds": price,
                    "decimal_odds": decimal_odds,
                    "implied_probability": round(implied_prob, 3),
                    "deep_link": outcome_link or book_link or "",
                    "sid": outcome_sid,
                    "point": point,
                }
                legs.append(leg)

    return legs


# ── Parlay builder ───────────────────────────────────────────

def build_parlays(all_legs, max_parlays=10):
    """
    Build "another day at the office" parlays from available legs.
    Rules:
    - 2-4 legs per parlay
    - All legs must be from the same bookmaker (for deep linking)
    - No two legs from the same event
    - Combined payout in target range
    - Prefer variety in sport/market type
    """
    parlays = []

    # Group legs by bookmaker
    by_book = {}
    for leg in all_legs:
        book = leg["bookmaker"]
        if book not in by_book:
            by_book[book] = []
        by_book[book].append(leg)

    # For each bookmaker, try to build parlays
    for book_key, book_legs in by_book.items():
        # Deduplicate: keep best odds per event+market+outcome
        seen = {}
        for leg in book_legs:
            key = (leg["event_id"], leg["market"], leg["outcome_name"], leg.get("point"))
            if key not in seen or leg["decimal_odds"] > seen[key]["decimal_odds"]:
                seen[key] = leg
        unique_legs = list(seen.values())

        if len(unique_legs) < MIN_LEGS:
            continue

        # Try combinations of 2, 3, 4 legs
        for num_legs in range(MIN_LEGS, min(MAX_LEGS + 1, len(unique_legs) + 1)):
            for combo in combinations(unique_legs, num_legs):
                # Check: no two legs from same event
                event_ids = [leg["event_id"] for leg in combo]
                if len(set(event_ids)) < len(event_ids):
                    continue

                # Calculate combined odds
                combined_decimal = parlay_decimal_odds(combo)
                payout = decimal_to_payout(combined_decimal)

                # Check payout range
                if payout < MIN_COMBINED_PAYOUT or payout > MAX_COMBINED_PAYOUT:
                    continue

                # Calculate combined implied probability
                combined_prob = 1.0
                for leg in combo:
                    combined_prob *= leg["implied_probability"]

                # Build the deep link
                # For single-book parlays, we link each leg individually
                # (true parlay deep links require sportsbook-specific URL construction)
                leg_links = [leg["deep_link"] for leg in combo if leg["deep_link"]]

                parlay = {
                    "legs": list(combo),
                    "bookmaker": book_key,
                    "bookmaker_title": combo[0]["bookmaker_title"],
                    "num_legs": num_legs,
                    "combined_decimal_odds": round(combined_decimal, 3),
                    "payout_per_dollar": payout,
                    "combined_implied_probability": round(combined_prob, 3),
                    "leg_deep_links": leg_links,
                    "has_deep_links": len(leg_links) == len(combo),
                }
                parlays.append(parlay)

    # Sort by: has deep links (prefer), then by payout (prefer mid-range ~2x)
    parlays.sort(key=lambda p: (
        -int(p["has_deep_links"]),
        abs(p["payout_per_dollar"] - 2.0),  # prefer ~2x payouts
    ))

    return parlays[:max_parlays]


# ── Output formatting ────────────────────────────────────────

def format_parlay_title(parlay):
    """Generate a human-readable title for a parlay card."""
    legs = parlay["legs"]
    if len(legs) == 2:
        return f"{legs[0]['description']} + {legs[1]['description']}"
    else:
        parts = [leg["description"] for leg in legs[:-1]]
        return ", ".join(parts) + f" + {legs[-1]['description']}"


def format_parlay_for_board(parlay, index=0):
    """
    Convert a parlay into Dollar Bets board format.
    Compatible with the existing generate.py pipeline.
    """
    import hashlib

    legs = parlay["legs"]
    title = format_parlay_title(parlay)
    payout = parlay["payout_per_dollar"]

    # Generate a stable ticker-like ID
    leg_ids = "-".join(sorted([leg["event_id"][:8] for leg in legs]))
    ticker = f"PARLAY-{hashlib.md5(leg_ids.encode()).hexdigest()[:8].upper()}"

    # Tier classification (matches sports_scanner.py payout_tier)
    if payout < 3:
        tier = "green"
    elif payout < 7:
        tier = "yellow"
    elif payout < 15:
        tier = "orange"
    elif payout < 50:
        tier = "red"
    else:
        tier = "purple"

    # Pick a quip
    quip_index = hash(ticker) % len(OFFICE_QUIPS)
    quip = OFFICE_QUIPS[quip_index]

    # Build matchup descriptions
    matchups = []
    for leg in legs:
        matchups.append({
            "matchup": leg["matchup"],
            "pick": leg["description"],
            "odds": leg["american_odds"],
            "implied_prob": f"{leg['implied_probability'] * 100:.0f}%",
            "sport": leg["sport"],
            "deep_link": leg["deep_link"],
            "commence_time": leg["commence_time"],
        })

    # Primary deep link — first leg's link or bookmaker homepage
    primary_link = ""
    for leg in legs:
        if leg["deep_link"]:
            primary_link = leg["deep_link"]
            break

    # Build matchup string from all legs
    matchup_str = " + ".join(leg["matchup"] for leg in legs[:2])
    if len(legs) > 2:
        matchup_str += f" +{len(legs) - 2} more"

    # Sport display — use first leg's sport or "Parlay"
    sport_key = legs[0]["sport"] if legs else ""
    sport_displays = {
        "basketball_nba": "NBA", "baseball_mlb": "MLB", "icehockey_nhl": "NHL",
        "americanfootball_nfl": "NFL", "americanfootball_ncaaf": "NCAAF",
        "basketball_ncaab": "NCAAB", "mma_mixed_martial_arts": "MMA",
        "soccer_usa_mls": "MLS",
    }
    # Check if multi-sport parlay
    unique_sports = set(leg["sport"] for leg in legs)
    if len(unique_sports) > 1:
        sport_display = "Multi"
    else:
        sport_display = sport_displays.get(sport_key, "Parlay")

    return {
        "ticker": ticker,
        "title": title,
        "payout": payout,
        "tier": tier,
        "quip": quip,
        "yes_price": f"{parlay['combined_implied_probability']:.2f}",
        "category": "sports-parlay",
        "platform": parlay["bookmaker"],
        "platform_display": parlay["bookmaker_title"],
        "url": primary_link,
        "sport": sport_key,
        "sport_display": sport_display,
        "matchup": matchup_str,
        "market_type": f"{parlay['num_legs']}-leg parlay",
        "american_odds": (
            round((payout - 1) * 100) if payout >= 2
            else round(-100 / (payout - 1)) if payout > 1
            else 0  # payout==1 edge case (zero edge); -100/0 would crash
        ),
        "implied_probability": parlay["combined_implied_probability"],
        "has_deep_link": parlay["has_deep_links"],
        "type": "parlay",
        "num_legs": parlay["num_legs"],
        "legs": matchups,
        "close_time": min(leg["commence_time"] for leg in legs),
    }


# ── Main ─────────────────────────────────────────────────────

def scan_parlays(sports=None, dry_run=False):
    """
    Main entry point: scan for parlay opportunities.
    Returns list of parlay card dicts in board format.
    """
    if not ODDS_API_KEY and not dry_run:
        print("[parlay] ERROR: Set ODDS_API_KEY environment variable", file=sys.stderr)
        print("[parlay] Get a free key at https://the-odds-api.com/", file=sys.stderr)
        return []

    if sports is None:
        # Auto-detect in-season sports
        sports_data = odds_api_get("/sports", {"all": "false"})
        if sports_data:
            sports = [s["key"] for s in sports_data
                      if s.get("active") and s["key"] in SPORTS]
            print(f"[parlay] Active sports: {sports}", file=sys.stderr)
        else:
            sports = ["basketball_nba", "baseball_mlb", "icehockey_nhl"]

    all_legs = []

    for sport in sports:
        print(f"\n[parlay] Scanning {sport}...", file=sys.stderr)
        events = fetch_odds_for_sport(sport, markets="h2h,spreads,totals")
        print(f"[parlay] Found {len(events)} events for {sport}", file=sys.stderr)

        # Wrap per-event extraction so one malformed event from one bookmaker
        # (missing point, weird market shape, new API field) skips that event
        # rather than killing the whole scan and failing the cron run.
        skipped = 0
        for event in events:
            try:
                legs = extract_legs_from_event(event, sport)
                all_legs.extend(legs)
            except Exception as e:
                skipped += 1
                print(f"[parlay] WARN: skipping event {event.get('id', '?')} ({sport}): "
                      f"{type(e).__name__}: {e}", file=sys.stderr)
                continue
        if skipped:
            print(f"[parlay] WARN: {skipped} {sport} events skipped due to data errors", file=sys.stderr)

        # Be nice to the API
        time.sleep(0.5)

    print(f"\n[parlay] Total qualifying legs: {len(all_legs)}", file=sys.stderr)

    # Build parlays — wrap so a malformed leg can't kill the whole scan.
    try:
        parlays = build_parlays(all_legs, max_parlays=10)
    except Exception as e:
        print(f"[parlay] ERROR: build_parlays crashed: {type(e).__name__}: {e}", file=sys.stderr)
        parlays = []
    print(f"[parlay] Built {len(parlays)} parlays", file=sys.stderr)

    # Format for board — wrap the entire per-parlay block (format + debug print)
    # in one try/except so any failure on a single parlay drops only that one,
    # not the whole scan. Past footguns: divide-by-zero in american_odds when
    # payout == 1.0, key-shape drift between intermediate parlay dict and card
    # dict (e.g. has_deep_links vs has_deep_link).
    cards = []
    for i, parlay in enumerate(parlays):
        try:
            card = format_parlay_for_board(parlay, i)
            cards.append(card)
            print(f"\n[parlay] Card {i+1}: {card['title']}", file=sys.stderr)
            print(f"         Payout: $1 → {card['payout']} ({card['tier']})", file=sys.stderr)
            print(f"         Quip: \"{card['quip']}\"", file=sys.stderr)
            print(f"         Book: {card['platform_display']}", file=sys.stderr)
            print(f"         Deep links: {'YES' if card.get('has_deep_link') else 'NO'}", file=sys.stderr)
            for leg in card.get("legs", []):
                print(f"         → {leg.get('pick','?')} ({leg.get('matchup','?')}) "
                      f"[{leg.get('odds','?')}] {leg.get('implied_prob','?')}", file=sys.stderr)
        except Exception as e:
            print(f"[parlay] WARN: dropping parlay {i} ({parlay.get('bookmaker','?')}, "
                  f"{parlay.get('num_legs','?')} legs, payout={parlay.get('payout_per_dollar','?')}): "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
            # If the card was already appended before the crash, remove it
            if cards and cards[-1].get("ticker", "").startswith("PARLAY-") and \
               len(cards) > i:  # defensive: only pop if we just added
                cards.pop()
            continue

    return cards


def main():
    import argparse
    global MIN_COMBINED_PAYOUT, MAX_COMBINED_PAYOUT, HEAVY_FAVORITE_THRESHOLD

    parser = argparse.ArgumentParser(description="Dollar Bets Parlay Scanner")
    parser.add_argument("--sport", help="Specific sport key to scan")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scanned")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--min-payout", type=float, default=MIN_COMBINED_PAYOUT)
    parser.add_argument("--max-payout", type=float, default=MAX_COMBINED_PAYOUT)
    parser.add_argument("--threshold", type=float, default=HEAVY_FAVORITE_THRESHOLD,
                        help="Min implied probability for each leg (0.0-1.0)")
    args = parser.parse_args()

    MIN_COMBINED_PAYOUT = args.min_payout
    MAX_COMBINED_PAYOUT = args.max_payout
    HEAVY_FAVORITE_THRESHOLD = args.threshold

    sports = [args.sport] if args.sport else None

    if args.dry_run:
        print("[parlay] DRY RUN — would scan:", file=sys.stderr)
        if sports:
            for s in sports:
                print(f"  - {s}", file=sys.stderr)
        else:
            print("  - all active US sports", file=sys.stderr)
        print(f"  - favorite threshold: {HEAVY_FAVORITE_THRESHOLD}", file=sys.stderr)
        print(f"  - payout range: ${MIN_COMBINED_PAYOUT:.2f} - ${MAX_COMBINED_PAYOUT:.2f}", file=sys.stderr)
        print(f"  - books: {', '.join(TARGET_BOOKS)}", file=sys.stderr)
        return

    cards = scan_parlays(sports=sports)

    # Output — matches sports_scanner.py board format
    tier_summary = {}
    sport_summary = {}
    for c in cards:
        tier_summary[c["tier"]] = tier_summary.get(c["tier"], 0) + 1
        sd = c.get("sport_display", "?")
        sport_summary[sd] = sport_summary.get(sd, 0) + 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "board_type": "combo-meal",
        "board_name": "the combo meal",
        "market_count": len(cards),
        "source": "odds_api",
        "tier_mix": tier_summary,
        "sport_mix": sport_summary,
        "board": cards,
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n[parlay] Wrote {len(cards)} cards to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
