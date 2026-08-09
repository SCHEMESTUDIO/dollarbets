#!/usr/bin/env python3
"""
Dollar Bets — Market Link Redirect Handler (/go/ endpoint)

Routes market links through eligible partners based on user location.
Example: /go/KXGROK → resolves to best Kalshi/Polymarket/etc URL → 302 redirect

Vercel Python serverless function using BaseHTTPRequestHandler.
"""

import html
import json
import os
import re
import glob
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


# ── Input validation ──────────────────────────────────────────
# Market IDs may only contain letters, digits, hyphens, underscores, and dots.
# This prevents path-traversal, header-splitting, and reflected-XSS attacks via
# the /go/<slug>/ rewrite — even though Vercel's rewrite is fairly strict, the
# slug still reaches Python URL-decoded. Length cap is generous but bounded.
_MARKET_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,80}$")


def _is_valid_market_id(value):
    """True if value looks like a real ticker slug (no whitespace, no scheme)."""
    return bool(value) and bool(_MARKET_ID_RE.fullmatch(value))


# Destination-domain allowlist — any redirect Location must resolve to one of
# these hosts. Protects against open-redirect if a poisoned board JSON ever
# slips through the CMS without URL validation.
_ALLOWED_REDIRECT_HOSTS = {
    "kalshi.com", "www.kalshi.com",
    "polymarket.com", "www.polymarket.com",
    "coinbase.com", "www.coinbase.com",
    "sportsbook.fanduel.com",
    "draftkings.com", "www.draftkings.com", "sportsbook.draftkings.com",
    "sports.betmgm.com",
    "betmgm.com", "www.betmgm.com",
    "betrivers.com", "www.betrivers.com",
    # Offshore books (bovada.lv, betonline.ag) removed 2026-05-14: no affiliate
    # deal + US compliance exposure. Re-add only with a licensed agreement
    # and per-partner geo restrictions wired up via config/partners.json.
}


def _is_allowed_destination(url):
    """True if `url` is https and the host (or its parent) is in the allowlist."""
    if not url or not isinstance(url, str):
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("https",):
        return False
    host = (p.hostname or "").lower()
    if not host:
        return False
    # Exact match
    if host in _ALLOWED_REDIRECT_HOSTS:
        return True
    # Subdomain match: e.g. nj.sportsbook.fanduel.com → sportsbook.fanduel.com
    for allowed in _ALLOWED_REDIRECT_HOSTS:
        if host.endswith("." + allowed):
            return True
    return False

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
}

