#!/usr/bin/env python3
"""/best-kalshi-bets-today/ and /kalshi-payout-calculator/.

The first is a browse page built from data/kalshi-top.json (written three times a day by
scripts/kalshi_top.py in the daily-scan workflow): every open Kalshi market that traded in the
last 24 hours, ranked by stated measures (contracts traded, price, time to settlement). Nothing on
it is a pick. The second is a static calculator using the fee formula in Kalshi's published fee
schedule. Both are built on every deploy and never fail the build: with no data file the list page
renders from the Dollar Bets board alone.

  python3 generate_best_kalshi.py
"""
import json, os, sys, html, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import page_shell, write_page, market_link, render_bet_card, SITE_URL
from generate_trending import latest_board
from editorial import nyt_date

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("KALSHI_TOP_FILE") or os.path.join(ROOT, "data", "kalshi-top.json")
LIST_PATH = "/best-kalshi-bets-today/"
CALC_PATH = "/kalshi-payout-calculator/"
MIN_HOURS_LEFT = 3
STALE_HOURS = 36   # older than this and the live lists are dropped; the page says so
FEE_RATE = 0.07    # Kalshi fee schedule: fees = round up(M x 0.07 x C x P x (1-P))
MAKER_RATE = 0.0175
CALC_UPDATED = datetime.date(2026, 11, 21)  # move when the calculator or the fee schedule changes


def esc(s): return html.escape(str(s or ""))


def fee(contracts, price, mult=1.0, rate=FEE_RATE):
    """Kalshi's general trading fee in dollars, rounded up to the next cent as in its fee table."""
    return math.ceil(round(mult * rate * contracts * price * (1 - price) * 100, 6)) / 100


def cents(p):
    c = p * 100
    return f"{c:.0f}¢" if abs(c - round(c)) < 0.05 else f"{c:.1f}¢"


def pays(p):
    v = 1 / p
    return f"${v:,.2f}" if v < 100 else f"${v:,.0f}"


def count(v):
    v = float(v or 0)
    return f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}k" if v >= 1e4 else f"{v:,.0f}"


def parse(ts):
    try: return datetime.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except ValueError: return None


def et(dt):
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return dt


def settles(m, now):
    """When the market is expected to settle: the earlier of the two times Kalshi gives."""
    ts = [t for t in (parse(m.get("expected_expiration_time")), parse(m.get("close_time"))) if t]
    return min(ts) if ts else None


def when_label(dt, now):
    if not dt: return ""
    d = et(dt); n = et(now)
    days = (d.date() - n.date()).days
    if days <= 0: return "settles today"
    if days == 1: return "settles tomorrow"
    if days < 7: return "settles " + d.strftime("%A")
    if d.year == n.year: return "settles " + nyt_date(d.date()).rsplit(",", 1)[0]
    return "settles " + nyt_date(d.date())


def names(m):
    """(headline, outcome). Kalshi puts the question on the event and the side on the market."""
    ev, title, side = (m.get("event_title") or "").strip(), (m.get("title") or "").strip(), (m.get("yes_label") or "").strip()
    head = ev or title
    out = side or title
    if title and title.lower() not in (head.lower(), out.lower()) and len(title) < 90 and not side:
        out = title
    if out.lower() == head.lower(): out = "Yes"
    return head, out


def one_per_event(rows, n):
    seen, out = set(), []
    for r in rows:
        if r["event_ticker"] in seen: continue
        seen.add(r["event_ticker"]); out.append(r)
        if len(out) == n: break
    return out


