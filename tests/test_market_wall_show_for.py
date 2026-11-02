#!/usr/bin/env python3
"""Offline checks for the market wall's `show_for` gate and per-book notes (no network).

Run from the repo root:
    python3 tests/test_market_wall_show_for.py

The Kalshi Perps row (config/market-wall.json) must appear only on crypto-price
markets, carry its tracking link and its note, and never show on a politics market.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

import market_wall  # noqa: E402

CFG = market_wall.load_config()
PERPS = next(b for b in CFG["books"] if b["slug"] == "kalshi_perps")

BTC = {"ticker": "pmus-btc-1", "title": "Bitcoin hits $150k by fall 2027", "platform": "polymarket_us",
       "category": "Crypto", "payout": 12.5, "url": "https://polymarket.us/event/bitcoin?marketSlug=x"}
POL = {"ticker": "KXGOV-1", "title": "The US government shuts down on October 1", "platform": "kalshi",
       "category": "Politics", "payout": 50.0, "url": "https://kalshi.com/markets/KXGOVTSHUTDOWN"}
ETH_OTHER = {"ticker": "KXETH-1", "title": "Ethereum above $3,000 on Friday", "platform": "kalshi",
             "category": "Other", "payout": 4.0, "url": "https://kalshi.com/markets/KXETH"}


def rows_for(market):
    info = market_wall.build_rows(market, "prediction", "US", "NY", "/crazy-kalshi-bets/",
                                  cfg=CFG, alternatives={}, allow=lambda u: True)
    return info["rows"], info


def main():
    assert market_wall._book_shows_for(PERPS, BTC), "category match"
    assert market_wall._book_shows_for(PERPS, ETH_OTHER), "title match"
    assert not market_wall._book_shows_for(PERPS, POL), "politics must not match"
    assert market_wall._book_shows_for({"slug": "x"}, POL), "no show_for means everywhere"
    for title in ("Silver hits $72 this month", "Gold above $4,000 by Friday", "WTI oil price above $100 this year",
                  "S&P 500 closes above 7,000 in 2026", "Nasdaq record high this week", "ETH above $3,000 on Friday",
                  "XRP hits $2 this month"):
        assert market_wall._book_shows_for(PERPS, {"title": title, "category": "Other"}), title
    for title in ("Jake Burger wins the AL Gold Glove at first", "Silver Spoon wins Best Picture",
                  "Oil spill cleanup finished by June", "Dow Constantine re-elected", "Solid gold toilet sold at auction"):
        assert not market_wall._book_shows_for(PERPS, {"title": title, "category": "Other"}), title

    rows, info = rows_for(BTC)
    slugs = [r["slug"] for r in rows]
    assert "kalshi_perps" in slugs, slugs
    perps = next(r for r in rows if r["slug"] == "kalshi_perps")
    assert perps["url"] == PERPS["affiliate_url"], perps["url"]
    assert perps["pays"] and perps["relation"] == "browse"
    assert perps["note"].startswith("Kalshi Perps is a different product")
    html = market_wall.wall_html(BTC, "prediction", info)
    assert html.count("Kalshi Perps is a different product") == 1
    assert "/kalshi-perpetuals/" in html
    assert PERPS["affiliate_url"] in html

    rows, info = rows_for(POL)
    assert "kalshi_perps" not in [r["slug"] for r in rows]
    html = market_wall.wall_html(POL, "prediction", info)
    assert "Kalshi Perps" not in html

    # A UK visitor: the row sits in the "outside" expander, never in the main list.
    info = market_wall.build_rows(BTC, "prediction", "GB", "", "/", cfg=CFG, alternatives={}, allow=lambda u: True)
    assert "kalshi_perps" not in [r["slug"] for r in info["rows"]]
    assert "kalshi_perps" in [r["slug"] for r in info["other_rows"]]
    print("ok: market wall show_for + notes")


if __name__ == "__main__":
    main()
