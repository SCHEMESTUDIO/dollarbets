#!/usr/bin/env python3
"""/trending/ — the prediction markets people are actually trading this week.

Hub page in the board's own card language. Built on every deploy from two live sources:
Polymarket's top events by 24-hour volume (one Gamma API call, public, no key) and today's
Dollar Bets board (Kalshi + Polymarket, already scored). Dated in the title; stable URL.
Never fails the build: if the Polymarket call fails, the page renders from the board alone.

  python3 generate_trending.py
"""
import json, os, re, sys, glob, html, datetime, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import page_shell, write_page, market_link, format_payout, render_bet_card, SITE_URL, _latest_board_meta
from editorial import nyt_date

GAMMA = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=120&order=volume24hr&ascending=false"
SPORTS = re.compile(r"sports|nfl|nba|mlb|nhl|soccer|ufc|tennis|esports|football|baseball|basketball|hockey|golf|f1|cricket|boxing|mma|premier league|epl|cfb|cbb|wnba|mls|league of legends|counter-strike|dota|valorant|games|match", re.I)
GROUPS = [
    ("politics", "Politics and the world", re.compile(r"politic|election|trump|iran|israel|geopolit|world|congress|senate|house|governor|president|shutdown|ukraine|russia|putin|primar|prime minister|parliament", re.I)),
    ("economy", "Economy and crypto", re.compile(r"fed|fomc|cpi|inflation|jobs|econom|bitcoin|ethereum|crypto|price|rate|oil|gold|stock|earn|ipo|market cap", re.I)),
    ("culture", "Culture, TV and awards", re.compile(r"culture|tv|movie|film|emmy|oscar|grammy|music|netflix|box office|celebrit|reality|big brother|survivor|love island|rotten|award|spotify|billboard|tweet|elon", re.I)),
    ("science", "Weather and science", re.compile(r"weather|temperature|hurricane|snow|rain|climate|space|spacex|nasa|science|ai\b|openai|gpt|anthropic", re.I)),
]

def esc(s): return html.escape(str(s or ""))
def money(v):
    v = float(v or 0)
    return f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}k" if v >= 1e3 else f"${v:.0f}"