def card(m, rank, now, hot=3):
    head, out = names(m)
    p = m["yes_ask"]
    cls = "hot" if p >= 0.8 else "warm" if p >= 0.5 else ""
    st = settles(m, now)
    return f'''<a class="hub-card{" hot" if rank <= hot else ""}" href="{market_link(m["ticker"])}" rel="nofollow" data-platform="kalshi" data-ticker="{esc(m["ticker"])}" data-payout="{1/p:.2f}" data-settles="{st.strftime("%Y-%m-%dT%H:%M:%SZ") if st else ""}">
  <div class="hub-card-inner"><div class="hub-rank">{rank}</div>
  <div class="hub-card-body"><div class="hub-title">{esc(head)}</div>
  <div class="hub-lead"><span class="hub-price {cls}">{cents(p)}</span><span class="hub-lead-name">{esc(out)} &middot; pays {pays(p)} per $1</span></div>
  <div class="hub-meta">{count(m["volume_24h"])} contracts in 24h &middot; {when_label(settles(m, now), now)}</div></div>
  <div class="hub-cta">See it on Kalshi &raquo;</div></div></a>'''


def section(key, label, note, rows, now):
    if not rows: return ""
    return (f'<div class="hub-kicker" id="{key}">{label} <span>{note}</span></div><div class="hub-list">'
            + "".join(card(r, i + 1, now) for i, r in enumerate(rows)) + "</div>")


def load():
    try:
        d = json.load(open(DATA))
    except (OSError, json.JSONDecodeError):
        return None
    gen = parse(d.get("generated_at"))
    if not gen or not d.get("markets"): return None
    d["_gen"] = gen
    return d


