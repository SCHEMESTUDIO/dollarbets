#!/usr/bin/env python3
"""
Dollar Bets — Market Link Redirect Handler (/go/ endpoint)

Routes market links through eligible partners based on user location.
Example: /go?market=KXGROK → resolves to best Kalshi/Polymarket/etc URL → 302 redirect

Vercel serverless function. Export: handler(request)
"""

import json
import os
import glob
from datetime import datetime

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


def handler(request):
    """
    Serverless function handler for Vercel.

    Query params:
      - market: Market ticker/ID (required, e.g., "KXGROK")
      - platform: Force a specific platform (optional, e.g., "kalshi")

    Returns:
      - 302 redirect to resolved market URL
      - 404 if market not found
      - 410 if no eligible partners
    """
    # Extract query parameters
    query_string = request.get("url", "").split("?", 1)
    params = {}
    if len(query_string) > 1:
        for part in query_string[1].split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v

    market_id = params.get("market")
    requested_platform = params.get("platform")

    if not market_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "missing ?market=TICKER"}),
            "headers": {"Content-Type": "application/json"}
        }

    # Load current board data
    board_data = load_latest_board_data()
    market = find_market_in_board(market_id, board_data)

    if not market:
        # Market not found in current board
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"market {market_id} not found"}),
            "headers": {"Content-Type": "application/json"}
        }

    # Get user's country from Vercel header
    headers = request.get("headers", {})
    user_country = headers.get("x-vercel-ip-country")

    # Resolve to best eligible partner
    result = resolve_market_destination(
        market_id=market_id,
        user_country=user_country,
        market_category=market.get("category"),
        requested_platform=requested_platform
    )

    if not result["eligible"]:
        # No eligible partner for this region
        return {
            "statusCode": 302,
            "headers": {"Location": "/unavailable/"}
        }

    # Redirect to resolved URL
    return {
        "statusCode": 302,
        "headers": {
            "Location": result["destination_url"],
            "Cache-Control": "no-cache"
        }
    }