def fetch_poly():
    try:
        req = urllib.request.Request(GAMMA, headers={"User-Agent": "DollarBets/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r: return json.loads(r.read())
    except Exception as e:
        print(f"[trending] polymarket fetch failed: {e}", file=sys.stderr); return []

def leader(ev):
    """Leading outcome. For ladder events (strikes, date ranges) where the top rung is ~100%,
    the interesting rung is the one nearest a coin flip."""
    rows = []
    for m in ev.get("markets") or []:
        try: p = float(json.loads(m.get("outcomePrices") or "null")[0])
        except Exception: continue
        name = m.get("groupItemTitle") or m.get("question") or ""
        if re.match(r"^(Film|Party|Person|Candidate|Show|Team) [A-Z]$", name): continue
        rows.append((name, p))
    if not rows: return None
    rows.sort(key=lambda r: -r[1])
    live = [r for r in rows if 0.03 < r[1] < 0.97]
    if len(rows) > 2 and rows[0][1] >= 0.97:
        if not live: return None  # every rung resolved or dead: nothing to say
        return min(live, key=lambda r: abs(r[1] - 0.5))
    return rows[0]

def group_of(ev):
    blob = " ".join([ev.get("title") or ""] + [t.get("label") or "" for t in (ev.get("tags") or [])])
    if SPORTS.search(blob): return "sports"
    for key, label, rx in GROUPS:
        if rx.search(blob): return key
    return "other"

def latest_board():
    fs = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards", "2026-*.json")))
    if not fs: return None, []
    d = json.load(open(fs[-1])); return os.path.basename(fs[-1])[:-5], d.get("board", [])

def price_class(p):
    return "hot" if p >= 0.8 else "warm" if p >= 0.5 else ""

def card(r, rank):
    name, p = r["lead"]
    lead_name = esc(name)
    if lead_name.lower() == r["title"].lower(): lead_name = "Yes"
    outcomes = f" &middot; {r['n']} outcomes" if r["n"] > 2 else ""
    return f'''<a class="hub-card{" hot" if rank <= 3 else ""}" href="https://polymarket.com/event/{esc(r["slug"])}" target="_blank" rel="nofollow noopener">
  <div class="hub-card-inner"><div class="hub-rank">{rank}</div>
  <div class="hub-card-body"><div class="hub-title">{esc(r["title"])}</div>
  <div class="hub-lead"><span class="hub-price {price_class(p)}">{p*100:.0f}%</span><span class="hub-lead-name">{lead_name}</span></div>
  <div class="hub-meta">{money(r["vol24"])} traded in 24h &middot; {money(r["vol"])} all time{outcomes}</div></div>
  <div class="hub-cta">See odds &raquo;</div></div></a>'''

def main():
    today = datetime.date.today()
    nice = nyt_date(today)
    events = fetch_poly()
    rows = []
    for ev in events:
        ld = leader(ev)
        if not ld: continue
        rows.append({"title": ev.get("title") or "", "slug": ev.get("slug") or "", "vol24": float(ev.get("volume24hr") or 0), "vol": float(ev.get("volume") or 0), "lead": ld, "group": group_of(ev), "n": len(ev.get("markets") or [])})
    groups = {}
    for r in rows: groups.setdefault(r["group"], []).append(r)
    total24 = sum(r["vol24"] for r in rows)
    non_sports = [r for r in rows if r["group"] != "sports"]
    bm = _latest_board_meta() or {}
    def _nyt(ds):
        try: return nyt_date(datetime.datetime.strptime(ds, "%B %d, %Y").date())
        except Exception: return ds
    read_line = f"read {bm['scan_time_et']} on {_nyt(bm['date_str'])}" if bm.get("scan_time_et") else f"as of {nice}"

    parts = []
    # Hero: the single most-traded non-sports market
    if non_sports:
        h = non_sports[0]; name, p = h["lead"]
        parts.append(f'''<a class="hub-hero" href="https://polymarket.com/event/{esc(h["slug"])}" target="_blank" rel="nofollow noopener">
  <div class="hub-hero-label">Most money moved today</div>
  <div class="hub-hero-title">{esc(h["title"])}</div>
  <div class="hub-hero-row"><span class="hub-hero-price">{p*100:.0f}%</span><span class="hub-hero-lead">{esc(name)}</span><span class="hub-hero-meta">{money(h["vol24"])} in 24h<br>{money(h["vol"])} all time</span></div>
  <div class="hub-hero-cta">See the odds on Polymarket &raquo;</div></a>''')
    if rows:
        parts.append(f'''<div class="hub-stats"><div class="hub-stat"><div class="l">Markets tracked</div><div class="v">{len(rows)}</div></div><div class="hub-stat"><div class="l">Traded in 24h</div><div class="v">{money(total24)}</div></div><div class="hub-stat"><div class="l">Not sports</div><div class="v">{len(non_sports)}</div></div></div>''')
    # Section chips
    order = [k for k, _, _ in GROUPS] + ["other", "sports"]
    labels = {k: l for k, l, _ in GROUPS}; labels["other"] = "Everything else"; labels["sports"] = "Sports"
    chips = "".join(f'<a href="#{k}">{labels[k]}</a>' for k in order if groups.get(k))
    if chips: parts.append(f'<nav class="nav section-chips" aria-label="Sections">{chips}<a href="#board">Today\'s board</a></nav>')
    for k in order:
        rs = groups.get(k) or []
        if not rs: continue
        rs = rs[:12] if k != "sports" else rs[:6]
        vol = sum(r["vol24"] for r in rs)
        parts.append(f'<div class="hub-kicker" id="{k}">{labels[k]} <span>{money(vol)} in 24h across the top {len(rs)}</span></div><div class="hub-list">' + "".join(card(r, i + 1) for i, r in enumerate(rs)) + '</div>')
    board_date, board = latest_board()
    if board:
        picks = sorted(board, key=lambda b: -(b.get("payout") or 0))[:6]
        parts.append(f'<div class="hub-kicker" id="board">Today\'s Dollar Bets board <span>our scanner\'s picks for entertainment value, not volume</span></div><ul class="board-list" style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:12px">' + "".join(render_bet_card(b) for b in picks) + '</ul><a href="/" class="board-promo-cta">See all {len(board)} on today\'s board &rarr;</a>')

    qa = ""
    if non_sports:
        qa = "The most-traded prediction markets this week, by 24-hour volume on Polymarket: " + "; ".join(f"{esc(r['title'])} ({esc(r['lead'][0])} at {r['lead'][1]*100:.0f}%, {money(r['vol24'])})" for r in non_sports[:3]) + f". {len(rows)} markets moved {money(total24)} in the last 24 hours."
    body = f"""    <h1 class="page-title">Trending Prediction Markets This Week</h1>
    <div class="byline">By <a href="/about/">Dollar Bets Staff</a> &middot; Updated <time datetime="{today.isoformat()}">{nice}</time></div>
    <div class="sourcing">Volume and prices from Polymarket, {read_line}; refreshed three times a day &middot; <a href="/editorial-policy/">Editorial policy</a></div>
    <p class="dek" role="doc-abstract">{qa or "Live volume data is temporarily unavailable; the board below is today's scan."}</p>
    {chr(10).join(parts)}
    <div class="article-body" style="margin-top:22px">
      <h2 id="how">How to read this page</h2>
      <p>What people are actually trading, ranked by money moved in the last 24 hours on Polymarket, grouped so the sports book does not bury everything else. The percentage is the leading outcome's price, which is the crowd's probability. For ladder markets (a price above a strike, a date by which something happens) we show the rung nearest a coin flip, because a rung at 100% tells you nothing.</p>
      <p>24-hour volume is dollars traded, not dollars at risk, so a market where two whales argue can outrank one with thousands of small traders. A leading outcome at 95% has mostly made up its mind; the interesting rows sit between 30 and 70. The list is automatic: no editor picked these, and no market is here because we like it. Side-by-side Kalshi and Polymarket prices on the big political and awards markets live on our sister site, <a href="https://oddsdesk.vercel.app/" rel="noopener">Odds Desk</a>.</p>
    </div>
    <div class="affiliate-strip">Affiliate disclosure: Dollar Bets earns a commission if you sign up to Kalshi through our links, never a cut of your bet. Polymarket links carry no referral. <a href="/affiliate-disclosure/">Full disclosure &rarr;</a></div>
    <div class="compliance-strip">Dollar Bets is an editorial and entertainment site. We do not operate markets or provide betting advice. Polymarket's global exchange does not serve US residents; Kalshi is a separate, CFTC-regulated platform, age-gated and not available in every state. Most longshot bets lose.</div>"""
    canonical = "/trending/"
    schema = json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": "Trending prediction markets this week", "url": SITE_URL + canonical, "dateModified": today.isoformat(), "description": "The most-traded prediction markets this week, by 24-hour volume, grouped by topic."})
    out = page_shell(title=f"Trending Prediction Markets This Week ({nice}) | Dollar Bets", description=f"The most-traded prediction markets right now, ranked by 24-hour volume and grouped by topic: politics, the economy, crypto, TV and awards, weather. Updated {nice}, refreshed three times a day.", body=body, canonical=canonical, extra_head=f'<script type="application/ld+json">{schema}</script>', compact_header=True, article=True, sticky_html="")
    write_page("trending/index.html", out)
    print(f"[trending] {len(rows)} polymarket events, {len(board)} board picks, {money(total24)} 24h volume")

if __name__ == "__main__":
    main()
