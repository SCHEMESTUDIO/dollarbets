"""Market wall: the page a visitor sees after clicking a card (James, 2026-11-01).

Replaces the leaving interstitial. One page, rendered per visitor from the
country and state Vercel puts on the request, listing every book that can take
the pick in that place: paying books first (best payout first within the
group), unpaid books last. Two exceptions, both from James:

  1. A visitor who arrives from a page whose path names a book (crazy-kalshi-
     bets, funny-polymarket-bets, ...) sees that book first.
  2. A market no paying book carries shows its own book first.

Books and switches: config/market-wall.json. Same-or-similar markets on the
other venues: data/alternatives.json, written by scanner.py each morning.
Every dynamic value is HTML-escaped; every destination passes the caller's
host allowlist before it is rendered. Stdlib only.
"""

import glob
import html
import json
import os
import re
from datetime import datetime, timezone

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SITE_DIR, "config", "market-wall.json")
ALTS_PATH = os.path.join(SITE_DIR, "data", "alternatives.json")
BOARDS_DIR = os.path.join(SITE_DIR, "data", "boards")
GA4_ID = "G-W2V9QGFCM5"

RELATION_RANK = {"same": 0, "similar": 1, "browse": 2}
US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "Washington, DC", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
COUNTRY_NAMES = {"US": "the United States", "GB": "the UK", "CA": "Canada", "AU": "Australia", "DE": "Germany",
                 "IE": "Ireland", "NZ": "New Zealand", "FR": "France", "ES": "Spain", "NL": "the Netherlands"}


# ── Data ─────────────────────────────────────────────────────

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"enabled": False, "books": []}


