#!/usr/bin/env python3
"""Pull every open Kalshi market that traded in the last 24 hours and write data/kalshi-top.json.

Feeds /best-kalshi-bets-today/ (generate_best_kalshi.py). Runs in the daily-scan workflow, never in
the Vercel build: the open catalogue is about 90,000 markets and takes minutes to page through.
Public API, no key. Stdlib only.

  python3 scripts/kalshi_top.py            # writes data/kalshi-top.json
  python3 scripts/kalshi_top.py --out x    # another path

Fails closed: a partial pull (API error part-way, or a page budget hit) exits 1 and leaves the old
file in place, because "most traded" computed from part of the catalogue would be wrong.
"""
import json, os, sys, time, datetime, urllib.request, urllib.error

API = "https://api.elections.kalshi.com/trade-api/v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_PAGES = 600          # 200 events a page; the catalogue was about 100 pages in November 2026
KEEP = 250               # rows kept by 24-hour volume, and again for markets settling soon


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "DollarBets/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def main():
    out = os.path.join(ROOT, "data", "kalshi-top.json")
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    rows, cursor, pages, events, active = [], "", 0, 0, 0
    t0 = time.time()
    while True:
        url = f"{API}/events?status=open&with_nested_markets=true&limit=200" + (f"&cursor={cursor}" if cursor else "")
        d = get(url)
        pages += 1
        for ev in d.get("events") or []:
            events += 1
            for m in ev.get("markets") or []:
                if m.get("status") != "active" or m.get("market_type") != "binary":
                    continue
                active += 1
                vol = num(m.get("volume_24h_fp"))
                ask = num(m.get("yes_ask_dollars"))
                if vol <= 0 or not (0 < ask < 1):
                    continue
                tk = m.get("ticker") or ""
                if not tk.startswith("KX"):
                    continue  # /go/ only routes KX tickers that are not on a board
                rows.append({
                    "ticker": tk,
                    "event_ticker": ev.get("event_ticker") or "",
                    "series_ticker": ev.get("series_ticker") or "",
                    "category": ev.get("category") or "",
                    "event_title": ev.get("title") or "",
                    "title": m.get("title") or "",
                    "yes_label": m.get("yes_sub_title") or "",
                    "yes_ask": ask,
                    "volume_24h": vol,
                    "close_time": m.get("close_time") or "",
                    "expected_expiration_time": m.get("expected_expiration_time") or "",
                })
        cursor = d.get("cursor") or ""
        if not cursor:
            break
        if pages >= MAX_PAGES:
            print(f"[kalshi-top] page budget hit at {pages} pages; not writing a partial file", file=sys.stderr)
            return 1
    traded = len(rows)
    rows.sort(key=lambda r: -r["volume_24h"])
    # Keep the head by volume, plus the most-traded market that settles within three days in every
    # event, so the "settles soon" lists are not crowded out by long-dated politics.
    soon_cut = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    keep, seen = rows[:KEEP], {r["ticker"] for r in rows[:KEEP]}
    # Sports and everything else are kept separately: on a Saturday the sports card alone
    # would fill the allowance.
    for is_sports in (True, False):
        per_event = {}
        for r in rows:
            when = min(t for t in (r["expected_expiration_time"], r["close_time"]) if t) if (r["expected_expiration_time"] or r["close_time"]) else ""
            if when and when <= soon_cut and r["ticker"] not in seen and (r["category"] == "Sports") == is_sports:
                per_event.setdefault(r["event_ticker"], r)
        keep += sorted(per_event.values(), key=lambda r: -r["volume_24h"])[:KEEP]
    doc = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": API + "/events",
        "events_read": events, "active_markets": active, "traded_24h": traded,
        "contracts_24h": round(sum(r["volume_24h"] for r in rows)),
        "markets": keep,
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(tmp, out)
    print(f"[kalshi-top] {pages} pages, {events} events, {active} active markets, {traded} traded in 24h, kept {len(keep)} in {time.time()-t0:.0f}s -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
