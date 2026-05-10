#!/usr/bin/env python3
"""
Dollar Bets — Market Link Redirect Handler (/go/ endpoint)

Routes market links through eligible partners based on user location.
Example: /go/KXGROK → resolves to best Kalshi/Polymarket/etc URL → 302 redirect

Vercel Python serverless function using BaseHTTPRequestHandler.
"""

import json
import os
import re
import glob
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent directory to path so we can import link_resolver
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from link_resolver import resolve_market_destination


POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"


# ── Sportsbook geo-resolution ─────────────────────────────────
# BetMGM and BetRivers use {state} placeholders in deep link URLs.
# Vercel provides the US state via x-vercel-ip-region header.

BETMGM_STATES = {
    "NJ": "nj", "PA": "pa", "MI": "mi", "WV": "wv", "CO": "co",
    "IN": "in", "IA": "ia", "VA": "va", "TN": "tn", "AZ": "az",
    "LA": "la", "WY": "wy", "OH": "oh", "MD": "md", "MA": "ma",
    "KY": "ky", "KS": "ks", "NC": "nc", "DC": "dc",
}

BETRIVERS_STATES = {
    "PA": "pa", "MI": "mi", "WV": "wv", "CO": "co", "IN": "in",
    "IA": "ia", "VA": "va", "IL": "il", "LA": "la", "OH": "oh",
    "MD": "md", "AZ": "az", "NJ": "nj", "NY": "ny", "CT": "ct",
}

# FanDuel uses state-specific subdomains. Their parent domain shows
# /select-region for users without a state cookie. Rewrite URLs at
# redirect time using x-vercel-ip-region.
FANDUEL_STATES = {
    "AZ": "az", "CO": "co", "CT": "ct", "DC": "dc", "IA": "ia",
    "IL": "il", "IN": "in", "KS": "ks", "KY": "ky", "LA": "la",
    "MA": "ma", "MD": "md", "MI": "mi", "NC": "nc", "NJ": "nj",
    "NY": "ny", "OH": "oh", "PA": "pa", "TN": "tn", "VT": "vt",
    "VA": "va", "WV": "wv", "WY": "wy",
}

# DraftKings uses a single domain with IP/cookie-based geo (no state
# subdomains). We can't rewrite the URL — only gate by supported state.
DRAFTKINGS_STATES = {
    "AZ", "CO", "CT", "DC", "IA", "IL", "IN", "KS", "KY", "LA",
    "MA", "MD", "MI", "MS", "NH", "NJ", "NY", "OH", "OR", "PA",
    "TN", "VA", "VT", "WV", "WY", "ND",
}

# Sport board files we search for SB- tickers. Each entry maps a board
# file prefix (filename pattern in data/boards/) to the URL slug used as
# ?from= and as the fallback page. The URL slug must match the actual
# URL path the user-facing page lives at — see SPORTS_BOARD_CONFIGS in
# generate.py.
SPORT_BOARD_PREFIXES = [
    ("sports", "the-lineup"),     # file: sports-*.json  → page: /the-lineup/
    ("underdogs", "underdogs"),   # file: underdogs-*.json → page: /underdogs/
    ("ocho", "the-ocho"),         # file: ocho-*.json    → page: /the-ocho/
    ("chalk", "chalk"),           # file: chalk-*.json   → page: /chalk/
    ("combo", "combo-meal"),      # file: combo-*.json   → page: /combo-meal/
]

# Map ?from= slug → URL path used for fallback redirects.
# Keys must match the url_slug values emitted by generate.py.
FROM_SLUG_TO_PATH = {
    "the-lineup": "/the-lineup/",
    "underdogs": "/underdogs/",
    "the-ocho": "/the-ocho/",
    "chalk": "/chalk/",
    "combo-meal": "/combo-meal/",
}

SPORTSBOOK_DISPLAY_NAMES = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "betrivers": "BetRivers",
    "bovada": "Bovada",
    "betonlineag": "BetOnline",
}


def resolve_sportsbook_state(url, region_code, book_slug):
    """Replace {state} placeholder in sportsbook URLs with the user's state.

    Returns the resolved URL, or None if the user is in an unsupported state.
    """
    if "{state}" not in url:
        return url

    if not region_code:
        return None

    state = region_code.upper()

    if "betmgm" in book_slug:
        state_slug = BETMGM_STATES.get(state)
    elif "betrivers" in book_slug or "sugarhouse" in book_slug:
        state_slug = BETRIVERS_STATES.get(state)
    else:
        state_slug = state.lower()

    if not state_slug:
        return None

    return url.replace("{state}", state_slug)