def build_list(now):
    d = load()
    fresh = bool(d) and (now - d["_gen"]).total_seconds() < STALE_HOURS * 3600
    parts, chips, qa, read_line, stats = [], [], "", "", ""
    if fresh:
        ms = []
        for m in d["markets"]:
            s = settles(m, now)
            # A reader sees this list up to eight hours after the read, so anything settling
            # inside three hours of it (15-minute and hourly crypto markets) is left out.
            if s and (s - d["_gen"]).total_seconds() < MIN_HOURS_LEFT * 3600: continue
            if not (0.02 <= m["yes_ask"] <= 0.98): continue
            m["_days"] = (s - now).total_seconds() / 86400 if s else 9999
            ms.append(m)
        ms.sort(key=lambda m: -m["volume_24h"])
        soon = [m for m in ms if m["_days"] <= 3]
        sports = lambda m: (m.get("category") or "") == "Sports"
        groups = [
            ("soon", "Most traded, settling soon", "not sports, settles within three days", one_per_event([m for m in soon if not sports(m)], 10)),
            ("sports", "Most traded in sports", "games and props settling within three days", one_per_event([m for m in soon if sports(m)], 10)),
            ("coinflips", "Closest calls", "priced between 40¢ and 60¢, settles within three days", one_per_event([m for m in soon if 0.40 <= m["yes_ask"] <= 0.60], 8)),
            ("favorites", "Heavy favorites", "priced at 80¢ or more, settles within three days", one_per_event([m for m in soon if 0.80 <= m["yes_ask"] <= 0.97], 8)),
            ("longshots", "Longshots with money behind them", "priced at 15¢ or less, settles within a week", one_per_event([m for m in ms if m["yes_ask"] <= 0.15 and m["_days"] <= 7], 8)),
            ("alltime", "Most traded on Kalshi today", "any settlement date", one_per_event(ms, 10)),
        ]
        for key, label, note, rows in groups:
            sec = section(key, label, note, rows, now)
            if sec:
                parts.append(sec); chips.append(f'<a href="#{key}">{label}</a>')
        g = et(d["_gen"])
        read_line = f"read {g.strftime('%-I:%M %p').replace('AM', 'a.m.').replace('PM', 'p.m.')} ET on {nyt_date(g.date())}"
        stats = (f'<div class="hub-stats"><div class="hub-stat"><div class="l">Markets that traded</div><div class="v">{d.get("traded_24h", 0):,}</div></div>'
                 f'<div class="hub-stat"><div class="l">Contracts in 24h</div><div class="v">{count(d.get("contracts_24h", 0))}</div></div>'
                 f'<div class="hub-stat"><div class="l">Open markets</div><div class="v">{count(d.get("active_markets", 0))}</div></div></div>')
        top, lead_in = groups[0][3][:3], "The most-traded Kalshi bets settling soon: "
        if not top:
            top, lead_in = groups[5][3][:3], "The most-traded Kalshi bets today: "
        if top:
            bits = []
            for m in top:
                head, out = names(m)
                bits.append(f"{esc(head)} ({esc(out)} at {cents(m['yes_ask'])}, pays {pays(m['yes_ask'])} per $1)")
            qa = lead_in + "; ".join(bits) + f". {d.get('traded_24h', 0):,} Kalshi markets traded in the last 24 hours."
    board_date, board = latest_board()
    kalshi_board = [b for b in board if b.get("platform", "kalshi") == "kalshi"]
    if kalshi_board:
        picks = sorted(kalshi_board, key=lambda b: -(b.get("payout") or 0))[:6]
        parts.append('<div class="hub-kicker" id="board">Strangest Kalshi bets today <span>from the Dollar Bets board, chosen for entertainment</span></div>'
                     '<ul class="board-list" style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:12px">'
                     + "".join(render_bet_card(b) for b in picks)
                     + '</ul><a href="/crazy-kalshi-bets/" class="board-promo-cta">The craziest Kalshi bets right now &rarr;</a>')
        chips.append('<a href="#board">Strangest</a>')
    today = et(now).date()
    nice = nyt_date(today)
    dek = qa or "Live Kalshi volume is temporarily unavailable. The list below is today's Dollar Bets board."
    sourcing = (f"Prices and volume from Kalshi's public market data, {read_line}; refreshed three times a day" if read_line
                else "From today's Dollar Bets board")
    faqs = [
        ("What are the best Kalshi bets today?",
         "This page ranks every Kalshi market that traded in the last 24 hours by contracts traded, price, and time to settlement. The lists are automatic and are not tips. The most-traded markets settling soon are at the top."),
        ("How much does a Kalshi bet pay?",
         "Every Kalshi contract pays $1 if it lands and nothing if it does not. A contract bought at 25¢ pays $4 for every $1 staked before fees, and a contract bought at 80¢ pays $1.25."),
        ("What fee does Kalshi charge?",
         "Kalshi's published fee schedule charges 7% of the contract price times one minus the price, per contract, rounded up. That is at most about 1.75¢ on a 50¢ contract, and less toward either end."),
        ("Is a heavily traded Kalshi market a safer bet?",
         "No. Volume shows where people are trading. It says nothing about which side wins. A price is the market's estimate of the chance, and most longshots lose."),
    ]
    faq_html = "".join(f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in faqs)
    body = f"""    <h1 class="page-title">The Best Kalshi Bets Today</h1>
    <div class="byline">By <a href="/about/">Dollar Bets Staff</a> &middot; Updated <time datetime="{today.isoformat()}">{nice}</time></div>
    <div class="sourcing">{sourcing} &middot; <a href="/editorial-policy/">Editorial policy</a></div>
    <p class="dek" role="doc-abstract">{dek}</p>
    {stats}
    {'<nav class="nav section-chips" aria-label="Sections">' + "".join(chips) + '</nav>' if chips else ''}
    {chr(10).join(parts)}
    <div class="article-body" style="margin-top:22px">
      <h2 id="how">How these lists are made</h2>
      <p>Every open Kalshi market that traded in the last 24 hours is read three times a day and sorted by measures you can check: contracts traded, the price of Yes, and when the market settles. One market is shown per event, so a 30-rung price ladder takes one row. No editor chose a row, and no row is a tip.</p>
      <p>The price is what one Yes contract costs. Each contract pays $1 if it lands, so a 25¢ contract pays $4 for every $1 staked and an 80¢ contract pays $1.25. The price is also the market's estimate of the chance: at 25¢ the market expects the bet to lose three times in four. Payouts on this page are before Kalshi's trading fee. The <a href="{CALC_PATH}">Kalshi payout calculator</a> works out the fee, the profit, and the break-even chance for any price and stake.</p>
      <p>Volume counts contracts changing hands. Two large traders arguing can put a market above one with thousands of small buyers. Prices move between reads, so check the live price on Kalshi before you buy.</p>
      <h2 id="faq">Frequently asked questions</h2>
      {faq_html}
    </div>
    <div class="affiliate-strip">Affiliate disclosure: Dollar Bets may earn a commission if you sign up to Kalshi through our links, never a cut of your bet. <a href="/affiliate-disclosure/">Full disclosure &rarr;</a></div>
    <div class="internal-links"><div class="internal-links-row">related: <a href="/crazy-kalshi-bets/">craziest Kalshi bets</a> &middot; <a href="{CALC_PATH}">Kalshi payout calculator</a> &middot; <a href="/trending/">trending markets</a> &middot; <a href="/kalshi-vs-polymarket/">Kalshi vs. Polymarket</a></div></div>
    <div class="compliance-strip">Dollar Bets is an editorial and entertainment site. We do not operate markets or provide betting advice. Kalshi is a CFTC-regulated exchange, age-gated and not available in every state. Most longshot bets lose.</div>
    {LIST_JS}"""
    schema = [
        {"@context": "https://schema.org", "@type": "WebPage", "name": "The best Kalshi bets today", "url": SITE_URL + LIST_PATH, "dateModified": today.isoformat(),
         "description": "Kalshi markets ranked by contracts traded, price, and time to settlement."},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]
    out = page_shell(
        title=f"Best Kalshi Bets Today ({nice}) | Dollar Bets",
        description=f"Best Kalshi bets today, ranked by contracts traded, price, and settlement time: most traded, closest calls, favorites, and longshots. Updated {nice}.",
        body=body, canonical=LIST_PATH,
        extra_head="".join(f'<script type="application/ld+json">{json.dumps(s)}</script>' for s in schema),
        compact_header=True, article=True, sticky_html="")
    write_page("best-kalshi-bets-today/index.html", out)
    print(f"[best-kalshi] live data {'fresh' if fresh else 'absent or stale'}, {len(parts)} sections, {len(kalshi_board)} board picks")


