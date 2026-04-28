#!/usr/bin/env python3
"""
Dollar Bets — Market Link Redirect Handler (/go/ endpoint)

Routes market links through eligible partners based on user location.
Example: /go/KXGROK → resolves to best Kalshi/Polymarket/etc URL → 302 redirect

Vercel Python serverless function using BaseHTTPRequestHandler.
"""

import json
import os
import glob
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent directory to path so we can import link_resolver
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from link_resolver import resolve_market_destination


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

        # Resolve to best eligible partner
        result = resolve_market_destination(
            market_id=market_id,
            user_country=user_country,
            market_category=market.get("category"),
            requested_platform=requested_platform,
            market_url=market.get("url")
        )

        if not result["eligible"]:
            self.send_response(302)
            self.send_header("Location", "/unavailable/")
            self.end_headers()
            return

        # Redirect to resolved URL
        self.send_response(302)
        self.send_header("Location", result["destination_url"])
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