def rewrite_fanduel_url(url, region_code):
    """Rewrite parent-domain FanDuel URLs to a state-specific subdomain.

    FanDuel's parent domain (sportsbook.fanduel.com) renders /select-region
    when the user has no state cookie. State subdomains like
    nj.sportsbook.fanduel.com bypass that page.

    Returns the rewritten URL, or None if the user's state is unsupported.
    Returns the URL unchanged if it already has a state subdomain or isn't
    a FanDuel URL.
    """
    if not url or "fanduel.com" not in url:
        return url

    # Already has a two-letter state subdomain — leave alone
    if re.search(r"https?://[a-z]{2}\.sportsbook\.fanduel\.com", url):
        return url

    if "sportsbook.fanduel.com" not in url:
        return url

    if not region_code:
        return None

    state_slug = FANDUEL_STATES.get(region_code.upper())
    if not state_slug:
        return None

    return url.replace(
        "sportsbook.fanduel.com",
        f"{state_slug}.sportsbook.fanduel.com",
        1,
    )


def is_draftkings_state_supported(region_code):
    """Return True if the user is in a DraftKings-supported state."""
    if not region_code:
        return False
    return region_code.upper() in DRAFTKINGS_STATES


def find_sports_market(market_id):
    """Search every sport board file for an SB- ticker.

    Returns (market_dict, source_slug) where source_slug is the URL slug
    of the originating board (used for fallback redirects). Returns
    (None, None) if the ticker isn't found in any sport board.
    """
    site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    boards_dir = os.path.join(site_dir, "data", "boards")

    for prefix, slug in SPORT_BOARD_PREFIXES:
        pattern = os.path.join(boards_dir, f"{prefix}-*.json")
        files = sorted(glob.glob(pattern), reverse=True)
        if not files:
            continue
        try:
            with open(files[0]) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for m in data.get("board", []):
            if m.get("ticker") == market_id:
                return m, slug

    return None, None


def fallback_path(from_slug):
    """Resolve the ?from= slug to a URL path. Defaults to /the-lineup/."""
    if from_slug and from_slug in FROM_SLUG_TO_PATH:
        return FROM_SLUG_TO_PATH[from_slug]
    return "/the-lineup/"


def load_latest_sports_board():
    """[Deprecated] Load the most recent lineup board only.

    Kept for any external callers. Use find_sports_market() instead — it
    searches across all sport board files (sports/underdogs/ocho/chalk/combo).
    """
    site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    boards_dir = os.path.join(site_dir, "data", "boards")

    pattern = os.path.join(boards_dir, "sports-*.json")
    files = sorted(glob.glob(pattern), reverse=True)

    if not files:
        return None

    try:
        with open(files[0]) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def sportsbook_unavailable_html(market_title, book_display, user_state, back_path="/the-lineup/"):
    """Unavailable page when a sportsbook isn't available in the user's state.

    `back_path` is the URL the back-link returns to — typically the originating
    board (/underdogs/, /ocho/, /chalk/, /combo-meal/, /the-lineup/) so users
    aren't dumped on a board they didn't come from.
    """
    state_str = user_state.upper() if user_state else "your state"
    # Derive a label from the path for the body link copy
    path_label = back_path.strip("/").replace("-", " ") or "lineup"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>not available — dollar bets</title>