LIST_JS = """<script>(function(){var n=Date.now();document.querySelectorAll('a.hub-card[data-settles]').forEach(function(a){var t=Date.parse(a.getAttribute('data-settles'));if(t&&t<n)a.hidden=true;});})();</script>"""

CALC_CSS = """
    .calc { background:#fff; border:1.5px solid #e8cdb5; border-radius:12px; padding:16px; margin-top:18px; }
    .calc-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .calc label { display:block; font-family:'IBM Plex Mono',monospace; font-size:10.5px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#806b5b; }
    .calc input, .calc select { width:100%; box-sizing:border-box; margin-top:5px; padding:10px 11px; font:600 17px 'Archivo',sans-serif; color:#2d2319; background:#fdf6ee; border:1.5px solid #e8cdb5; border-radius:8px; }
    .calc input:focus, .calc select:focus { outline:2px solid #e8642c; outline-offset:1px; }
    .calc-hint { font-size:11px; color:#a08b77; margin-top:4px; line-height:1.4; }
    .calc-out { margin-top:16px; background:#2d2319; color:#fdf6ee; border-radius:10px; padding:14px 16px; }
    .calc-big { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
    .calc-big .v { font:900 34px 'Archivo',sans-serif; color:#7fd89a; letter-spacing:-0.5px; line-height:1; }
    .calc-big .l { font-size:12px; color:#d9c6ac; }
    .calc-rows { margin-top:12px; display:grid; grid-template-columns:1fr auto; gap:6px 14px; font-size:13.5px; }
    .calc-rows .k { color:#d9c6ac; } .calc-rows .n { font-family:'IBM Plex Mono',monospace; font-weight:700; text-align:right; }
    .calc-note { font-size:11px; color:#a08b77; margin-top:10px; line-height:1.5; }
    .calc-cta { display:flex; align-items:center; justify-content:center; margin-top:12px; min-height:46px; background:#e8642c; color:#fff; border-radius:8px; font:700 13px 'IBM Plex Mono',monospace; text-decoration:none; }
    .calc-cta:hover { background:#b5470a; }
    .fee-table { width:100%; border-collapse:collapse; margin-top:12px; font-size:14px; }
    .fee-table th, .fee-table td { text-align:right; padding:7px 8px; border-bottom:1px solid #eadfce; font-family:'IBM Plex Mono',monospace; }
    .fee-table th { font-size:10.5px; letter-spacing:1px; text-transform:uppercase; color:#806b5b; }
    .fee-table th:first-child, .fee-table td:first-child { text-align:left; }
    @media (max-width:520px) { .calc-grid { grid-template-columns:1fr; } }
"""