# Minimum age the user must acknowledge before being shown the outbound link.
# Sportsbooks: 21 (US standard). Polymarket / Coinbase: 18 (non-US markets).
# Kalshi: 21 to match the value in config/partners.json. Default for unknown
# platforms is 21 (strictest, fail-safe).
PLATFORM_MIN_AGE = {
    "kalshi": 21,
    "polymarket": 18,
    "coinbase": 18,
    "fanduel": 21,
    "draftkings": 21,
    "betmgm": 21,
    "betrivers": 21,
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


def _pick_related_markets(board_source_path_prefix, exclude_ticker, n=4):
    """Pick a few markets from a board file as escape-hatch suggestions.

    `board_source_path_prefix` is e.g. "sports" or "underdogs" or "" (for the
    main date-stamped prediction-market board). `exclude_ticker` is the
    ticker that just got blocked — we won't suggest it back to the user.

    Returns a list of {"title": str, "href": str} dicts ready to render.
    Always returns a list (possibly empty); never raises.
    """
    try:
        site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        boards_dir = os.path.join(site_dir, "data", "boards")
        if board_source_path_prefix:
            pattern = os.path.join(boards_dir, f"{board_source_path_prefix}-*.json")
        else:
            # Main board: date-stamped JSON, e.g. 2026-05-11.json
            pattern = os.path.join(boards_dir, "*.json")
        candidates = sorted(glob.glob(pattern), reverse=True)
        if not board_source_path_prefix:
            candidates = [c for c in candidates if os.path.basename(c)[0].isdigit()]
        if not candidates:
            return []
        with open(candidates[0]) as f:
            data = json.load(f)
        out = []
        for m in data.get("board", []):
            t = m.get("ticker", "")
            if not t or t == exclude_ticker:
                continue
            title = m.get("title", "").strip()
            if not title:
                continue
            href = f"/go/{t}/"
            out.append({"title": title, "href": href})
            if len(out) >= n:
                break
        return out
    except Exception:
        return []


def sportsbook_unavailable_html(market_title, book_display, user_state=None,
                                 user_country=None, back_path="/the-lineup/",
                                 related_markets=None):
    """Unavailable page when a sportsbook isn't available in the user's region.

    Adapts the copy to whether the user is in the US (state-level restriction)
    or non-US (country-level restriction). Also expands country codes to
    readable names via COUNTRY_NAMES.

    `related_markets` is an optional list of dicts (title, href) shown as
    escape-hatch links so the page isn't a dead end. Pass an empty list or
    None to omit that block.

    `back_path` is the URL the back-link returns to — typically the originating
    board (/underdogs/, /ocho/, /chalk/, /combo-meal/, /the-lineup/) so users
    aren't dumped on a board they didn't come from.
    """
    is_us = (user_country or "").upper() == "US"

    # Determine the region label + the noun forms (singular and plural)
    # used in copy. Plural needed for "varies by {x}. ... which {x}s are
    # supported." Naive +s would produce "countrys" — handle explicitly.
    if is_us and user_state:
        region_label = user_state.upper()
        region_noun = "state"
        region_plural = "states"
    elif user_country:
        # Non-US user (or no state info) — use the country name
        region_label = _country_name(user_country)
        region_noun = "country"
        region_plural = "countries"
    elif user_state:
        # Have a state code but no country — assume US to preserve old behavior
        region_label = user_state.upper()
        region_noun = "state"
        region_plural = "states"
    else:
        # No location data at all
        region_label = "your region"
        region_noun = "region"
        region_plural = "regions"

    # Derive a label from the path for the body link copy
    path_label = back_path.strip("/").replace("-", " ") or "lineup"

    # Escape every dynamic value once. region_label, market_title, book_display,
    # back_path, and path_label all flow into HTML below. region_label and
    # market_title in particular originate from board data (market_id is URL-
    # sourced via find_sports_market lookup but title is data-sourced).
    safe_region_label = html.escape(str(region_label), quote=True)
    safe_market_title = html.escape(str(market_title or ""), quote=True)
    safe_book_display = html.escape(str(book_display or ""), quote=True)
    safe_back_path = html.escape(str(back_path or "/"), quote=True)
    safe_path_label = html.escape(str(path_label or "lineup"), quote=True)

    # Optional related-markets escape-hatch block — internal /go/ links only
    if related_markets:
        related_items = "".join(
            f'<li><a href="{html.escape(m["href"], quote=True)}" style="color:#d97c3c">{html.escape(m["title"], quote=True)}</a></li>'
            for m in related_markets
        )
        related_block = f"""
  <div class="related">
    <p style="font-size:12px;color:#6b5744;margin:0 0 6px 0">other wagers on today's board:</p>
    <ul style="list-style:none;padding:0;margin:0;font-size:13px;line-height:1.7">
      {related_items}
    </ul>
  </div>"""
    else:
        related_block = ""

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
  .related {{ margin: 16px 0; padding: 10px 12px; border-left: 3px solid #e8cdb5; }}
  .related ul li {{ margin-bottom: 4px; }}
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
  <h1>sportsbook not available in your {region_noun}</h1>
  <p><strong>{safe_book_display}</strong> is not available in <strong>{safe_region_label}</strong> for the wager "{safe_market_title}".</p>
  <div class="warn">
    <p>sportsbook availability varies by {region_noun}. dollar bets does not control which {region_plural} are supported.</p>
  </div>
  {related_block}
  <p>check the <a href="{safe_back_path}" style="color:#d97c3c">{safe_path_label} board</a> for other wagers, or other boards for different sportsbooks.</p>
  <a class="back" href="{safe_back_path}">back to {safe_path_label}</a>
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


def unavailable_html(market_id, platform_display, user_country, partner_config,
                     related_markets=None):
    """Generate a geo-specific unavailable page.

    `related_markets` is an optional list of {"title", "href"} dicts shown as
    escape-hatch links so the page isn't a dead end. Pass None to omit.

    All dynamic values are HTML-escaped before interpolation.
    """
    user_location = html.escape(_country_name(user_country), quote=True)
    safe_platform = html.escape(str(platform_display or ""), quote=True)

    # Build blocked region description
    blocked = partner_config.get("blocked_countries", [])
    allowed = partner_config.get("allowed_countries", "all")
    safe_availability = html.escape(_describe_availability(partner_config), quote=True)

    if isinstance(allowed, list):
        # Allowlist model — user isn't on the list
        reason_html = f"<strong>{safe_platform}</strong> is only available in: <strong>{safe_availability}</strong>."
    elif user_country and user_country.upper() in blocked:
        reason_html = f"<strong>{safe_platform}</strong> is not available in <strong>{user_location}</strong>."
    else:
        reason_html = f"<strong>{safe_platform}</strong> is not available in your region."

    available_html = safe_availability

    # Optional related-markets escape-hatch block — internal /go/ links only
    if related_markets:
        related_items = "".join(
            f'<li><a href="{html.escape(m["href"], quote=True)}" style="color:#d97c3c">{html.escape(m["title"], quote=True)}</a></li>'
            for m in related_markets
        )
        related_block_html = f"""
  <div class="related">
    <p style="font-size:12px;color:#6b5744;margin:0 0 6px 0">other markets on today's board:</p>
    <ul style="list-style:none;padding:0;margin:0;font-size:13px;line-height:1.7">
      {related_items}
    </ul>
  </div>"""
    else:
        related_block_html = ""

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
  .related {{ margin: 16px 0; padding: 10px 12px; border-left: 3px solid #e8cdb5; }}
  .related ul li {{ margin-bottom: 4px; }}
  .fine {{ font-size: 11px; color: #a08b77; margin-top: 20px; }}
</style>
</head>
<body>
<div class="box">
  <h1>market not available in your region</h1>
  <p>you appear to be located in <strong>{user_location}</strong>. {reason_html}</p>
  <div class="warn">
    <p>dollar bets does not control platform availability. this restriction is set by {safe_platform}, not by us.</p>
  </div>
  <div class="available">
    <strong>{safe_platform}</strong> is available in: {available_html}
  </div>
  {related_block_html}
  <p>other markets on the <a href="/" style="color:#d97c3c">homepage</a> may be available near you.</p>
  <a class="back" href="/">back to dollar bets</a>
  <p class="fine">dollar bets is an editorial site. we do not operate markets or verify user eligibility.</p>
</div>
</body>
</html>"""


def interstitial_html(platform_name, destination_url, market_id, min_age=21):
    """Generate the /go/ interstitial — Ticket Stand dark design with combined age ack.

    All dynamic values are HTML-escaped. Outbound link carries
    rel="nofollow sponsored noopener noreferrer". One-tap age ack (checkbox)
    replaces the old two-step modal flow. Cookie semantics unchanged.
    """
    safe_platform = html.escape(str(platform_name or ""), quote=True)
    safe_market_id = html.escape(str(market_id or ""), quote=True)
    safe_destination = html.escape(str(destination_url or ""), quote=True)
    try:
        gate_age = int(min_age)
    except (TypeError, ValueError):
        gate_age = 21
    if gate_age < 18:
        gate_age = 18
    if gate_age > 21:
        gate_age = 21

    # Look up market details from latest board for the recap ticket
    board_data = load_latest_board_data()
    market = find_market_in_board(market_id, board_data) if board_data else None
    if market:
        m_title = html.escape(str(market.get("title", market_id)), quote=False)
        m_quip = html.escape(str(market.get("quip", "")), quote=False)
        m_payout_raw = market.get("payout", 0)
        m_payout = f"${m_payout_raw:.2f}" if m_payout_raw and m_payout_raw != int(m_payout_raw) else (f"${int(m_payout_raw)}" if m_payout_raw else "")
        platform_key = market.get("platform", "kalshi")
        reg_label = "CFTC-regulated" if platform_key == "kalshi" else "prediction market"
    else:
        m_title = html.escape(str(market_id), quote=False)
        m_quip = ""
        m_payout_raw = 0
        m_payout = ""
        reg_label = safe_platform

    payout_row_html = ""
    if m_payout:
        payout_row_html = f"""
          <div style="display:flex;align-items:baseline;gap:8px;margin-top:12px;border-top:1px dashed #d9c6ac;padding-top:12px;">
            <span style="font-size:12px;color:#806b5b;">$1 pays</span>
            <span style="font-family:'Archivo',sans-serif;font-weight:900;font-size:26px;color:#237a3f;letter-spacing:-0.5px;">{m_payout}</span>
            <span style="font-size:10px;color:#a08b77;margin-left:auto;text-align:right;">{safe_platform}<br>{reg_label}</span>
          </div>"""

    quip_html = f'<div style="font-size:11.5px;color:#6b5744;font-style:italic;margin-top:3px;">{m_quip}</div>' if m_quip else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>leaving dollar bets</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;900&family=IBM+Plex+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #2d2319;
    color: #d7c8b2;
    font-family: 'IBM Plex Mono', 'Courier New', monospace;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: #e8642c; }}
  a:hover {{ color: #ff8a50; }}
  .wrap {{
    max-width: 480px;
    width: 100%;
    padding: 32px 20px 24px;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
  }}
  .wordmark {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .wordmark-text {{
    font-family: 'Archivo', sans-serif;
    font-weight: 900;
    font-size: 16px;
    letter-spacing: -0.5px;
    color: #fdf6ee;
    text-decoration: none;
  }}
  .wordmark-text span {{ color: #e8642c; }}
  .leaving-label {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #93836c;
  }}
  .ticket {{
    background: #fdf6ee;
    border-radius: 12px;
    padding: 16px;
    margin-top: 20px;
    position: relative;
    color: #2d2319;
    overflow: hidden;
  }}
  .ticket-notch-l {{
    position: absolute;
    left: -8px;
    top: 62%;
    width: 16px;
    height: 16px;
    background: #2d2319;
    border-radius: 50%;
  }}
  .ticket-notch-r {{
    position: absolute;
    right: -8px;
    top: 62%;
    width: 16px;
    height: 16px;
    background: #2d2319;
    border-radius: 50%;
  }}
  .ticket-label {{
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #b5470a;
  }}
  .ticket-title {{
    font-family: 'Archivo', sans-serif;
    font-weight: 700;
    font-size: 17px;
    line-height: 1.3;
    margin-top: 4px;
    color: #2d2319;
  }}
  .juris-note {{
    background: rgba(254,249,231,0.06);
    border: 1px solid #5a4e3f;
    border-radius: 10px;
    padding: 12px 14px;
    margin-top: 16px;
    font-size: 11.5px;
    line-height: 1.7;
    color: #b7a894;
  }}
  .age-label {{
    display: flex;
    gap: 12px;
    align-items: flex-start;
    margin-top: 16px;
    font-size: 12.5px;
    line-height: 1.6;
    color: #d7c8b2;
    cursor: pointer;
  }}
  .age-label input[type="checkbox"] {{
    width: 20px;
    height: 20px;
    accent-color: #e8642c;
    margin: 1px 0 0;
    flex-shrink: 0;
    cursor: pointer;
  }}
  .cta-btn {{
    display: block;
    margin-top: 16px;
    background: #e8642c;
    color: #fff;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 700;
    font-size: 15px;
    text-align: center;
    border-radius: 10px;
    padding: 15px;
    min-height: 48px;
    box-sizing: border-box;
    text-decoration: none;
    transition: background 0.15s ease;
    pointer-events: none;
    opacity: 0.5;
  }}
  .cta-btn.enabled {{
    pointer-events: auto;
    opacity: 1;
  }}
  .cta-btn.enabled:hover {{ background: #c4341c; color: #fff; }}
  .back-link {{
    text-align: center;
    font-size: 12px;
    color: #93836c;
    margin-top: 14px;
    text-decoration: underline;
    display: block;
  }}
  .back-link:hover {{ color: #d7c8b2; }}
  .fine-print {{
    margin-top: auto;
    font-size: 10px;
    color: #6f6250;
    line-height: 1.7;
    padding-top: 28px;
  }}
  .fine-print a {{ color: #93836c; text-decoration: underline; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="wordmark">
    <a href="/" class="wordmark-text">DOLLAR<span>BETS</span></a>
    <span class="leaving-label">leaving &rarr;</span>
  </div>

  <div class="ticket">
    <div class="ticket-notch-l"></div>
    <div class="ticket-notch-r"></div>
    <div class="ticket-label">your pick</div>
    <div class="ticket-title">{m_title}</div>
    {quip_html}
    {payout_row_html}
  </div>

  <div class="juris-note">availability depends on your location &mdash; confirm you're in an eligible jurisdiction before continuing. dollar bets doesn't verify eligibility and isn't affiliated with, endorsed by, or an agent of {safe_platform}.</div>

  <label class="age-label">
    <input type="checkbox" id="age-ack">
    <span>i'm <strong style="color:#fdf6ee;">{gate_age} or older</strong> and responsible for complying with the laws of my jurisdiction.</span>
  </label>

  <a href="{safe_destination}" target="_blank" rel="nofollow sponsored noopener noreferrer" id="cta-btn" class="cta-btn">continue to {safe_platform} &raquo;</a>

  <a href="/" class="back-link">go back to the board</a>

  <div class="fine-print">by continuing you acknowledge you are solely responsible for complying with the laws and regulations of your jurisdiction. struggling with gambling? <a href="/responsible-gambling/">get help &rarr;</a></div>
</div>

<script>
(function() {{
  var minAge = {gate_age};
  var match = document.cookie.match(/(?:^|;\\s*)db_age_ack=(\\d+)/);
  var acked = match ? parseInt(match[1], 10) : 0;
  var checkbox = document.getElementById('age-ack');
  var btn = document.getElementById('cta-btn');

  // Pre-check if already acked at this age threshold
  if (acked >= minAge) {{
    checkbox.checked = true;
    btn.classList.add('enabled');
  }}

  checkbox.addEventListener('change', function() {{
    if (this.checked) {{
      btn.classList.add('enabled');
      var newAck = Math.max(acked, minAge);
      document.cookie = 'db_age_ack=' + newAck + ';max-age=31536000;path=/;samesite=lax;secure';
    }} else {{
      btn.classList.remove('enabled');
    }}
  }});
}})();
</script>
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

        # Reject anything that doesn't look like a ticker slug. This is the
        # main defense against reflected XSS, header injection, and path
        # traversal via the /go/<slug>/ rewrite — the slug reaches Python
        # URL-decoded by parse_qs, so we re-validate the shape here.
        if not _is_valid_market_id(market_id):
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return

        # requested_platform may also be reflected into HTML / consulted in
        # lookups — keep it strict.
        if requested_platform and not re.fullmatch(r"[a-z0-9_\-]{1,32}", requested_platform):
            requested_platform = None

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

            def _show_unavailable(_unused=None):
                # Pull a few related markets from the same sports board so the
                # page isn't a dead end. source_slug maps to the file prefix:
                # the-lineup→sports, underdogs→underdogs, the-ocho→ocho, etc.
                source_to_prefix = {
                    "the-lineup": "sports",
                    "underdogs": "underdogs",
                    "the-ocho": "ocho",
                    "chalk": "chalk",
                    "combo-meal": "combo",
                }
                prefix = source_to_prefix.get(source_slug, "sports")
                related = _pick_related_markets(prefix, market_id, n=4)
                html = sportsbook_unavailable_html(
                    title, book_display,
                    user_state=user_region or None,
                    user_country=user_country or None,
                    back_path=sb_back_path,
                    related_markets=related,
                )
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

            # Refuse to interstitial any URL that escapes the allowlist —
            # protects against a poisoned board JSON pointing at an arbitrary
            # third-party host.
            if not _is_allowed_destination(url):
                self.send_response(302)
                self.send_header("Location", "/the-lineup/")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return

            # Serve interstitial before redirecting to sportsbook
            html_body = interstitial_html(
                book_display, url, title,
                min_age=PLATFORM_MIN_AGE.get(book_slug, 21),
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html_body.encode("utf-8"))
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

            def _show_parlay_unavailable():
                # Parlays come from combo-*.json — suggest other parlays first.
                related = _pick_related_markets("combo", market_id, n=4)
                html = sportsbook_unavailable_html(
                    title, book_display,
                    user_state=user_region or None,
                    user_country=user_country or None,
                    back_path=parlay_back,
                    related_markets=related,
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            if "{state}" in url:
                if user_country and not is_us:
                    _show_parlay_unavailable()
                    return
                resolved = resolve_sportsbook_state(url, user_region, book_slug)
                if not resolved:
                    _show_parlay_unavailable()
                    return
                url = resolved
            elif book_slug == "fanduel" or "fanduel.com" in url:
                resolved = rewrite_fanduel_url(url, user_region) if is_us or not user_country else None
                if not resolved:
                    _show_parlay_unavailable()
                    return
                url = resolved

            if not _is_allowed_destination(url):
                self.send_response(302)
                self.send_header("Location", "/combo-meal/")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return

            html_body = interstitial_html(
                book_display, url, title,
                min_age=PLATFORM_MIN_AGE.get(book_slug, 21),
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html_body.encode("utf-8"))
            return

        # ── Prediction market routing (KX/0x prefix) ─────────
        # Load current board data
        board_data = load_latest_board_data()
        market = find_market_in_board(market_id, board_data)

        if not market:
            # Market not found in current board data (stale link, removed
            # market, ticker drift, or recap-page reference to a past board).
            # Infer the platform from the ticker prefix so a card labeled
            # "Polymarket" doesn't fall through to a Kalshi affiliate URL.
            #
            # Convention:
            #   KX...  → Kalshi
            #   0x...  → Polymarket
            #   other  → no safe platform inference; bounce to homepage
            inferred_slug = None
            if market_id.startswith("KX"):
                inferred_slug = "kalshi"
            elif market_id.startswith("0x"):
                inferred_slug = "polymarket"

            if inferred_slug is None:
                # Can't safely infer — return to homepage rather than
                # crediting an arbitrary affiliate.
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return

            # For Polymarket we can't construct a working market URL from
            # just the ticker (Polymarket uses event slugs that don't match
            # the contract address). Their base_url in partners.json points
            # at a 404-equivalent page. Bounce stale 0x tickers home instead
            # of dumping the user on a broken third-party page.
            if inferred_slug == "polymarket":
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return

            # Kalshi case: ticker == market slug, so /markets/{ticker}
            # generally works (or lands on Kalshi's own "market not found"
            # page which is at least an on-brand experience).
            site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(site_dir, "config", "partners.json")
            try:
                with open(config_path) as f:
                    config = json.load(f)
                partner = next((p for p in config.get("partners", []) if p["slug"] == inferred_slug), None)
                if partner and partner.get("enabled"):
                    base = partner.get("base_url", "")
                    affiliate_id = partner.get("affiliate_id", "")
                    param_name = partner.get("tracking_param_name", "ref")
                    url = f"{base.rstrip('/')}/{market_id}"
                    if affiliate_id:
                        sep = "&" if "?" in url else "?"
                        url = f"{url}{sep}{param_name}={affiliate_id}"
                    # market_id was already shape-validated above, but the
                    # partner base_url could in principle have drifted. Gate
                    # the final URL on the allowlist before redirecting.
                    if not _is_allowed_destination(url):
                        self.send_response(302)
                        self.send_header("Location", "/")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        return
                    self.send_response(302)
                    self.send_header("Location", url)
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    return
            except Exception:
                pass

            # Last resort: bounce home rather than guess a destination.
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-cache")
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

            # Suggest a few other markets from today's main board so the page
            # isn't a dead end. "" = date-stamped main board (not sports).
            related = _pick_related_markets("", market_id, n=4)
            html = unavailable_html(market_id, platform_display, user_country, partner_config, related_markets=related)
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

        dest = result["destination_url"]
        if not _is_allowed_destination(dest):
            # Destination escapes the allowlist (e.g. poisoned board data).
            # Refuse to interstitial — bounce the user home instead.
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return

        html_body = interstitial_html(
            display_name, dest, market_id,
            min_age=PLATFORM_MIN_AGE.get(platform_name, 21),
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html_body.encode("utf-8"))
