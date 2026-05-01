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
    background: #0a0a0a; color: #b0b0b0; font-family: 'Courier New', monospace;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; margin: 0; padding: 16px; box-sizing: border-box;
  }}
  .box {{
    max-width: 480px; width: 100%; border: 1px solid #333; padding: 24px;
  }}
  h1 {{ color: #e0e0e0; font-size: 16px; margin: 0 0 16px 0; text-transform: lowercase; }}
  p {{ font-size: 13px; line-height: 1.6; margin: 0 0 12px 0; }}
  .warn {{ color: #cc8800; border-left: 3px solid #cc8800; padding-left: 12px; margin: 16px 0; }}
  a.go {{
    display: inline-block; margin-top: 16px; padding: 8px 20px;
    border: 1px solid #555; color: #e0e0e0; text-decoration: none;
    font-family: 'Courier New', monospace; font-size: 13px;
  }}
  a.go:hover {{ border-color: #888; }}
  a.back {{ color: #666; font-size: 12px; margin-left: 16px; }}
  .fine {{ font-size: 11px; color: #666; margin-top: 20px; }}
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
    """Load the most recent board JSON file from data/boards/."""
    site_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    boards_dir = os.path.join(site_dir, "data", "boards")

    pattern = os.path.join(boards_dir, "*.json")
    files = sorted(glob.glob(pattern), reverse=True)

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

        if not market_id:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

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
            self.send_response(302)
            self.send_header("Location", "/unavailable/")
            self.end_headers()
            return

        # Serve jurisdiction interstitial instead of instant redirect
        platform_name = result.get("platform", "the market platform")
        display_names = {"kalshi": "Kalshi", "polymarket": "Polymarket", "coinbase": "Coinbase International"}
        display_name = display_names.get(platform_name, platform_name)

        html = interstitial_html(display_name, result["destination_url"], market_id)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