CALC_JS = """
(function(){
  var $=function(id){return document.getElementById(id)};
  function fee(c,p,m,rate){ return Math.ceil(Math.round(m*rate*c*p*(1-p)*1e6)/1e4)/100; }
  function money(v){ return (v<0?'-':'')+'$'+Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
  function american(p){ return p>=0.5 ? '-'+Math.round(100*p/(1-p)) : '+'+Math.round(100*(1-p)/p); }
  function run(){
    var p=parseFloat($('c-price').value)/100, stake=parseFloat($('c-stake').value), mode=$('c-mode').value;
    var m=parseFloat($('c-mult').value), order=$('c-order').value, exit=parseFloat($('c-exit').value)/100;
    var out=$('c-out');
    if(!(p>0&&p<1)||!(stake>0)||!(m>=0)){ out.hidden=true; $('c-err').textContent='Enter a price from 1 to 99 cents and an amount above zero.'; $('c-err').hidden=false; return; }
    $('c-err').hidden=true; out.hidden=false;
    var rate = order==='maker' ? 0.0175 : 0.07;
    var mm = order==='free' ? 0 : m;
    var c;
    if(mode==='contracts'){ c=Math.floor(stake); }
    else { c=Math.floor(stake/p+1e-9); while(c>0 && c*p+fee(c,p,mm,rate) > stake+1e-9) c--; }
    if(c<1){ out.hidden=true; $('c-err').hidden=false; $('c-err').textContent='That stake does not cover one contract at this price.'; return; }
    var cost=c*p, f=fee(c,p,mm,rate), outlay=cost+f, payout=c, profit=payout-outlay;
    $('o-profit').textContent=money(profit);
    $('o-contracts').textContent=c.toLocaleString('en-US');
    $('o-cost').textContent=money(cost);
    $('o-fee').textContent=money(f);
    $('o-outlay').textContent=money(outlay);
    $('o-payout').textContent=money(payout);
    $('o-return').textContent=(100*profit/outlay).toFixed(1)+'%';
    $('o-per').textContent=money(payout/outlay);
    $('o-implied').textContent=(100*p).toFixed(1)+'%';
    $('o-breakeven').textContent=(100*outlay/payout).toFixed(1)+'%';
    $('o-american').textContent=american(p);
    $('o-lose').textContent=money(-outlay);
    var er=$('o-exit-row'), ev=$('o-exit');
    if(exit>0&&exit<1){ var ef=fee(c,exit,mm,rate); ev.textContent=money(c*exit-ef-outlay); er.hidden=false; ev.hidden=false; }
    else { er.hidden=true; ev.hidden=true; }
  }
  ['c-price','c-stake','c-mode','c-mult','c-order','c-exit'].forEach(function(id){ $(id).addEventListener('input',run); $(id).addEventListener('change',run); });
  try{ var q=new URLSearchParams(location.search); var qp=parseFloat(q.get('p')); if(qp>0&&qp<100) $('c-price').value=qp; var qs=parseFloat(q.get('stake')); if(qs>0) $('c-stake').value=qs; }catch(e){}
  run();
})();
"""


