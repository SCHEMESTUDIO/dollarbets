#!/usr/bin/env python3
"""/trending/ — the prediction markets people are actually trading this week.

Built on every deploy from two live sources: Polymarket's top events by 24-hour volume
(one Gamma API call, public, no key) and today's Dollar Bets board (Kalshi + Polymarket,
already scored). Dated in the title so it reads as this week's page; the URL is stable.
Never fails the build: if the Polymarket call fails, the page renders from the board alone.

  python3 generate_trending.py
"""
import json, os, re, sys, glob, html, datetime, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import page_shell, write_page, market_link, format_payout, SITE_URL

GAMMA = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=120&order=volume24hr&ascending=false"
SPORTS = re.compile(r"sports|nfl|nba|mlb|nhl|soccer|ufc|tennis|esports|football|baseball|basketball|hockey|golf|f1|cricket|boxing|mma|premier league|epl|cfb|cbb|wnba|mls|league of legends|counter-strike|dota|valorant|games|match", re.I)
GROUPS = [
    ("politics & world", re.compile(r"politic|election|trump|iran|israel|geopolit|world|congress|senate|house|governor|president|shutdown|ukraine|russia|putin|primar", re.I)),
    ("economy & crypto", re.compile(r"fed|fomc|cpi|inflation|jobs|econom|bitcoin|ethereum|crypto|price|rate|oil|gold|stock|earn|ipo", re.I)),
    ("culture, tv & awards", re.compile(r"culture|tv|movie|film|emmy|oscar|grammy|music|netflix|box office|celebrit|reality|big brother|survivor|love island|rotten|award|spotify|billboard|tweet|elon", re.I)),
    ("weather & science", re.compile(r"weather|temperature|hurricane|snow|rain|climate|space|spacex|nasa|science|ai\b|openai|gpt", re.I)),
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
    best = None
    for m in ev.get("markets") or []:
        try: p = float(json.loads(m.get("outcomePrices") or "null")[0])
        except Exception: continue
        name = m.get("groupItemTitle") or m.get("question") or ""
        if re.match(r"^(Film|Party|Person|Candidate|Show|Team) [A-Z]$", name): continue
        if best is None or p > best[1]: best = (name, p)
    return best

def group_of(ev):
    blob = " ".join([ev.get("title") or ""] + [t.get("label") or "" for t in (ev.get("tags") or [])])
    if SPORTS.search(blob): return "sports"
    for g, rx in GROUPS:
        if rx.search(blob): return g
    return "everything else"

def latest_board():
    fs = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards", "2026-*.json")))
    if not fs: return None, []
    d = json.load(open(fs[-1])); return os.path.basename(fs[-1])[:-5], d.get("board", [])

def main():
    today = datetime.date.today()
    nice = today.strftime("%B %-d, %Y")
    events = fetch_poly()
    rows = []
    for ev in events:
        ld = leader(ev)
        if not ld: continue
        rows.append({"title": ev.get("title") or "", "slug": ev.get("slug") or "", "vol24": float(ev.get("volume24hr") or 0), "vol": float(ev.get("volume") or 0), "lead": ld, "group": group_of(ev), "n": len(ev.get("markets") or [])})
    groups = {}
    for r in rows: groups.setdefault(r["group"], []).append(r)
    order = ["politics & world", "economy & crypto", "culture, tv & awards", "weather & science", "everything else", "sports"]
    parts = []
    total24 = sum(r["vol24"] for r in rows)
    top_non_sports = [r for r in rows if r["group"] != "sports"][:5]
    qa = ""
    if rows:
        qa = f"The most-traded prediction markets this week, by 24-hour volume on Polymarket: " + "; ".join(f"{esc(r['title'])} ({esc(r['lead'][0])} at {r['lead'][1]*100:.0f}%, {money(r['vol24'])} traded)" for r in top_non_sports[:3]) + f". {len(rows)} markets traded a combined {money(total24)} in the last 24 hours. Prices refresh three times a day."
    for g in order:
        rs = groups.get(g) or []
        if not rs: continue
        rs = rs[:12] if g != "sports" else rs[:6]
        items = "".join(f'<li><a href="https://polymarket.com/event/{esc(r["slug"])}" rel="nofollow noopener">{esc(r["title"])}</a> &mdash; <strong>{esc(r["lead"][0])}</strong> {r["lead"][1]*100:.0f}% &middot; {money(r["vol24"])} in 24h{" &middot; " + str(r["n"]) + " outcomes" if r["n"] > 2 else ""}</li>' for r in rs)
        parts.append(f"<h2>{esc(g)}</h2>\n<ul style=\"font-size:13px;line-height:1.7;margin:8px 0 0 20px;list-style:disc\">{items}</ul>")
    board_date, board = latest_board()
    if board:
        bl = "".join(f'<li><a href="{market_link(b.get("ticker"))}">{esc(b.get("title"))}</a> &mdash; $1 pays {format_payout(b.get("payout", 0))}{(" &middot; <em>" + esc(b.get("quip")) + "</em>") if b.get("quip") else ""}</li>' for b in sorted(board, key=lambda b: -(b.get("payout") or 0))[:10])
        parts.append(f"<h2>today's dollar bets board</h2><p>The ten markets our scanner picked this morning for entertainment value, not volume. Kalshi and Polymarket, $1 each.</p><ul style=\"font-size:13px;line-height:1.7;margin:8px 0 0 20px;list-style:disc\">{bl}</ul>")
    body = f"""    <h1 class="page-title">trending prediction markets this week</h1>
    <div class="byline">updated {nice} &middot; refreshed three times a day from live exchange data</div>
    <div class="quick-answer" role="doc-abstract"><strong>Quick answer:</strong> {qa or "Live volume data is temporarily unavailable; the board below is today's scan."}</div>
    <div class="affiliate-strip">affiliate disclosure: dollar bets earns a commission if you sign up to kalshi through our links &mdash; never a cut of your bet. polymarket links carry no referral. <a href="/affiliate-disclosure/">full disclosure &rarr;</a></div>
    <div class="article-body">
      <p>What people are actually trading, ranked by money moved in the last 24 hours on Polymarket, grouped so the sports book does not bury everything else. The percentage is the leading outcome's price, which is the crowd's probability. Side-by-side Kalshi and Polymarket prices on the big political and awards markets live on our sister site, <a href="https://oddsdesk.vercel.app/" rel="noopener">Odds Desk</a>.</p>
      {chr(10).join(parts)}
      <h2>how to read this page</h2>
      <p>24-hour volume is dollars traded, not dollars at risk, so a market where two whales argue can outrank one with thousands of small traders. A leading outcome at 95% is a market that has mostly made up its mind; the interesting rows are the ones at 30 to 70. The list is automatic: no editor picked these, and no market is here because we like it.</p>
    </div>
    <div class="compliance-strip">Dollar Bets is an editorial and entertainment site. We do not operate markets or provide betting advice. Polymarket's global exchange does not serve US residents; Kalshi is a separate, CFTC-regulated platform, age-gated and not available in every state. Most longshot bets lose.</div>"""
    canonical = "/trending/"
    schema = json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": "Trending prediction markets this week", "url": SITE_URL + canonical, "dateModified": today.isoformat(), "description": "The most-traded prediction markets this week, by 24-hour volume, grouped by topic."})
    out = page_shell(title=f"Trending Prediction Markets This Week ({nice}) | Dollar Bets", description=f"The most-traded prediction markets right now, ranked by 24-hour volume and grouped by topic: politics, the economy, crypto, TV and awards, weather. Updated {nice}, refreshed three times a day.", body=body, canonical=canonical, extra_head=f'<script type="application/ld+json">{schema}</script>', compact_header=True)
    write_page("trending/index.html", out)
    print(f"[trending] {len(rows)} polymarket events, {len(board)} board picks, {money(total24)} 24h volume")

if __name__ == "__main__":
    main()