def load_alternatives():
    try:
        with open(ALTS_PATH) as f:
            return (json.load(f) or {}).get("markets") or {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def checked_ago():
    """'12 mins ago' / '3 hours ago' since the alternatives index was written,
    which is when the prices on the wall were last checked. '' if unknown."""
    try:
        with open(ALTS_PATH) as f:
            stamp = (json.load(f) or {}).get("generated_at") or ""
        then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        mins = int((datetime.now(timezone.utc) - then).total_seconds() // 60)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        return ""
    if mins < 1:
        return "just now"
    if mins < 90:
        return f"{mins} min{'s' if mins != 1 else ''} ago"
    hours = mins // 60
    if hours < 36:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return f"{hours // 24} days ago"


def find_market_any_board(ticker):
    """The market record for a ticker from any board, newest first.
    Returns (market, kind) with kind 'sports' for the sports boards and
    'prediction' for the date-stamped board, or (None, None)."""
    if not ticker:
        return None, None
    files = sorted(glob.glob(os.path.join(BOARDS_DIR, "*.json")), reverse=True)
    for path in files:
        name = os.path.basename(path)
        kind = "prediction" if name[0].isdigit() else "sports"
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for m in (data.get("board") or []):
            if m.get("ticker") == ticker:
                return m, kind
    return None, None


def wall_enabled(cfg, category, country):
    if not cfg.get("enabled"):
        return False
    if (category or "") in (cfg.get("off_for_categories") or []):
        return False
    if (country or "").upper() in [c.upper() for c in (cfg.get("off_for_countries") or [])]:
        return False
    return True


# ── Rows ─────────────────────────────────────────────────────

def _book_allows_country(book, country):
    c = (country or "").upper()
    allowed = book.get("countries", "all")
    blocked = [x.upper() for x in (book.get("blocked_countries") or [])]
    if c in blocked:
        return False
    if allowed == "all":
        return True
    return c in [x.upper() for x in allowed]


def _destination(book, url):
    """The outbound URL: a full affiliate link wins, else the book's own
    param appended, else the plain URL."""
    if book.get("affiliate_url"):
        return book["affiliate_url"]
    aid = book.get("affiliate_id") or ""
    param = book.get("tracking_param_name") or ""
    if url and aid and param:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{param}={aid}"
    return url


def _fmt_payout(p):
    try:
        v = float(p)
    except (TypeError, ValueError):
        return ""
    if v <= 0:
        return ""
    return f"${v:.2f}" if v != int(v) else f"${int(v)}"


def build_rows(market, kind, country, region, referer_path, own_row=None, allow=None,
               cfg=None, alternatives=None):
    """Rows for the wall.

    market:   the board record (title, platform, payout, url, category, ...)
    kind:     'prediction' or 'sports'
    own_row:  for sports, the row for the market's own book as api/go.py
              resolved it: {"url": str|None, "eligible": bool}; None otherwise
    allow:    callable(url) -> bool, the redirect host allowlist
    Returns a dict: rows (eligible, ordered), other_rows (for the region
    expander), gate_age, place (where we think the visitor is), region_key.
    """
    cfg = cfg or load_config()
    alternatives = alternatives if alternatives is not None else load_alternatives()
    allow = allow or (lambda u: bool(u))
    c = (country or "").upper() or (cfg.get("unknown_country_as") or "US").upper()
    ticker = market.get("ticker") or ""
    plat = market.get("platform") or "kalshi"
    alts = (alternatives.get(ticker) or {}).get("alts") or {}
    if plat not in alts and market.get("url"):
        alts = dict(alts)
        alts[plat] = {"ticker": ticker, "title": market.get("title", ""), "url": market.get("url", ""),
                      "payout": market.get("payout"), "same": True, "sim": 1.0}

    rows = []
    for book in cfg.get("books") or []:
        if book.get("enabled") is False:
            continue
        bm = book.get("markets", "both")
        if kind == "sports" and bm == "prediction":
            continue
        if kind == "prediction" and bm == "sports":
            continue
        slug = book.get("slug")
        link = book.get("link", "hub")
        url, payout, relation, alt_title = None, None, None, ""

        if kind == "sports" and book.get("kind") == "sportsbook":
            if slug != plat or own_row is None:
                continue
            url, payout, relation = own_row.get("url"), market.get("payout"), "same"
            eligible_here = bool(own_row.get("eligible")) and _book_allows_country(book, c)
        else:
            eligible_here = _book_allows_country(book, c)
            if link == "ticker":
                if slug != plat:
                    continue
                url, payout, relation = market.get("url"), market.get("payout"), "same"
            elif link == "alt":
                alt = alts.get(slug)
                if not alt:
                    continue
                url, payout = alt.get("url"), alt.get("payout")
                relation = "same" if alt.get("same") else "similar"
                alt_title = "" if alt.get("same") else (alt.get("title") or "")
            else:  # hub
                mirror = book.get("mirror")
                if mirror:
                    src = alts.get(mirror)
                    if not src:
                        continue
                    relation = "same" if (src.get("same") or plat == mirror) else "similar"
                    payout = src.get("payout")
                    alt_title = "" if relation == "same" else (src.get("title") or "")
                else:
                    relation = "browse"
                url = book.get("url")

        dest = _destination(book, url)
        if not dest or not allow(dest):
            continue
        rows.append({
            "slug": slug, "name": book.get("name", slug), "kind": book.get("kind", "exchange"),
            "pays": bool(book.get("pays")), "relation": relation, "payout": payout,
            "payout_str": _fmt_payout(payout), "alt_title": alt_title,
            "label": book.get("label", ""), "blurb": book.get("blurb", ""),
            "regulator": book.get("regulator", ""), "min_age": int(book.get("min_age") or 18),
            "rank": int(book.get("rank") or 50),
            "url": dest, "eligible": eligible_here,
        })

    def order(rs):
        # Paying books first, then James's rank (best affiliate terms first),
        # then same-market before similar. Never by payout: the visitor can
        # read the payouts, and the ticket shows the best one.
        return sorted(rs, key=lambda r: (0 if r["pays"] else 1, r["rank"], RELATION_RANK.get(r["relation"], 3)))

    eligible = order([r for r in rows if r["eligible"]])
    other = order([r for r in rows if not r["eligible"]])

    # Exception 1: the page the visitor came from names a book.
    ref = (referer_path or "").lower()
    named = None
    if "kalshi" in ref:
        named = "kalshi"
    elif "polymarket" in ref:
        named = "polymarket_us" if c == "US" else "polymarket"
    if named:
        for i, r in enumerate(eligible):
            if r["slug"] == named:
                eligible.insert(0, eligible.pop(i))
                break
    # Exception 2: no paying book carries the market -> its own book first.
    # On the sports boards the pick'em apps are the paying route even though
    # they cannot deep-link the bet, so a "browse" row counts there.
    elif not any(r["pays"] and (r["relation"] in ("same", "similar") or (kind == "sports" and r["kind"] == "pickem"))
                 for r in eligible):
        for i, r in enumerate(eligible):
            if r["slug"] == plat:
                eligible.insert(0, eligible.pop(i))
                break

    gate_age = max([r["min_age"] for r in eligible] or [18])
    if c == "US" and region and region.upper() in US_STATE_NAMES:
        place = US_STATE_NAMES[region.upper()]
    else:
        place = COUNTRY_NAMES.get(c, c)
    return {"rows": eligible, "other_rows": other, "gate_age": gate_age, "place": place,
            "region_key": "US" if c == "US" else c}


# ── Page ─────────────────────────────────────────────────────

def _e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def _row_html(r, primary, hidden=False):
    name = _e(r["name"])
    rel = r["relation"]
    if rel == "same":
        rel_text, rel_color = "same market", "#237a3f"
        if r["kind"] == "sportsbook":
            rel_text = "same bet"
    elif rel == "similar":
        rel_text, rel_color = "similar market", "#a05a00"
    else:
        rel_text, rel_color = "browse the book", "#6b5744"
    label = _e(r["label"])
    second = label or _e(r["regulator"])
    sub = " &middot; ".join(x for x in (rel_text, second if second != rel_text else "") if x)
    detail = _e(r["alt_title"]) if r["alt_title"] else _e(r["blurb"])
    if detail and r["alt_title"]:
        detail = f"&ldquo;{detail}&rdquo;"
    payout = r["payout_str"]
    if payout:
        pay_html = (f'<div style="font-size:10px;color:#6b5744;">$1 pays</div>'
                    f'<div class="pay" style="font-size:{"28" if primary else "24"}px;">{_e(payout)}</div>')
    elif rel == "browse":
        pay_html = ""  # a hub link has no price to show; pick'em pays a multiplier
    else:
        pay_html = '<div style="font-size:10px;color:#6b5744;">price</div><div class="pay pay-na">not checked</div>'
    cta = "open on" if rel != "browse" else "find it on"
    border = "2px solid #c9a227" if (primary and r["pays"]) else ("2px solid #e8642c" if primary else ("1.5px dashed #c9a98a" if rel == "browse" else "1.5px solid #e8cdb5"))
    tag = '<div class="tag">featured</div>' if (primary and r["pays"]) else ""
    btn_class = "btn primary" if primary else ("btn outline" if rel == "browse" else "btn")
    return f"""
    <div class="row{' hidden' if hidden else ''}" style="border:{border};">
      {tag}
      <div class="row-top">
        <div class="row-left">
          <div class="book">{name}</div>
          <div class="rel" style="color:{rel_color};">{sub}</div>
          <div class="detail">{detail}</div>
        </div>
        <div class="row-right">{pay_html}</div>
      </div>
      <a class="{btn_class}" href="{_e(r['url'])}" data-book="{_e(r['slug'])}" data-rel="{_e(rel)}" data-pays="{'1' if r['pays'] else '0'}" target="_blank" rel="nofollow sponsored noopener noreferrer">{cta} {name} &raquo;</a>
    </div>"""


WALL_CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #2d2319; color: #d7c8b2; font-family: 'IBM Plex Mono', 'Courier New', monospace; min-height: 100vh; display: flex; justify-content: center; -webkit-font-smoothing: antialiased; }
  a { color: #e8642c; } a:hover { color: #ff8a50; }
  .wrap { max-width: 480px; width: 100%; padding: 28px 18px 24px; display: flex; flex-direction: column; gap: 14px; }
  .wordmark { display: flex; align-items: center; justify-content: space-between; }
  .wordmark-text { font-family: 'Archivo', sans-serif; font-weight: 900; font-size: 16px; letter-spacing: -0.5px; color: #fdf6ee; text-decoration: none; }
  .wordmark-text span { color: #e8642c; }
  .label { font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #b7a894; }
  .ticket { background: #fdf6ee; border-radius: 12px; padding: 14px 16px; color: #2d2319; position: relative; overflow: hidden; }
  .notch { position: absolute; top: 58%; width: 16px; height: 16px; background: #2d2319; border-radius: 50%; }
  .notch.l { left: -8px; } .notch.r { right: -8px; }
  .ticket-label { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #b5470a; }
  .ticket-title { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 17px; line-height: 1.3; margin-top: 4px; }
  .quip { font-size: 11.5px; color: #6b5744; font-style: italic; margin-top: 3px; }
  .ticket-pay { display: flex; align-items: baseline; gap: 8px; margin-top: 10px; border-top: 1px dashed #d9c6ac; padding-top: 10px; }
  .ticket-pay .big { font-family: 'Archivo', sans-serif; font-weight: 900; font-size: 26px; letter-spacing: -0.5px; }
  .ticket-pay .small { font-size: 12px; color: #6b5744; }
  .ticket-pay .right { font-size: 10px; color: #6b5744; margin-left: auto; text-align: right; }
  h1 { font-family: 'Archivo', sans-serif; font-weight: 900; font-size: 20px; line-height: 1.15; color: #fdf6ee; margin-top: 4px; }
  .where { font-size: 11.5px; line-height: 1.6; color: #b7a894; margin-top: -8px; }
  .where strong { color: #fdf6ee; }
  .age { display: flex; gap: 12px; align-items: flex-start; font-size: 12.5px; line-height: 1.6; color: #d7c8b2; cursor: pointer; }
  .age input { width: 20px; height: 20px; accent-color: #e8642c; margin: 1px 0 0; flex-shrink: 0; cursor: pointer; }
  .age strong { color: #fdf6ee; }
  .rows { display: flex; flex-direction: column; gap: 10px; }
  .row { background: #fdf6ee; border-radius: 12px; padding: 14px; color: #2d2319; position: relative; }
  .row.hidden { display: none; }
  .tag { position: absolute; top: -9px; left: 14px; background: #c9a227; color: #2d2319; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; padding: 3px 8px; border-radius: 6px; }
  .row-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-top: 4px; }
  .row-left { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .row-right { text-align: right; flex-shrink: 0; }
  .book { font-family: 'Archivo', sans-serif; font-weight: 900; font-size: 17px; letter-spacing: -0.3px; }
  .rel { font-size: 10.5px; font-weight: 700; }
  .detail { font-size: 11px; color: #6b5744; line-height: 1.45; }
  .pay { font-family: 'Archivo', sans-serif; font-weight: 900; line-height: 1; letter-spacing: -0.5px; color: #c05a10; }
  .pay-na { font-size: 12px; color: #806b5b; font-family: 'IBM Plex Mono', monospace; font-weight: 700; margin-top: 4px; }
  .btn { display: flex; align-items: center; justify-content: center; margin-top: 12px; background: #2d2319; color: #fdf6ee; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 14px; border-radius: 10px; min-height: 44px; text-decoration: none; }
  .btn.primary { background: #e8642c; color: #fff; font-size: 15px; min-height: 48px; }
  .btn.outline { background: transparent; color: #2d2319; border: 2px solid #2d2319; }
  .btn:hover { filter: brightness(1.1); color: inherit; }
  .btn.primary:hover { color: #fff; }
  .note { font-size: 11px; line-height: 1.6; color: #b7a894; border: 1px solid #5a4e3f; border-radius: 10px; padding: 10px 12px; }
  .expander { display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: #d7c8b2; text-decoration: none; border-top: 1px solid #5a4e3f; padding-top: 12px; cursor: pointer; background: none; border-left: 0; border-right: 0; border-bottom: 0; width: 100%; font-family: inherit; text-align: left; }
  .expander span:last-child { color: #e8642c; }
  .fine { margin-top: auto; font-size: 10px; line-height: 1.7; color: #b7a894; padding-top: 12px; }
  .fine a { color: #b7a894; text-decoration: underline; }
  .empty { font-size: 12.5px; line-height: 1.6; color: #d7c8b2; }
"""


def wall_html(market, kind, info, back_path="/", consent_region_cookie=True):
    """The page. `info` is build_rows()' result."""
    rows = info["rows"]
    other = info["other_rows"]
    title = _e(market.get("title") or market.get("ticker") or "")
    quip = _e(market.get("quip") or "")
    payout_str = _fmt_payout(market.get("payout"))
    ticker = _e(market.get("ticker") or "")
    try:
        chance = f"{round(100 / float(market.get('payout') or 0))}% chance priced in" if float(market.get("payout") or 0) > 0 else ""
    except (TypeError, ValueError, ZeroDivisionError):
        chance = ""
    place = _e(info["place"])
    region_key = info["region_key"]
    gate_age = int(info["gate_age"])
    rows_html = "".join(_row_html(r, primary=(i == 0)) for i, r in enumerate(rows))
    other_html = "".join(_row_html(r, primary=False, hidden=True) for r in other)
    top_book = _e(rows[0]["slug"]) if rows else ""
    best_payout = max([r["payout_str"] for r in rows if r["payout_str"]] or [payout_str] or [""], key=lambda s: float(s.strip("$") or 0))
    ago = checked_ago()
    checked = f" Lines checked {_e(ago)}." if ago else ""
    if rows:
        heading = "Choose your market"
        where = f"showing you books licensed in <strong>{place}</strong>.{checked}"
    else:
        heading = "No book we list takes this one where you are"
        where = f"you look like you're in <strong>{place}</strong>. the books below are the ones we know of elsewhere.{checked}"
    similar_note = ""
    if any(r["relation"] == "similar" for r in rows + other):
        similar_note = '<div class="note">"similar market" means the book words the bet a little differently, so the odds or the fine print may change. check them on the book before you trade.</div>'
    pickem_note = ""
    if any(r["kind"] == "pickem" for r in rows):
        pickem_note = '<div class="note">pick\'em apps pay a fixed multiplier on a 2-pick or more, not a line, so the payout is not comparable to a sportsbook.</div>'
    expander = ""
    if other:
        other_label = f"books outside {place}"
        expander = f"""
  <button class="expander" id="expander" type="button" aria-expanded="false"><span>{_e(other_label)}</span><span>show &darr;</span></button>
  <div class="rows" id="other-rows" hidden>{other_html}</div>"""
    ticket_pay = ""
    if payout_str:
        ticket_pay = f"""
    <div class="ticket-pay"><span class="small">$1 pays up to</span><span class="big">{_e(best_payout)}</span><span class="right">{_e(chance)}</span></div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>market wall &middot; dollar bets</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;900&family=IBM+Plex+Mono:wght@400;700&display=swap" rel="stylesheet">
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('consent', 'default', {{ad_storage:'denied', ad_user_data:'denied', ad_personalization:'denied', analytics_storage:'denied', functionality_storage:'granted', security_storage:'granted', wait_for_update: 500}});
  (function(){{
    function cookie(n){{ var p=('; '+document.cookie).split('; '+n+'='); return p.length>1 ? p.pop().split(';')[0] : null; }}
    var choice = cookie('db_consent'), region = cookie('db_region');
    if (choice === 'accept' || (choice !== 'decline' && region === 'row')) gtag('consent', 'update', {{analytics_storage:'granted'}});
  }})();
  gtag('js', new Date());
  gtag('config', '{GA4_ID}', {{anonymize_ip: true, send_page_view: false}});
  gtag('event', 'wall_view', {{ticker: '{ticker}', region: '{_e(region_key)}', rows: {len(rows)}, top_book: '{top_book}', kind: '{_e(kind)}'}});
  {"gtag('event', 'affiliate_blocked', {ticker: '" + ticker + "', region: '" + _e(region_key) + "', kind: '" + _e(kind) + "'});" if not rows else ""}
</script>
<style>{WALL_CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="wordmark">
    <a href="/" class="wordmark-text">DOLLAR<span>BETS</span></a>
    <span class="label">market wall</span>
  </div>

  <div class="ticket">
    <div class="notch l"></div><div class="notch r"></div>
    <div class="ticket-label">your pick</div>
    <div class="ticket-title">{title}</div>
    {f'<div class="quip">{quip}</div>' if quip else ''}{ticket_pay}
  </div>

  <h1>{heading}</h1>
  <div class="where">{where}</div>

  <div class="rows" id="rows">{rows_html if rows else '<div class="empty">nothing we list is open to you for this pick. the board has plenty that is.</div>'}</div>
  {similar_note}
  {pickem_note}
  {expander}

  <div class="fine">you must be {gate_age} or older and in a place where the book operates; every book checks both at sign-up, and dollar bets doesn't. dollar bets is paid by some of these books when you sign up, never a cut of your bet, and never holds your money. we aren't an agent of any book. struggling with gambling? <a href="/responsible-gambling/">get help &rarr;</a> &middot; <a href="{_e(back_path)}">back to the board</a></div>
</div>
<script>
(function() {{
  var btns = Array.prototype.slice.call(document.querySelectorAll('a.btn'));
  btns.forEach(function(b) {{
    b.addEventListener('click', function() {{
      if (typeof gtag === 'function') gtag('event', 'wall_click', {{ticker: '{ticker}', book: b.getAttribute('data-book'), relation: b.getAttribute('data-rel'), pays: b.getAttribute('data-pays'), region: '{_e(region_key)}'}});
    }});
  }});
  var ex = document.getElementById('expander'), other = document.getElementById('other-rows');
  if (ex && other) ex.addEventListener('click', function() {{
    var open = other.hasAttribute('hidden');
    if (open) {{ other.removeAttribute('hidden'); other.querySelectorAll('.row.hidden').forEach(function(r) {{ r.classList.remove('hidden'); }}); }}
    else other.setAttribute('hidden', '');
    ex.setAttribute('aria-expanded', open ? 'true' : 'false');
  }});
}})();
</script>
</body>
</html>"""