def build_calc(now):
    today = CALC_UPDATED
    nice = nyt_date(today)
    rows = "".join(
        f"<tr><td>{cents(p)}</td><td>${fee(1, p):.2f}</td><td>${fee(100, p):.2f}</td><td>{pays(p)}</td><td>${100 - 100*p - fee(100, p):,.2f}</td></tr>"
        for p in (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99))
    faqs = [
        ("How do you calculate a Kalshi payout?",
         "Every contract pays $1 if it lands. Divide your stake by the price to get the number of contracts, and that number is your payout in dollars. Profit is the payout minus what you paid and minus the trading fee."),
        ("What is the Kalshi fee formula?",
         "Kalshi's fee schedule gives the general trading fee as 0.07 times the number of contracts, times the price, times one minus the price, rounded up. A fee multiplier applies on some markets. The fee is largest at 50¢ and shrinks toward 1¢ and 99¢."),
        ("Does Kalshi charge a fee when a market settles?",
         "No. Kalshi's fee schedule lists no settlement fee. The trading fee is charged when your order is matched, and again if you sell before settlement."),
        ("Do limit orders pay a fee on Kalshi?",
         "Kalshi charges the trading fee on orders that match immediately. An order that rests on the book pays no fee on most markets. Some markets carry a maker fee of 0.0175 times contracts, times price, times one minus the price."),
        ("How do Kalshi prices convert to odds?",
         "The price is the implied chance. A 25¢ contract implies 25%, which is +300 in American odds. An 80¢ contract implies 80%, which is -400."),
    ]
    faq_html = "".join(f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in faqs)
    body = f"""    <h1 class="page-title">Kalshi Payout Calculator</h1>
    <div class="byline">By <a href="/about/">Dollar Bets Staff</a> &middot; Updated <time datetime="{today.isoformat()}">{nice}</time></div>
    <div class="sourcing">Fee formula from <a href="https://kalshi.com/docs/kalshi-fee-schedule.pdf" rel="noopener">Kalshi's fee schedule</a> &middot; <a href="/editorial-policy/">Editorial policy</a></div>
    <p class="dek" role="doc-abstract">Enter a Kalshi price and a stake to see the contracts you get, the trading fee, the payout, the profit, and the chance you need to break even.</p>
    <div class="calc">
      <div class="calc-grid">
        <div><label for="c-price">Price per contract (cents)</label><input id="c-price" type="number" inputmode="decimal" min="1" max="99" step="1" value="25"><div class="calc-hint">The Yes or No price shown on Kalshi, 1 to 99.</div></div>
        <div><label for="c-stake">Amount</label><input id="c-stake" type="number" inputmode="decimal" min="0" step="1" value="100"><div class="calc-hint"><select id="c-mode" aria-label="Amount is in" style="font-size:13px;padding:6px 8px"><option value="dollars">Dollars to spend, fee included</option><option value="contracts">Number of contracts</option></select></div></div>
        <div><label for="c-order">Order type</label><select id="c-order"><option value="taker">Fills immediately (trading fee)</option><option value="free">Rests on the book (no fee on most markets)</option><option value="maker">Rests on the book, market with a maker fee</option></select></div>
        <div><label for="c-mult">Fee multiplier</label><input id="c-mult" type="number" inputmode="decimal" min="0" step="0.05" value="1"><div class="calc-hint">1 on most markets. Kalshi lists exceptions in its fee schedule.</div></div>
        <div><label for="c-exit">Sell early at (cents, optional)</label><input id="c-exit" type="number" inputmode="decimal" min="1" max="99" step="1" placeholder="Leave blank to hold"><div class="calc-hint">Profit if you sell before settlement, with the second fee.</div></div>
      </div>
      <div class="calc-out" id="c-out">
        <div class="calc-big"><span class="v" id="o-profit"></span><span class="l">profit if it lands</span></div>
        <div class="calc-rows">
          <span class="k">Contracts</span><span class="n" id="o-contracts"></span>
          <span class="k">Cost of contracts</span><span class="n" id="o-cost"></span>
          <span class="k">Trading fee</span><span class="n" id="o-fee"></span>
          <span class="k">Total you pay</span><span class="n" id="o-outlay"></span>
          <span class="k">Payout if it lands</span><span class="n" id="o-payout"></span>
          <span class="k">Return on what you pay</span><span class="n" id="o-return"></span>
          <span class="k">Pays per $1, after the fee</span><span class="n" id="o-per"></span>
          <span class="k">Chance the price implies</span><span class="n" id="o-implied"></span>
          <span class="k">Chance you need to break even</span><span class="n" id="o-breakeven"></span>
          <span class="k">American odds</span><span class="n" id="o-american"></span>
          <span class="k">If it does not land</span><span class="n" id="o-lose"></span>
          <span class="k" id="o-exit-row" hidden>Profit if you sell early</span><span class="n" id="o-exit" hidden></span>
        </div>
      </div>
      <div class="calc-note" id="c-err" hidden>Enter a price from 1 to 99 cents and an amount above zero.</div>
      <a class="calc-cta" href="{LIST_PATH}">See the best Kalshi bets today &raquo;</a>
      <div class="calc-note">Fees are rounded up to the next cent, as in Kalshi's general fee table. Your order ticket on Kalshi shows the exact fee before you confirm.</div>
    </div>
    <div class="article-body" style="margin-top:22px">
      <h2 id="formula">How a Kalshi payout works</h2>
      <p>A Kalshi contract pays $1 if the outcome you bought happens and nothing if it does not. The price is what you pay for that $1. Buy 400 contracts at 25¢ and you pay $100. If the bet lands you receive $400, a $300 gain before fees. If it does not, you lose the $100.</p>
      <p>The trading fee comes from Kalshi's fee schedule: 0.07 &times; contracts &times; price &times; (1 &minus; price), rounded up. On those 400 contracts at 25¢ the fee is $5.25, so the profit is $294.75. Kalshi charges no fee at settlement. Selling before settlement is a second trade with its own fee.</p>
      <h2 id="table">Kalshi fees and payouts by price</h2>
      <table class="fee-table"><thead><tr><th>Price</th><th>Fee, 1 contract</th><th>Fee, 100 contracts</th><th>Pays per $1</th><th>Profit on 100, after fee</th></tr></thead><tbody>{rows}</tbody></table>
      <p>The fee is largest in the middle and small at the ends. A 50¢ contract carries 1.75¢ of fee per contract in bulk, which moves the break-even chance from 50% to 51.75%. A 5¢ longshot carries about a third of a cent.</p>
      <h2 id="faq">Frequently asked questions</h2>
      {faq_html}
    </div>
    <div class="affiliate-strip">Affiliate disclosure: Dollar Bets may earn a commission if you sign up to Kalshi through our links, never a cut of your bet. <a href="/affiliate-disclosure/">Full disclosure &rarr;</a></div>
    <div class="internal-links"><div class="internal-links-row">related: <a href="{LIST_PATH}">best Kalshi bets today</a> &middot; <a href="/crazy-kalshi-bets/">craziest Kalshi bets</a> &middot; <a href="/kalshi-vs-polymarket/">Kalshi vs. Polymarket</a> &middot; <a href="/kalshi-perpetuals/">Kalshi perpetuals</a></div></div>
    <div class="compliance-strip">Dollar Bets is an editorial and entertainment site. We do not operate markets or provide betting advice. This calculator is an estimate from Kalshi's published fee schedule; fees on some markets differ. Kalshi is a CFTC-regulated exchange, age-gated and not available in every state.</div>
    <script>{CALC_JS}</script>"""
    schema = [
        {"@context": "https://schema.org", "@type": "WebApplication", "name": "Kalshi payout calculator", "url": SITE_URL + CALC_PATH, "applicationCategory": "FinanceApplication",
         "operatingSystem": "Any", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "description": "Works out contracts, trading fee, payout, profit, and break-even chance for a Kalshi price and stake."},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]
    out = page_shell(
        title="Kalshi Payout Calculator: Fees and Profit | Dollar Bets",
        description="Free Kalshi payout calculator. Enter a price and a stake to get the trading fee, payout, profit, break-even chance, and American odds.",
        body=body, canonical=CALC_PATH,
        extra_head=f"<style>{CALC_CSS}</style>" + "".join(f'<script type="application/ld+json">{json.dumps(s)}</script>' for s in schema),
        compact_header=True, article=True, sticky_html="")
    write_page("kalshi-payout-calculator/index.html", out)
    print("[best-kalshi] calculator page written")


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    build_list(now)
    build_calc(now)


if __name__ == "__main__":
    main()