<style>
  body {{
    background: #fdf6ee; color: #2d2319; font-family: 'Courier New', monospace;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; margin: 0; padding: 16px; box-sizing: border-box;
  }}
  .box {{
    max-width: 480px; width: 100%; border: 1px solid #e8cdb5; padding: 24px;
    background: #faf7f3;
  }}
  h1 {{ font-size: 16px; margin: 0 0 16px 0; text-transform: lowercase; color: #2d2319; }}
  p {{ font-size: 13px; line-height: 1.6; margin: 0 0 12px 0; color: #5a4e2f; }}
  .warn {{
    background: #fef9e7; border: 1px solid #d4c479; color: #5a4e2f;
    padding: 10px 12px; margin: 16px 0; font-size: 12px;
  }}
  a.back {{
    display: block; text-align: center; margin: 16px auto 0; padding: 12px 24px;
    border: 2px solid #e8642c; color: #e8642c; text-decoration: none;
    font-family: 'Courier New', monospace; font-size: 15px; font-weight: 700;
    max-width: 280px;
  }}
  a.back:hover {{ background: #e8642c; color: #fdf6ee; }}
  .fine {{ font-size: 11px; color: #a08b77; margin-top: 20px; }}
</style>
</head>
<body>
<div class="box">
  <h1>sportsbook not available in your state</h1>
  <p><strong>{book_display}</strong> is not available in <strong>{state_str}</strong> for the wager "{market_title}".</p>
  <div class="warn">
    <p>sportsbook availability varies by state. dollar bets does not control which states are supported.</p>
  </div>
  <p>check the <a href="{back_path}" style="color:#d97c3c">{path_label} board</a> for other wagers, or other boards for different sportsbooks.</p>
  <a class="back" href="{back_path}">back to {path_label}</a>
  <p class="fine">dollar bets is an editorial site. we do not operate sportsbooks or verify user eligibility.</p>
</div>
</body>
</html>"""


COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "AU": "Australia",
    "CA": "Canada", "DE": "Germany", "FR": "France", "IT": "Italy",
    "ES": "Spain", "NL": "Netherlands", "BE": "Belgium", "CH": "Switzerland",
    "AT": "Austria", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
    "FI": "Finland", "IE": "Ireland", "PT": "Portugal", "PL": "Poland",
    "CZ": "Czech Republic", "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria",
    "HR": "Croatia", "SK": "Slovakia", "SI": "Slovenia", "LT": "Lithuania",
    "LV": "Latvia", "EE": "Estonia", "GR": "Greece", "CY": "Cyprus",
    "MT": "Malta", "LU": "Luxembourg",
    "CN": "China", "HK": "Hong Kong", "JP": "Japan", "KR": "South Korea",
    "IN": "India", "SG": "Singapore", "TW": "Taiwan", "TH": "Thailand",
    "MY": "Malaysia", "PH": "Philippines", "ID": "Indonesia", "VN": "Vietnam",
    "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "CO": "Colombia",
    "CL": "Chile", "PE": "Peru",
    "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt",
    "AE": "UAE", "SA": "Saudi Arabia", "IL": "Israel", "TR": "Turkey",
    "RU": "Russia", "UA": "Ukraine", "BY": "Belarus",
    "IR": "Iran", "KP": "North Korea", "CU": "Cuba", "SY": "Syria",
    "VE": "Venezuela", "MM": "Myanmar",
    "NZ": "New Zealand",
}


def _country_name(code):
    """Convert ISO country code to readable name."""
    return COUNTRY_NAMES.get(code.upper(), code.upper()) if code else "your region"


def _describe_availability(partner_config):
    """Build human-readable availability description from partner config."""
    allowed = partner_config.get("allowed_countries", "all")
    blocked = partner_config.get("blocked_countries", [])

    if isinstance(allowed, list) and len(allowed) <= 10:
        # Allowlist model (e.g., Kalshi = US only)
        names = [_country_name(c) for c in allowed]
        return ", ".join(names)

    if allowed == "all" and blocked:
        # Blocklist model — too many allowed countries to list, describe as "most countries"
        blocked_names = [_country_name(c) for c in blocked]
        suffix = ""
        return f"most countries except {', '.join(blocked_names)}{suffix}"

    return "varies by jurisdiction"


def unavailable_html(market_id, platform_display, user_country, partner_config):
    """Generate a geo-specific unavailable page."""
    user_location = _country_name(user_country)

    # Build blocked region description
    blocked = partner_config.get("blocked_countries", [])
    allowed = partner_config.get("allowed_countries", "all")

    if isinstance(allowed, list):
        # Allowlist model — user isn't on the list
        reason_html = f"<strong>{platform_display}</strong> is only available in: <strong>{_describe_availability(partner_config)}</strong>."
    elif user_country and user_country.upper() in blocked:
        reason_html = f"<strong>{platform_display}</strong> is not available in <strong>{user_location}</strong>."
    else:
        reason_html = f"<strong>{platform_display}</strong> is not available in your region."

    available_html = _describe_availability(partner_config)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>not available — dollar bets</title>
<style>
  body {{
    background: #fdf6ee; color: #2d2319; font-family: 'Courier New', monospace;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; margin: 0; padding: 16px; box-sizing: border-box;
  }}
  .box {{
    max-width: 480px; width: 100%; border: 1px solid #e8cdb5; padding: 24px;
    background: #faf7f3;
  }}
  h1 {{ font-size: 16px; margin: 0 0 16px 0; text-transform: lowercase; color: #2d2319; }}
  p {{ font-size: 13px; line-height: 1.6; margin: 0 0 12px 0; color: #5a4e2f; }}
  .warn {{
    background: #fef9e7; border: 1px solid #d4c479; color: #5a4e2f;
    padding: 10px 12px; margin: 16px 0; font-size: 12px;
  }}
  .available {{
    font-size: 12px; color: #6b5744; margin: 12px 0;
    padding: 8px 12px; border-left: 3px solid #e8cdb5;
  }}
  a.back {{
    display: block; text-align: center; margin: 16px auto 0; padding: 12px 24px;
    border: 2px solid #e8642c; color: #e8642c; text-decoration: none;
    font-family: 'Courier New', monospace; font-size: 15px; font-weight: 700;
    max-width: 280px;
  }}
  a.back:hover {{ background: #e8642c; color: #fdf6ee; }}
  .fine {{ font-size: 11px; color: #a08b77; margin-top: 20px; }}
</style>
</head>
<body>
<div class="box">
  <h1>market not available in your region</h1>
  <p>you appear to be located in <strong>{user_location}</strong>. {reason_html}</p>
  <div class="warn">
    <p>dollar bets does not control platform availability. this restriction is set by {platform_display}, not by us.</p>
  </div>
  <div class="available">
    <strong>{platform_display}</strong> is available in: {available_html}
  </div>
  <p>other markets on the <a href="/" style="color:#d97c3c">homepage</a> may be available near you.</p>
  <a class="back" href="/">back to dollar bets</a>
  <p class="fine">dollar bets is an editorial site. we do not operate markets or verify user eligibility.</p>
</div>
</body>
</html>"""


def interstitial_html(platform_name, destination_url, market_id):
    """Generate a jurisdiction warning interstitial page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>leaving dollar bets</title>
<style>
  body {{
    background: #fdf6ee; color: #2d2319; font-family: 'Courier New', monospace;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; margin: 0; padding: 16px; box-sizing: border-box;
  }}
  .box {{
    max-width: 480px; width: 100%; border: 1px solid #e8cdb5; padding: 24px;
    background: #faf7f3;
  }}
  h1 {{ font-size: 16px; margin: 0 0 16px 0; text-transform: lowercase; color: #2d2319; }}
  p {{ font-size: 13px; line-height: 1.6; margin: 0 0 12px 0; color: #5a4e2f; }}
  .warn {{
    background: #fef9e7; border: 1px solid #d4c479; color: #5a4e2f;
    padding: 10px 12px; margin: 16px 0; font-size: 12px;
  }}
  a.go {{
    display: inline-block; margin-top: 16px; padding: 10px 24px;
    border: 2px solid #e8642c; color: #e8642c; text-decoration: none;
    font-family: 'Courier New', monospace; font-size: 14px; font-weight: 700;
  }}
  a.go:hover {{ background: #e8642c; color: #fdf6ee; }}
  a.back {{ color: #a08b77; font-size: 12px; margin-left: 16px; }}
  a.back:hover {{ color: #6b5744; }}
  .fine {{ font-size: 11px; color: #a08b77; margin-top: 20px; }}
</style>
</head>
<body>
<div class="box">
  <h1>you are leaving dollar bets</h1>
  <p>you are about to visit <strong>{platform_name}</strong> to view market <strong>{market_id}</strong>.</p>
  <div class="warn">
    <p>availability depends on your location. confirm you are in an eligible jurisdiction before continuing. dollar bets does not verify your eligibility.</p>
  </div>
  <p>dollar bets is an editorial site. we are not affiliated with, endorsed by, or acting as an agent of {platform_name}.</p>
  <a class="go" href="{destination_url}">continue to {platform_name}</a>
  <a class="back" href="/">go back</a>
  <p class="fine">by clicking continue you acknowledge that you are solely responsible for complying with the laws and regulations of your jurisdiction.</p>
</div>
</body>
</html>"""


def resolve_polymarket_url(market_url):
    """Fix Polymarket URLs by looking up the correct event slug via Gamma API.

    Polymarket /event/ URLs require the EVENT slug, but board data often stores
    the MARKET slug (which 404s). This looks up the market by its slug and
    returns the correct event URL.
    """
    if not market_url or "polymarket.com/event/" not in market_url:
        return market_url

    match = re.search(r'polymarket\.com/event/([^/?#]+)', market_url)
    if not match:
        return market_url

    slug = match.group(1)

    # Try markets endpoint — market slug → events[0].slug
    try:
        api_url = f"{POLYMARKET_GAMMA_API}/markets?slug={slug}&limit=1"
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/json",
            "User-Agent": "DollarBets/1.0"
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                events = data[0].get("events") or []
                if events and len(events) > 0:
                    event_slug = events[0].get("slug", "")
                    if event_slug and event_slug != slug:
                        return f"https://polymarket.com/event/{event_slug}"
                # No parent event — slug might already be an event slug
                return market_url
    except Exception:
        pass

    # Try events endpoint — maybe it's already correct
    try:
        api_url = f"{POLYMARKET_GAMMA_API}/events?slug={slug}&limit=1"
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/json",
            "User-Agent": "DollarBets/1.0"
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                return market_url  # Event slug is valid
    except Exception:
        pass

    return market_url  # Can't resolve — return as-is


def load_latest_board_data():
    """Load the most recent prediction market board JSON (excludes sports-*.json)."""
    site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    boards_dir = os.path.join(site_dir, "data", "boards")

    pattern = os.path.join(boards_dir, "*.json")
    files = [f for f in sorted(glob.glob(pattern), reverse=True)
             if os.path.basename(f)[0].isdigit()]

    if not files:
        return None

    try:
        with open(files[0]) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def find_market_in_board(market_id, board_data):
    """Find a market by ticker/ID in the board data."""
    if not board_data:
        return None

    for market in board_data.get("board", []):
        if market.get("ticker") == market_id:
            return market

    return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        market_id = params.get("market", [None])[0]
        requested_platform = params.get("platform", [None])[0]
        from_slug = params.get("from", [None])[0]
        back_path = fallback_path(from_slug)

        if not market_id:
            self.send_response(302)
            self.send_header("Location", back_path)
            self.end_headers()
            return

        # ── Sportsbook routing (SB- prefix) ──────────────────
        if market_id.startswith("SB-"):
            # Search across every sport board file (sports/underdogs/ocho/chalk/combo)
            market, source_slug = find_sports_market(market_id)

            # If the caller passed ?from=, prefer that for the back-link;
            # otherwise use the board where we actually found the ticker.
            sb_back_path = back_path if from_slug else fallback_path(source_slug)

            if not market:
                # SB ticker not found in any sport board — return user to
                # the originating board (or /the-lineup/ if unknown).
                self.send_response(302)
                self.send_header("Location", sb_back_path)
                self.end_headers()
                return

            url = market.get("url", "")
            book_slug = market.get("platform", "")
            book_display = SPORTSBOOK_DISPLAY_NAMES.get(book_slug, book_slug)
            title = market.get("title", market_id)

            # Resolve geo placeholders / domains using Vercel geo headers
            user_country = self.headers.get("x-vercel-ip-country", "")
            user_region = self.headers.get("x-vercel-ip-region", "")
            is_us = (user_country or "").upper() == "US"

            def _show_unavailable(state_label):
                html = sportsbook_unavailable_html(title, book_display, state_label, sb_back_path)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            # 1. {state} placeholder books (BetMGM, BetRivers)
            if "{state}" in url:
                if user_country and not is_us:
                    _show_unavailable(user_country)
                    return
                resolved = resolve_sportsbook_state(url, user_region, book_slug)
                if not resolved:
                    _show_unavailable(user_region)
                    return
                url = resolved

            # 2. FanDuel — rewrite parent domain to state subdomain
            elif book_slug == "fanduel" or "fanduel.com" in url:
                if user_country and not is_us:
                    _show_unavailable(user_country)
                    return
                resolved = rewrite_fanduel_url(url, user_region)
                if not resolved:
                    _show_unavailable(user_region)
                    return
                url = resolved

            # 3. DraftKings — single domain; gate by supported state
            elif book_slug == "draftkings" or "draftkings.com" in url:
                if user_country and not is_us:
                    _show_unavailable(user_country)
                    return
                if user_region and not is_draftkings_state_supported(user_region):
                    _show_unavailable(user_region)
                    return
                # If we have no region info, let DraftKings handle it
                # (their region detector will redirect or block as needed).

            # Serve interstitial before redirecting to sportsbook
            html = interstitial_html(book_display, url, title)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # ── Parlay routing (PARLAY- prefix) ──────────────────
        if market_id.startswith("PARLAY-"):
            # Parlays live in combo-*.json. If the ticker isn't found, send
            # the user back to the combo meal board.
            market, source_slug = find_sports_market(market_id)
            if not market:
                self.send_response(302)
                self.send_header("Location", "/combo-meal/")
                self.end_headers()
                return

            url = market.get("url", "")
            book_slug = market.get("platform", "")
            book_display = SPORTSBOOK_DISPLAY_NAMES.get(book_slug, book_slug or "Sportsbook")
            title = market.get("title", market_id)
            parlay_back = "/combo-meal/"

            # Apply the same geo logic as single SB- bets when applicable
            user_country = self.headers.get("x-vercel-ip-country", "")
            user_region = self.headers.get("x-vercel-ip-region", "")
            is_us = (user_country or "").upper() == "US"

            if "{state}" in url:
                if user_country and not is_us:
                    html = sportsbook_unavailable_html(title, book_display, user_country, parlay_back)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                    return
                resolved = resolve_sportsbook_state(url, user_region, book_slug)
                if not resolved:
                    html = sportsbook_unavailable_html(title, book_display, user_region, parlay_back)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                    return
                url = resolved
            elif book_slug == "fanduel" or "fanduel.com" in url:
                resolved = rewrite_fanduel_url(url, user_region) if is_us or not user_country else None
                if not resolved:
                    html = sportsbook_unavailable_html(title, book_display, user_region or user_country, parlay_back)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                    return
                url = resolved

            html = interstitial_html(book_display, url, title)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # ── Prediction market routing (KX/0x prefix) ─────────
        # Load current board data
        board_data = load_latest_board_data()
        market = find_market_in_board(market_id, board_data)

        if not market:
            # Market not found — fall back to direct Kalshi URL as best guess
            site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(site_dir, "config", "partners.json")
            try:
                with open(config_path) as f:
                    config = json.load(f)
                kalshi = next((p for p in config.get("partners", []) if p["slug"] == "kalshi"), None)
                if kalshi and kalshi.get("enabled"):
                    affiliate_id = kalshi.get("affiliate_id", "")
                    param_name = kalshi.get("tracking_param_name", "referral")
                    url = f"https://kalshi.com/markets/{market_id}"
                    if affiliate_id:
                        url += f"?{param_name}={affiliate_id}"
                    self.send_response(302)
                    self.send_header("Location", url)
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    return
            except Exception:
                pass

            # Last resort: send to Kalshi homepage with affiliate
            self.send_response(302)
            self.send_header("Location", "https://kalshi.com/markets/" + market_id + "?referral=e690aa11-1f29-49d1-b27f-d5e6ccf38d9f")
            self.end_headers()
            return

        # Get user's country from Vercel header
        user_country = self.headers.get("x-vercel-ip-country")

        # Per-market platform override (from board data) takes precedence
        # over query-string ?platform= param
        platform = market.get("platform") or requested_platform

        # Infer platform from ticker pattern when board data doesn't set it
        if not platform:
            if market_id.startswith("KX"):
                platform = "kalshi"
            elif market_id.startswith("0x"):
                platform = "polymarket"

        # For Polymarket: resolve the correct event URL via Gamma API
        market_url = market.get("url", "")
        if platform == "polymarket":
            market_url = resolve_polymarket_url(market_url)

        # Resolve to best eligible partner
        result = resolve_market_destination(
            market_id=market_id,
            user_country=user_country,
            market_category=market.get("category"),
            requested_platform=platform,
            market_url=market_url
        )

        if not result["eligible"]:
            # Load partner config for the blocked platform to show availability info
            site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(site_dir, "config", "partners.json")
            partner_config = {}
            platform_display = platform or "this platform"
            try:
                with open(config_path) as f:
                    config = json.load(f)
                for p in config.get("partners", []):
                    if p.get("slug") == platform:
                        partner_config = p
                        platform_display = p.get("display_name", platform)
                        break
            except Exception:
                pass

            html = unavailable_html(market_id, platform_display, user_country, partner_config)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # Serve jurisdiction interstitial instead of instant redirect
        platform_name = result.get("platform", "the market platform")
        display_names = {"kalshi": "Kalshi", "polymarket": "Polymarket", "coinbase": "Coinbase International"}
        display_names.update(SPORTSBOOK_DISPLAY_NAMES)
        display_name = display_names.get(platform_name, platform_name)

        html = interstitial_html(display_name, result["destination_url"], market_id)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
