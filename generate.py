#!/usr/bin/env python3
"""
Dollar Bets — Multi-Page Static Site Generator (v3)

Reads accumulated daily board JSON files from data/boards/ and generates:
  1. /today          — daily board (the main page)
  2. /category/*     — SEO hub pages (by topic)
  3. /archetypes/*   — narrative archetype pages
  4. /recap/*        — weekly recap pages
  5. /autopsy/*      — market autopsy pages (resolved bets)
  6. /sitemap.xml    — for Google
"""

import json
import os
import re
import glob
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────

SITE_URL = "https://dollarbets.lol"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards")

# Replace with your real GA4 measurement ID after setup
GA4_ID = "G-W2V9QGFCM5"

# Kalshi referral tracking
KALSHI_REFERRAL = "e690aa11-1f29-49d1-b27f-d5e6ccf38d9f"

def kalshi_ref_url(url):
    """Append referral parameter to any Kalshi URL that doesn't already have one."""
    if not url or "kalshi.com" not in url:
        return url
    if "referral=" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}referral={KALSHI_REFERRAL}"


# ── Analytics snippet ───────────────────────────────────────

def analytics_head():
    """GA4 + outbound click tracking. Replace GA4_ID above."""
    if GA4_ID == "G-XXXXXXXXXX":
        return "<!-- GA4: replace G-XXXXXXXXXX in generate.py with your measurement ID -->"
    return f"""<!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA4_ID}');
    // Track outbound affiliate clicks
    document.addEventListener('click', function(e) {{
      var link = e.target.closest('a[href^="https://kalshi.com"]');
      if (link) {{
        gtag('event', 'click', {{
          event_category: 'outbound',
          event_label: link.href,
          transport_type: 'beacon'
        }});
      }}
    }});
  </script>"""


# ── Shared layout ───────────────────────────────────────────

SHARED_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: #fdf6ee;
      color: #2d2319;
      font-family: 'Courier New', Courier, monospace;
      font-size: 14px;
      line-height: 1.5;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    .container {
      max-width: 640px;
      margin: 0 auto;
      padding: 24px 16px;
    }

    /* === HEADER === */
    .header { margin-bottom: 16px; }

    .site-title {
      font-family: 'Georgia', 'Times New Roman', serif;
      font-size: 28px;
      font-weight: 700;
      color: #e8642c;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .site-title a {
      color: inherit;
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .site-logo {
      font-size: 26px;
      line-height: 1;
    }

    .tagline {
      font-size: 14px;
      color: #6b5744;
      margin-top: 4px;
      font-weight: 400;
      letter-spacing: 0.2px;
    }

    .date-line {
      font-size: 11px;
      color: #a08b77;
      margin-top: 4px;
      letter-spacing: 0.3px;
    }

    hr {
      border: none;
      border-top: 1.5px solid #e8cdb5;
      margin: 14px 0;
    }

    /* === NAV (two-line) === */
    .nav {
      font-size: 11px;
      color: #a08b77;
      margin-bottom: 14px;
      letter-spacing: 0.3px;
    }

    .nav-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0;
      line-height: 2.2;
    }

    .nav a, .nav .active {
      display: inline-block;
      margin-right: 14px;
      padding: 2px 0;
      border-bottom: 1.5px solid transparent;
    }

    .nav a {
      color: #6b5744;
      text-decoration: none;
      transition: all 0.15s ease;
    }

    .nav a:hover {
      color: #e8642c;
      border-bottom-color: #e8642c;
      text-decoration: none;
    }

    .nav .active {
      color: #e8642c;
      font-weight: 700;
      border-bottom-color: #e8642c;
    }

    /* === LEGEND (tier pills) === */
    .legend {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 20px;
    }

    .legend-pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 11px;
      color: #6b5744;
      background: #fef0e4;
      border: 1px solid #f0dcc8;
      border-radius: 100px;
      padding: 4px 12px 4px 8px;
      white-space: nowrap;
      letter-spacing: 0.2px;
    }

    /* === WAGER LIST === */
    .board { list-style: none; padding: 0; margin: 0; }

    .wager { margin-bottom: 10px; }

    .wager a {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      text-decoration: none;
      color: inherit;
      padding: 14px 16px;
      border-radius: 8px;
      background: #ffffff;
      border: 1.5px solid #e8cdb5;
      transition: all 0.15s ease;
    }

    /* Tier-colored borders */
    .wager.tier-green a { border-color: #4caf50; }
    .wager.tier-yellow a { border-color: #e6c731; }
    .wager.tier-orange a { border-color: #e8842c; }
    .wager.tier-red a { border-color: #e05252; }
    .wager.tier-purple a { border-color: #9c5ec7; }

    .wager a:hover {
      transform: translateY(-1px);
      box-shadow: 0 3px 8px rgba(0,0,0,0.06);
    }

    .wager.tier-green a:hover { border-color: #388e3c; box-shadow: 0 3px 8px rgba(76,175,80,0.12); }
    .wager.tier-yellow a:hover { border-color: #c9a800; box-shadow: 0 3px 8px rgba(230,199,49,0.15); }
    .wager.tier-orange a:hover { border-color: #d06a1a; box-shadow: 0 3px 8px rgba(232,132,44,0.12); }
    .wager.tier-red a:hover { border-color: #c62828; box-shadow: 0 3px 8px rgba(224,82,82,0.12); }
    .wager.tier-purple a:hover { border-color: #7b1fa2; box-shadow: 0 3px 8px rgba(156,94,199,0.12); }

    .wager a:active {
      transform: translateY(0);
      box-shadow: none;
    }

    .wager a:focus-visible {
      outline: 2px solid #e8642c;
      outline-offset: 2px;
    }

    .wager-emoji {
      font-size: 18px;
      flex-shrink: 0;
      line-height: 1.5;
      margin-top: 1px;
    }

    .wager-body {
      display: flex;
      flex-direction: column;
      gap: 4px;
      flex: 1;
      min-width: 0;
    }

    .wager-title {
      font-size: 15px;
      color: #2d2319;
      font-weight: 700;
      line-height: 1.4;
      letter-spacing: -0.3px;
    }

    .wager-payout-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 2px;
    }

    .wager-payout {
      font-size: 13px;
      font-weight: 800;
      letter-spacing: -0.3px;
      display: inline-block;
    }

    .payout-stake {
      color: #e8642c;
    }

    .payout-arrow {
      color: #a08b77;
    }

    .payout-return {
      color: #2a8c4a;
      background: #e8f5ec;
      padding: 2px 8px;
      border-radius: 4px;
      border: 1px solid #b8ddc5;
    }

    .wager-quip {
      font-size: 12.5px;
      color: #6b5744;
      font-style: italic;
      letter-spacing: 0.1px;
      line-height: 1.5;
    }

    /* === SHARE === */
    .wager-share {
      font-size: 10.5px;
      color: #e8642c;
      cursor: pointer;
      border: 1px solid #e8642c;
      background: #fff;
      font-family: 'Courier New', monospace;
      padding: 4px 10px;
      letter-spacing: 0.3px;
      border-radius: 4px;
      transition: all 0.12s ease;
      flex-shrink: 0;
      font-weight: 700;
    }

    .wager-share:hover {
      color: #fff;
      background: #e8642c;
      border-color: #e8642c;
    }

    .wager-share:active {
      background: #d45520;
      border-color: #d45520;
    }

    .wager-share.copied {
      color: #5a8a5a;
      border-color: #b0ccb0;
      background: #eef5ee;
    }

    /* === PAGE CONTENT === */
    h1, h2, h3 {
      font-family: inherit;
      line-height: inherit;
    }

    .page-title {
      font-size: 18px;
      font-weight: 700;
      color: #2d2319;
      margin-bottom: 8px;
      letter-spacing: -0.3px;
    }

    .page-intro {
      font-size: 13px;
      color: #6b5744;
      line-height: 1.7;
      margin-bottom: 18px;
    }

    .page-intro p {
      margin-bottom: 10px;
    }

    .section-head {
      font-size: 14px;
      font-weight: 700;
      color: #2d2319;
      margin: 24px 0 10px 0;
      letter-spacing: -0.2px;
    }

    .section-note {
      font-size: 12px;
      color: #a08b77;
      font-style: italic;
      margin-bottom: 12px;
    }

    .empty-note {
      font-size: 12px;
      color: #a08b77;
      font-style: italic;
      padding: 12px;
    }

    /* === RECAP BLOCKS === */
    .recap-block {
      margin-bottom: 20px;
      padding: 14px;
      background: #ffffff;
      border: 1.5px solid #e8cdb5;
      border-radius: 8px;
    }

    .recap-label {
      font-size: 11px;
      font-weight: 700;
      color: #e8642c;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }

    .recap-title {
      font-size: 14px;
      font-weight: 700;
      color: #2d2319;
    }

    .recap-detail {
      font-size: 12px;
      color: #6b5744;
      margin-top: 2px;
    }

    .recap-quip {
      font-size: 11.5px;
      color: #a08b77;
      font-style: italic;
      margin-top: 4px;
    }

    /* === AUTOPSY === */
    .autopsy-section {
      margin-bottom: 16px;
    }

    .autopsy-section h3 {
      font-size: 13px;
      font-weight: 700;
      color: #6b5744;
      margin-bottom: 4px;
    }

    .autopsy-section p {
      font-size: 13px;
      color: #6b5744;
      line-height: 1.6;
    }

    .autopsy-verdict {
      font-size: 14px;
      font-weight: 700;
      color: #2d2319;
      padding: 14px;
      background: #fef0e4;
      border: 1.5px solid #e8cdb5;
      border-radius: 8px;
      margin: 16px 0;
      font-style: italic;
    }

    /* === SIGNUP === */
    .signup {
      margin: 28px 0;
    }

    .signup iframe {
      width: 100%;
      height: 340px;
      border: none;
      background: transparent;
    }

    .signup-fallback {
      display: none;
      text-align: center;
      padding: 16px 0;
    }

    .signup-fallback a {
      color: #e8642c;
      font-weight: 700;
      text-decoration: underline;
    }

    /* === FOOTER === */
    .footer {
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1.5px solid #e8cdb5;
      font-size: 10px;
      color: #a08b77;
      line-height: 1.8;
    }

    .footer a {
      color: #6b5744;
      transition: color 0.12s;
    }

    .footer a:hover { color: #e8642c; }

    /* === MOBILE === */
    @media (max-width: 500px) {
      .container { padding: 16px 12px; }
      .site-title { font-size: 22px; }
      .site-logo { font-size: 22px; }
      .wager a { padding: 12px; }
      .wager-title { font-size: 14px; }
      .wager-payout { font-size: 12px; }
      .wager-quip { font-size: 12px; }
      .legend { overflow-x: auto; flex-wrap: nowrap; -webkit-overflow-scrolling: touch; padding-bottom: 4px; }
    }
"""

SIGNUP_HTML = """
    <div class="signup">
      <iframe src="https://subscribe-forms.beehiiv.com/78789979-d89a-4de1-adb9-cb88a40ce0dd" scrolling="no"></iframe>
      <noscript><div class="signup-fallback" style="display:block"><p><a href="https://subscribe-forms.beehiiv.com/78789979-d89a-4de1-adb9-cb88a40ce0dd" target="_blank">subscribe here</a></p></div></noscript>
    </div>
"""

SIGNUP_JS = ""


def nav_html(current=""):
    """Two-line site nav: row 1 = categories, row 2 = site links."""
    row1_links = [
        ("/weird-markets/", "black swans"),
        ("/sports-markets/", "underdogs"),
        ("/politics-markets/", "gridlock"),
        ("/financial-markets/", "ball street"),
        ("/crypto-markets/", "moonshots"),
    ]
    row2_links = [
        ("/", "today's board"),
        ("/guides/", "guides"),
        ("/about/", "about"),
    ]

    def render_link(href, label):
        if href.strip("/") == current.strip("/"):
            return f'<span class="active">{label}</span>'
        return f'<a href="{href}">{label}</a>'

    r1 = " ".join(render_link(h, l) for h, l in row1_links)
    r2 = " ".join(render_link(h, l) for h, l in row2_links)
    return f'<div class="nav"><div class="nav-row">{r1}</div><div class="nav-row">{r2}</div></div>'


def page_shell(title, description, body, canonical="", noindex=False, current_nav="", extra_head=""):
    """Wrap body content in the full HTML shell."""
    year = datetime.now().year
    noindex_tag = '<meta name="robots" content="noindex, follow">' if noindex else ""
    canonical_tag = f'<link rel="canonical" href="{SITE_URL}{canonical}">' if canonical else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  {noindex_tag}
  {canonical_tag}
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}{canonical}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💵</text></svg>">
  {analytics_head()}
  {extra_head}
  <style>{SHARED_CSS}
  </style>
</head>
<body>
  <div class="container">

    <div class="header">
      <div class="site-title"><a href="/"><span class="site-logo">💵</span> Dollar Bets</a></div>
      <div class="tagline">The world's most interesting $1 wagers. A buck says maybe.</div>
    </div>

    <hr>

{body}

    <hr>

    {nav_html(current_nav)}

{SIGNUP_HTML}

    <div class="footer">
      <p>dollar bets is an entertainment and market-discovery site. we do not operate markets, take bets, or provide betting, financial, investment, or legal advice. markets, odds, and availability vary by jurisdiction. longshots are unlikely by definition. never risk money you cannot afford to lose.</p>
      <p style="margin-top:6px">"$1 pays" = what one dollar returns if the event happens. actual returns depend on price at purchase. some links may be affiliate links — see our <a href="/affiliate-disclosure/">disclosure</a>.</p>
      <p style="margin-top:6px">this site is intended for adults only. do not use this site if you are under the legal age for gambling, trading, or participating in prediction markets in your jurisdiction.</p>
      <p style="margin-top:8px">
        <a href="/about/">about</a> &middot;
        <a href="/editorial-policy/">editorial policy</a> &middot;
        <a href="/affiliate-disclosure/">affiliate disclosure</a> &middot;
        <a href="/responsible-gambling/">responsible gambling</a> &middot;
        <a href="/availability/">jurisdiction</a> &middot;
        <a href="/privacy/">privacy</a> &middot;
        <a href="/terms/">terms</a> &middot;
        <a href="mailto:james.lamon@gmail.com">contact</a>
      </p>
      <p style="margin-top:6px">&copy; {year} dollarbets.lol</p>
    </div>

  </div>
{SIGNUP_JS}
<script>
function shareBet(e, btn) {{
  e.preventDefault();
  e.stopPropagation();
  var t = btn.dataset.title;
  var q = btn.dataset.quip;
  var p = btn.dataset.payout;
  var u = btn.dataset.url;
  var text = t + '\\n"' + q + '"\\n$1 → ' + p + '\\n' + u;
  if (navigator.share) {{
    navigator.share({{ title: 'Dollar Bets', text: text, url: u }}).catch(function(){{}});
  }} else {{
    navigator.clipboard.writeText(text).then(function() {{
      btn.textContent = '[copied]';
      btn.classList.add('copied');
      setTimeout(function() {{ btn.textContent = '[share]'; btn.classList.remove('copied'); }}, 1500);
    }}).catch(function() {{
      // fallback: select-copy via textarea
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      btn.textContent = '[copied]';
      btn.classList.add('copied');
      setTimeout(function() {{ btn.textContent = '[share]'; btn.classList.remove('copied'); }}, 1500);
    }});
  }}
}}
</script>
</body>
</html>"""


# ── Bet card renderer ───────────────────────────────────────

def tier_emoji(tier):
    return {"green": "🟩", "yellow": "🟨", "orange": "🟧",
            "red": "🟥", "purple": "🟪"}.get(tier, "⬜")


def format_payout(payout):
    if payout >= 1000:
        return f"${payout:,.0f}"
    elif payout == int(payout):
        return f"${int(payout)}"
    else:
        return f"${payout:.2f}"


def render_bet_card(m):
    """Render a single bet as an <li> element."""
    emoji = tier_emoji(m.get("tier", ""))
    tier = m.get("tier", "")
    payout_str = format_payout(m.get("payout", 0))
    title = m.get("title", "")
    quip = m.get("quip", "")
    url = kalshi_ref_url(m.get("url", "#"))

    # Escape for JS data attributes
    share_title = title.replace('"', '&quot;').replace("'", "&#39;")
    share_quip = quip.replace('"', '&quot;').replace("'", "&#39;")

    tier_class = f" tier-{tier}" if tier else ""

    return f"""      <li class="wager{tier_class}">
        <a href="{url}" target="_blank" rel="noopener">
          <span class="wager-emoji">{emoji}</span>
          <span class="wager-body">
            <span class="wager-title">{title}</span>
            <span class="wager-quip">{quip}</span>
            <span class="wager-payout-row">
              <span class="wager-payout"><span class="payout-stake">$1</span> <span class="payout-arrow">&rarr;</span> <span class="payout-return">{payout_str}</span></span>
              <button class="wager-share" onclick="shareBet(event, this)" data-title="{share_title}" data-quip="{share_quip}" data-payout="{payout_str}" data-url="{url}">[share]</button>
            </span>
          </span>
        </a>
      </li>"""


def render_bet_list(bets, empty_msg="no bets yet — check back soon."):
    """Render a list of bets as a <ul>."""
    if not bets:
        return f'    <div class="empty-note">{empty_msg}</div>'
    rows = "\n".join(render_bet_card(b) for b in bets)
    return f"""    <ul class="board">
{rows}
    </ul>"""


# ── Data loading ────────────────────────────────────────────

def load_all_boards():
    """Load all daily board JSON files, return sorted list of (date, board_data)."""
    boards = []
    pattern = os.path.join(DATA_DIR, "*.json")
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath) as f:
                data = json.load(f)
            date_str = os.path.basename(filepath).replace(".json", "")
            boards.append((date_str, data))
        except (json.JSONDecodeError, IOError) as e:
            print(f"[generate] Skipping {filepath}: {e}")
    return boards


def flatten_all_bets(boards):
    """Flatten all boards into a single list of bets with date metadata."""
    all_bets = []
    for date_str, data in boards:
        for bet in data.get("board", []):
            bet_copy = dict(bet)
            bet_copy["date_featured"] = date_str
            all_bets.append(bet_copy)
    return all_bets


# ── Category mapping ────────────────────────────────────────

# Maps Kalshi categories to our SEO categories
CATEGORY_MAP = {
    # Kalshi category (lowercased) → our slug
    "climate and weather": "weird-markets",
    "weather": "weird-markets",
    "entertainment": "weird-markets",
    "culture": "weird-markets",
    "science and technology": "weird-markets",
    "science": "weird-markets",
    "tech": "weird-markets",
    "sports": "sports-markets",
    "politics": "politics-markets",
    "political": "politics-markets",
    "world": "politics-markets",
    "crypto": "crypto-markets",
    "cryptocurrency": "crypto-markets",
    "financial": "financial-markets",
    "economics": "financial-markets",
    "finance": "financial-markets",
    "fed": "financial-markets",
    "treasury": "financial-markets",
}

# Secondary category detection via keywords in title
KEYWORD_CATEGORIES = {
    "sports-markets": [
        "nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball",
        "baseball", "hockey", "premier league", "champions league",
        "playoff", "championship", "tournament", "world cup",
        "super bowl", "world series", "stanley cup", "draft", "sweep",
        "olympics", "tennis", "golf", "f1", "formula",
    ],
    "politics-markets": [
        "trump", "biden", "election", "congress", "senate", "governor",
        "president", "vote", "democrat", "republican", "political",
        "legislation", "supreme court", "impeach", "cabinet",
    ],
    "crypto-markets": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
        "dogecoin", "solana", "defi",
    ],
    "financial-markets": [
        "s&p", "s&p 500", "sp500", "nasdaq", "dow jones", "dow ",
        "fed ", "federal reserve", "interest rate", "rate cut", "rate hike",
        "inflation", "cpi", "gdp", "recession", "treasury", "yield",
        "stock market", "wall street", "ipo", "earnings",
        "oil price", "gold price", "commodities",
        "unemployment", "jobs report", "nonfarm", "housing",
        "debt ceiling", "tariff",
    ],
}


def categorize_bet(bet):
    """Return our category slug for a bet."""
    kalshi_cat = (bet.get("category") or "").lower().strip()
    title_lower = (bet.get("title") or "").lower()

    # Keyword override takes priority
    for slug, keywords in KEYWORD_CATEGORIES.items():
        if any(kw in title_lower for kw in keywords):
            return slug

    # Fall back to Kalshi category mapping
    return CATEGORY_MAP.get(kalshi_cat, "weird-markets")


# ── Archetype mapping ───────────────────────────────────────

ARCHETYPE_KEYWORDS = {
    "weather-freakout": [
        "snow", "rain", "hurricane", "tornado", "earthquake", "volcano",
        "temperature", "heat", "cold", "storm", "flood", "wildfire",
        "weather", "climate", "drought",
    ],
    "crypto-moonshot": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "dogecoin",
        "solana", "blockchain", "defi", "nft",
    ],
    "sports-collapse": [
        "sweep", "upset", "eliminated", "fired", "benched", "injured",
        "losing streak", "worst", "collapse", "choke",
    ],
    "political-chaos": [
        "impeach", "resign", "indicted", "scandal", "investigation",
        "subpoena", "shutdown", "crisis", "emergency", "executive order",
    ],
    "celebrity-wildcard": [
        "taylor swift", "kanye", "drake", "elon", "musk", "kardashian",
        "beyonce", "rihanna", "bieber", "album", "tour", "announce",
        "oscar", "grammy", "emmy", "award",
    ],
    "the-surely-not": [],  # Catch-all for extreme longshots (payout > 50x)
}


def get_archetypes(bet):
    """Return list of archetype slugs a bet matches."""
    title_lower = (bet.get("title") or "").lower()
    payout = bet.get("payout", 0)
    matches = []

    for slug, keywords in ARCHETYPE_KEYWORDS.items():
        if slug == "the-surely-not":
            continue
        if any(kw in title_lower for kw in keywords):
            matches.append(slug)

    # "The Surely Not" = extreme longshots
    if payout and payout >= 50:
        matches.append("the-surely-not")

    return matches if matches else ["the-surely-not"]


# ── Page content definitions ────────────────────────────────

CATEGORIES = {
    "weird-markets": {
        "title": "weird prediction markets — dollar bets",
        "h1": "weird prediction markets",
        "description": "The internet's strangest prediction markets, translated into what a $1 bet could pay. Weather, pop culture, science, tech — the black swans.",
        "intro": """<p>These are the markets that make you stop scrolling. Snow in April. Celebrity announcements. AI breakthroughs. Earthquake odds. The kind of stuff that sounds fake but has actual money behind it.</p>
<p>Dollar Bets tracks the most entertaining prediction markets every day and frames each one by what a single dollar could pay out. Below are the strangest markets we've featured — the black swans, the outliers, and the bets that shouldn't exist but do.</p>""",
    },
    "sports-markets": {
        "title": "sports prediction markets — dollar bets",
        "h1": "sports prediction markets",
        "description": "Sports prediction markets where $1 could pay big. Playoff sweeps, championship longshots, and underdog bets translated into dollar payouts.",
        "intro": """<p>Sports prediction markets are where drama meets math. A playoff sweep priced at 45 cents. A championship longshot at 3 cents. The kinds of bets your fantasy league group chat argues about.</p>
<p>Unlike traditional sportsbooks, prediction markets let you trade in and out as odds shift — which means the stories are just as interesting as the outcomes. Here are the underdog markets Dollar Bets has featured — the longshots, the upsets-in-waiting, and the bets that made the group chat go quiet.</p>""",
    },
    "politics-markets": {
        "title": "political prediction markets — dollar bets",
        "h1": "political prediction markets",
        "description": "Political prediction markets — elections, policy, and gridlock. Real money odds on what happens next in Washington and beyond, framed as $1 payouts.",
        "intro": """<p>Political prediction markets are where public opinion gets a price tag. Elections, legislation, Supreme Court decisions, international crises — if it can be resolved with a yes or no, someone's trading on it.</p>
<p>These markets often move faster than polls and pundits. When news breaks, the price moves in minutes. Dollar Bets tracks the political markets that are actually interesting to normal people — not the wonky stuff, but the gridlock and chaos that shows up in your group chat.</p>""",
    },
    "financial-markets": {
        "title": "financial prediction markets — dollar bets",
        "h1": "financial prediction markets",
        "description": "Financial prediction markets — the Fed, interest rates, recessions, stock market milestones, and economic indicators. What does $1 pay when Wall Street gets weird?",
        "intro": """<p>These are the markets where the suits meet the spreadsheet degenerates. Will the Fed cut rates? Will the S&P hit a round number? Will a recession technically happen before anyone admits it?</p>
<p>Financial prediction markets on Kalshi turn the stuff your econ professor made boring into actual wagers with deadlines. Dollar Bets tracks the ones that matter to people who check their portfolio more than their email — framed by what a single dollar could pay out.</p>""",
    },
    "crypto-markets": {
        "title": "crypto prediction markets — dollar bets",
        "h1": "crypto prediction markets",
        "description": "Crypto prediction markets — Bitcoin milestones, ETH price targets, and blockchain moonshots. What does $1 pay if the chart cooperates?",
        "intro": """<p>Crypto prediction markets are the most volatile corner of an already volatile world. Bitcoin above $100k by Friday? Ethereum flipping something? A memecoin doing something inexplicable?</p>
<p>The beauty of crypto markets on Kalshi is that they have real expiration dates. No vague "to the moon" — just a yes-or-no question with a deadline and a price. Here are the moonshots Dollar Bets has featured — the round-number milestones, the leveraged bets, and the charts that had a plan.</p>""",
    },
}

ARCHETYPES = {
    "weather-freakout": {
        "title": "the weather freakout bet — dollar bets",
        "h1": "the weather freakout bet",
        "emoji": "🌪️",
        "description": "When weather prediction markets panic — snow in April, earthquakes, hurricanes, and temperature records. The markets where Mother Nature sets the odds.",
        "intro": """<p>Every few weeks, a weather market goes from background noise to front-page drama. Snow in a city that shouldn't have snow. A hurricane track that shifts toward somewhere expensive. A temperature record that sounds made up.</p>
<p>Weather freakout bets are some of the most entertaining on Kalshi because nature doesn't read the forecast. The odds can swing wildly in hours, and resolution is binary — it either snowed or it didn't. No spin, no interpretation, just the weather station.</p>
<p>These are the bets where you check your weather app and your portfolio at the same time.</p>""",
    },
    "crypto-moonshot": {
        "title": "the crypto moonshot bet — dollar bets",
        "h1": "the crypto moonshot bet",
        "emoji": "🚀",
        "description": "Bitcoin milestones, ETH targets, and memecoin madness. Crypto prediction markets where $1 chases the chart.",
        "intro": """<p>The crypto moonshot is prediction markets at their most degenerate and most entertaining. Will Bitcoin hit a round number by a specific date? Will Ethereum do something nobody can quite explain? Will a token that started as a joke outperform the S&P?</p>
<p>What makes these bets special is that the underlying asset is already volatile — and then you're betting on a specific threshold by a specific date. It's leverage on leverage. The payout swings are violent and the charts tell stories.</p>
<p>Dollar Bets tracks the crypto markets that are entertaining, not just profitable. The ones you screenshot for the group chat.</p>""",
    },
    "sports-collapse": {
        "title": "the sports collapse bet — dollar bets",
        "h1": "the sports collapse bet",
        "emoji": "💀",
        "description": "Playoff sweeps, coaching firings, losing streaks, and underdog collapses. Sports prediction markets for when everything falls apart.",
        "intro": """<p>The sports collapse bet is the one you place when you sense the vibes are off. A team up 3-0 in a series that suddenly looks nervous. A coach whose press conferences are getting weird. A franchise that traded for someone who hasn't practiced.</p>
<p>These markets are fascinating because sports collapses are always obvious in hindsight and invisible in real time. The odds tell you what the crowd thinks — and the crowd is often wrong right up until it's catastrophically right.</p>
<p>These are the bets for the people who watch the postgame interviews more closely than the game.</p>""",
    },
    "political-chaos": {
        "title": "the political chaos bet — dollar bets",
        "h1": "the political chaos bet",
        "emoji": "🏛️",
        "description": "Resignations, investigations, shutdowns, and surprises. Political prediction markets for when Washington gets weird.",
        "intro": """<p>Political chaos bets are the prediction market equivalent of watching cable news with a price tag. Someone resigns unexpectedly. An investigation gets announced. A vote that was supposed to be routine turns into a spectacle.</p>
<p>These markets move on headlines — sometimes before the headline is even confirmed. A rumor hits, the price swings 30 cents, and then everyone waits. That's the drama.</p>
<p>Dollar Bets tracks the political chaos markets that cut through the noise — the ones where something is actually happening, not just being talked about.</p>""",
    },
    "celebrity-wildcard": {
        "title": "the celebrity wildcard bet — dollar bets",
        "h1": "the celebrity wildcard bet",
        "emoji": "⭐",
        "description": "Album drops, tour announcements, award shows, and Elon tweets. Celebrity prediction markets where fame meets probability.",
        "intro": """<p>The celebrity wildcard is the bet that makes prediction markets feel like entertainment, not finance. Will Taylor Swift announce something? Will Elon tweet 50 times in a day? Will Drake respond to a diss track? Will an awards show produce an actual surprise?</p>
<p>These markets are priced on a mix of historical behavior, insider speculation, and pure vibes. They're the markets most likely to end up on social media and least likely to be discussed by serious people. That's the point.</p>
<p>If you've ever had a strong opinion about a celebrity's next move, there might be a market for that.</p>""",
    },
    "the-surely-not": {
        "title": "the \"surely not\" bet — dollar bets",
        "h1": "the \"surely not\" bet",
        "emoji": "🟪",
        "description": "Extreme longshot prediction markets where $1 could pay $50, $100, or more. The bets that sound impossible until they aren't.",
        "intro": """<p>The "surely not" bet is the extreme longshot — the market priced so low that the payout on a dollar is absurd. $50. $100. $500. The kind of number that makes you do the math twice and then think about it for the rest of the day.</p>
<p>Most of these won't hit. That's the point. But prediction markets occasionally misprice things — and when a "surely not" suddenly starts moving, it becomes the most interesting market on the board.</p>
<p>These are the bets filed under "entertainment expenses." A dollar and a dream, priced by the crowd.</p>""",
    },
}


# ── Page generators ─────────────────────────────────────────

def generate_daily_board(boards):
    """Generate the main /index.html — today's board."""
    if not boards:
        return

    latest_date, latest_data = boards[-1]
    board = latest_data.get("board", [])

    try:
        dt = datetime.fromisoformat(latest_date)
        date_str = dt.strftime("%B %d, %Y")
    except ValueError:
        date_str = latest_date

    legend = """    <div class="legend">
      <span class="legend-pill">🟩 respectable</span>
      <span class="legend-pill">🟨 alive</span>
      <span class="legend-pill">🟧 heater</span>
      <span class="legend-pill">🟥 filthy</span>
      <span class="legend-pill">🟪 generational</span>
    </div>
"""
    date_line = f'    <div class="date-line" style="margin-bottom:14px">{date_str}</div>\n'

    trust_strip = """
    <div style="margin:20px 0;padding:12px;border-top:1.5px solid #e8cdb5;font-size:10px;color:#a08b77;line-height:1.6">
      tiny stakes. huge maybes. dollar bets is entertainment-first market discovery — not betting advice, not financial advice, and not a guarantee that any market is available where you live. odds and markets change. <a href="/responsible-gambling/" style="color:#6b5744">gamble responsibly</a>. <a href="/availability/" style="color:#6b5744">check availability</a>.
    </div>
"""

    body = date_line + legend + render_bet_list(board) + trust_strip

    html = page_shell(
        title="dollar bets — what does $1 pay?",
        description="A buck says maybe. Daily board of the internet's most entertaining wagers.",
        body=body,
        canonical="/",
        current_nav="/",
    )

    write_page("index.html", html)


def generate_category_pages(all_bets):
    """Generate category SEO hub pages."""
    # Bucket bets by category
    cat_bets = defaultdict(list)
    for bet in all_bets:
        slug = categorize_bet(bet)
        cat_bets[slug].append(bet)

    for slug, config in CATEGORIES.items():
        bets = cat_bets.get(slug, [])

        # Deduplicate by title, keep most recent
        seen_titles = {}
        for b in bets:
            t = b.get("title", "")
            if t not in seen_titles or b.get("date_featured", "") > seen_titles[t].get("date_featured", ""):
                seen_titles[t] = b
        unique_bets = sorted(seen_titles.values(), key=lambda x: x.get("payout", 0), reverse=True)

        # Show up to 15 examples
        display_bets = unique_bets[:15]

        # Count for section header
        count_note = f"{len(unique_bets)} markets featured" if unique_bets else ""

        body = f"""    <h1 class="page-title">{config['h1']}</h1>
    <div class="page-intro">
      {config['intro']}
    </div>

    <h2 class="section-head">featured markets</h2>
    <div class="section-note">{count_note}</div>

{render_bet_list(display_bets, "no markets featured in this category yet — check back soon.")}
"""

        html = page_shell(
            title=config["title"],
            description=config["description"],
            body=body,
            canonical=f"/{slug}/",
            current_nav=f"/{slug}/",
        )

        write_page(f"{slug}/index.html", html)


def generate_archetype_pages(all_bets):
    """Generate bet archetype narrative pages."""
    # Bucket bets by archetype
    arch_bets = defaultdict(list)
    for bet in all_bets:
        for arch_slug in get_archetypes(bet):
            arch_bets[arch_slug].append(bet)

    for slug, config in ARCHETYPES.items():
        bets = arch_bets.get(slug, [])

        # Deduplicate by title
        seen = {}
        for b in bets:
            t = b.get("title", "")
            if t not in seen or b.get("date_featured", "") > seen[t].get("date_featured", ""):
                seen[t] = b
        unique_bets = sorted(seen.values(), key=lambda x: x.get("payout", 0), reverse=True)
        display_bets = unique_bets[:12]

        body = f"""    <h1 class="page-title">{config.get('emoji', '')} {config['h1']}</h1>
    <div class="page-intro">
      {config['intro']}
    </div>

    <h2 class="section-head">examples from the board</h2>
    <div class="section-note">{len(unique_bets)} markets matched this archetype</div>

{render_bet_list(display_bets, "no examples yet — this archetype is waiting for its moment.")}
"""

        html = page_shell(
            title=config["title"],
            description=config["description"],
            body=body,
            canonical=f"/archetypes/{slug}/",
        )

        write_page(f"archetypes/{slug}/index.html", html)


def generate_weekly_recaps(boards):
    """Generate weekly recap pages from accumulated boards."""
    if len(boards) < 2:
        return  # Need at least a couple days of data

    # Group boards by ISO week
    weeks = defaultdict(list)
    for date_str, data in boards:
        try:
            dt = datetime.fromisoformat(date_str)
            # Week starts Monday
            week_start = dt - timedelta(days=dt.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
            weeks[week_key].append((date_str, data))
        except ValueError:
            continue

    for week_start_str, week_boards in sorted(weeks.items()):
        # Flatten all bets for this week
        week_bets = []
        for date_str, data in week_boards:
            for bet in data.get("board", []):
                bet_copy = dict(bet)
                bet_copy["date_featured"] = date_str
                week_bets.append(bet_copy)

        if not week_bets:
            continue

        # Compute week end
        try:
            ws = datetime.fromisoformat(week_start_str)
            we = ws + timedelta(days=6)
            week_label = f"{ws.strftime('%B %d')} – {we.strftime('%B %d, %Y')}"
            week_slug = f"week-of-{week_start_str}"
        except ValueError:
            continue

        # Find notable bets for recap sections
        sorted_by_payout = sorted(week_bets, key=lambda x: x.get("payout", 0), reverse=True)
        highest_payout = sorted_by_payout[0] if sorted_by_payout else None
        lowest_payout = sorted(week_bets, key=lambda x: x.get("payout", 0))[0] if week_bets else None

        # Most "interesting" = middle payout range (10-50x sweet spot)
        sweet_spot = [b for b in week_bets if 10 <= b.get("payout", 0) <= 50]
        best_sweet = sweet_spot[0] if sweet_spot else None

        # Build recap blocks
        blocks = []

        if highest_payout:
            blocks.append(recap_block(
                "biggest longshot",
                highest_payout,
                f"$1 could have paid {format_payout(highest_payout.get('payout', 0))}"
            ))

        if best_sweet:
            blocks.append(recap_block(
                "most respectable longshot",
                best_sweet,
                f"$1 pays {format_payout(best_sweet.get('payout', 0))} — dramatic but credible"
            ))

        if lowest_payout and lowest_payout != highest_payout:
            blocks.append(recap_block(
                "lowest payout on the board",
                lowest_payout,
                f"$1 pays {format_payout(lowest_payout.get('payout', 0))} — barely worth bragging about"
            ))

        # Deduplicated full list
        seen = set()
        unique_week = []
        for b in week_bets:
            t = b.get("title", "")
            if t not in seen:
                seen.add(t)
                unique_week.append(b)

        blocks_html = "\n".join(blocks)

        body = f"""    <h1 class="page-title">the week in dollar bets</h1>
    <div class="date-line" style="margin-bottom:14px">{week_label}</div>
    <div class="page-intro">
      <p>{len(unique_week)} markets featured across {len(week_boards)} days. Here's what stood out.</p>
    </div>

{blocks_html}

    <h2 class="section-head">all markets this week</h2>

{render_bet_list(unique_week[:15])}
"""

        html = page_shell(
            title=f"the week in dollar bets — {week_label}",
            description=f"Weekly recap: {len(unique_week)} prediction markets featured on Dollar Bets, {week_label}. Biggest longshots, best odds, weirdest bets.",
            body=body,
            canonical=f"/recap/{week_slug}/",
        )

        write_page(f"recap/{week_slug}/index.html", html)


def recap_block(label, bet, detail):
    """Render a recap highlight block."""
    return f"""    <div class="recap-block">
      <div class="recap-label">{label}</div>
      <div class="recap-title">{tier_emoji(bet.get('tier', ''))} {bet.get('title', '')}</div>
      <div class="recap-detail">{detail}</div>
      <div class="recap-quip">{bet.get('quip', '')}</div>
    </div>"""


def generate_market_autopsies(all_bets):
    """Generate market autopsy pages for resolved high-interest bets.

    For now, generates autopsy-style pages for bets with extreme payouts
    (content-afterlife candidates). In production, this would check
    market_status == 'resolved' from the data model.
    """
    # Select autopsy candidates: high payout (50x+) bets are most interesting
    candidates = [b for b in all_bets if b.get("payout", 0) >= 20]

    # Deduplicate
    seen = {}
    for b in candidates:
        t = b.get("title", "")
        if t not in seen:
            seen[t] = b
    candidates = list(seen.values())

    for bet in candidates[:10]:  # Cap at 10 autopsies for now
        title = bet.get("title", "")
        slug = slugify(title)
        if not slug:
            continue

        payout = bet.get("payout", 0)
        quip = bet.get("quip", "")
        category = bet.get("category", "unknown")
        date_featured = bet.get("date_featured", "unknown")
        url = kalshi_ref_url(bet.get("url", "#"))

        body = f"""    <h1 class="page-title">market autopsy: {title}</h1>
    <div class="date-line" style="margin-bottom:14px">featured {date_featured} · {category}</div>

    <div class="autopsy-verdict">
      "{quip}"
    </div>

    <div class="autopsy-section">
      <h3>what this market was</h3>
      <p>{title}. Priced on Kalshi with a $1 payout of {format_payout(payout)} — the market gave this roughly a {round(100/payout, 1)}% chance of happening.</p>
    </div>

    <div class="autopsy-section">
      <h3>why it was on the board</h3>
      <p>At {format_payout(payout)} on a dollar, this was a {tier_label(bet.get('tier', ''))} tier bet. The kind of market that makes you open a new tab and start reading. Filed under {category.lower()} on Kalshi, it caught Dollar Bets' attention for the payout drama and the cultural hook.</p>
    </div>

    <div class="autopsy-section">
      <h3>the bet type</h3>
      <p>This is a classic {_archetype_name(bet)} — the kind of market that shows up on prediction platforms whenever the news cycle gets interesting. The structure is simple: yes or no, by a deadline, with real money on the line.</p>
    </div>

    <div class="autopsy-section">
      <h3>see this market</h3>
      <p><a href="{url}" target="_blank" rel="noopener" style="color:#333">view on kalshi →</a></p>
    </div>
"""

        html = page_shell(
            title=f"market autopsy: {title} — dollar bets",
            description=f"Dollar Bets market autopsy: {title}. What it was, why it was interesting, and what $1 could have paid ({format_payout(payout)}).",
            body=body,
            canonical=f"/autopsy/{slug}/",
        )

        write_page(f"autopsy/{slug}/index.html", html)


def tier_label(tier):
    return {"green": "respectable", "yellow": "alive", "orange": "heater",
            "red": "filthy", "purple": "generational"}.get(tier, "unknown")


def _archetype_name(bet):
    archetypes = get_archetypes(bet)
    names = {
        "weather-freakout": "Weather Freakout",
        "crypto-moonshot": "Crypto Moonshot",
        "sports-collapse": "Sports Collapse",
        "political-chaos": "Political Chaos",
        "celebrity-wildcard": "Celebrity Wildcard",
        "the-surely-not": '"Surely Not"',
    }
    if archetypes:
        return names.get(archetypes[0], "longshot bet")
    return "longshot bet"


# ── About page ──────────────────────────────────────────────

def generate_about_page():
    """Generate the /about/ page."""
    body = """    <h1 class="page-title">what is dollar bets?</h1>
    <div class="page-intro">
      <p>A daily board of weird, funny, and culturally relevant prediction markets, translated into what a $1 bet could pay.</p>

      <p>Every day we scan thousands of markets on Kalshi — a US-regulated prediction market exchange — and pick roughly ten that are actually interesting to a normal human being. Then we frame each one by what a single dollar could pay out. "$1 pays $20" is more fun than "priced at 5 cents with an implied probability of 5%." One of these sentences makes you lean in. The other makes you close the tab.</p>

      <p style="font-weight:700; margin-top:16px">what's a prediction market?</p>

      <p>A prediction market is a place where people bet real money on whether something will happen. Will Bitcoin hit $100k by Friday? Will it snow in Phoenix? Will a senator resign? You buy a contract for a few cents. If the event happens, it pays out $1. If it doesn't, you lose what you paid.</p>

      <p>The price of a contract tells you what the crowd thinks. A contract at 5 cents means the market thinks there's roughly a 5% chance. When news breaks, prices move — sometimes in minutes. Prediction markets are often faster than polls, pundits, and cable news.</p>

      <p style="font-weight:700; margin-top:16px">what does "$1 pays $20" mean?</p>

      <p>It means the contract is priced around 5 cents. If you buy one contract at 5 cents and the event happens, you get back $1 — a 20x return. The higher the payout, the less likely the market thinks it is. We color-code these: 🟩 respectable, 🟨 alive, 🟧 heater, 🟥 filthy, 🟪 generational.</p>

      <p style="font-weight:700; margin-top:16px">what dollar bets is not</p>

      <p>We are not a sportsbook. We are not a bookmaker. We are not a tout sheet and we are not here to tell you what to bet on. Dollar Bets is a discovery and editorial layer — we curate markets the way a good newspaper curates headlines, with taste, timing, and a mild disregard for conventional financial advice. Every listing links directly to the market on Kalshi. You must be 18+ to trade.</p>

      <p>The markets we feature are real. They have real money behind them, real deadlines, and real outcomes. Most of the longshots will not pay off. That's what makes them longshots. The point is not to win — the point is that these markets exist at all, and they're frequently absurd, occasionally profound, and almost always more entertaining than whatever else you were going to do with a dollar.</p>

      <p>Dollar Bets is built for the person who reads the news and thinks "I wonder if there's a market for that." There usually is. We find it for you.</p>

      <p>The board updates daily. The email is free. The bets are a dollar. The rest is up to the universe.</p>

      <p style="font-weight:700; margin-top:16px">who runs this?</p>

      <p><a href="https://linkedin.com/in/jameslamon" target="_blank" style="color:#333">James Lamon</a> — founder and editor. James spent over a decade building content businesses at scale. As EVP Content & Operations at <a href="https://footballco.com" target="_blank" style="color:#333">Footballco</a>, he led the teams behind GOAL and World Soccer — overseeing editorial, video, social, branded content, affiliate, and events across global offices. Before that, he was Head of Content Europe at <a href="https://buzzfeed.com" target="_blank" style="color:#333">BuzzFeed</a>, where he launched and ran a portfolio of brands in entertainment, food, and travel across both the editorial and commercial sides of the business.</p>

      <p>He started his career as a creative strategist and creative director, working with brands including Sky, Diageo, Google, Samsung, BMW, and Porsche. He graduated summa cum laude from the University of Texas at Austin. Dollar Bets is what happens when someone who spent a career turning content into revenue discovers prediction markets and can't look away.</p>

      <p style="margin-top:12px"><a href="/editorial-policy/" style="color:#666">editorial policy</a> · <a href="/affiliate-disclosure/" style="color:#666">affiliate disclosure</a> · <a href="/responsible-gambling/" style="color:#666">responsible gambling</a></p>
    </div>
"""

    html = page_shell(
        title="what is dollar bets? — about",
        description="Dollar Bets is a daily board of weird, funny, and culturally relevant prediction markets, translated into what a $1 bet could pay. Not a sportsbook — a discovery layer.",
        body=body,
        canonical="/about/",
        current_nav="/about/",
    )

    write_page("about/index.html", html)


# ── Sitemap ─────────────────────────────────────────────────

def generate_sitemap(pages):
    """Generate sitemap.xml from list of (path, priority) tuples."""
    today = datetime.now().strftime("%Y-%m-%d")
    urls = []
    for path, priority in pages:
        urls.append(f"""  <url>
    <loc>{SITE_URL}{path}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{"daily" if priority >= 0.8 else "weekly"}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    write_page("sitemap.xml", xml)


def generate_robots_txt():
    """Generate robots.txt with sitemap reference."""
    txt = f"""User-agent: *
Allow: /

# AI crawlers welcome
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: GoogleOther
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    write_page("robots.txt", txt)


# ── Archetype index page ───────────────────────────────────

def generate_archetype_index():
    """Generate /archetypes/ index page linking to all archetypes."""
    links = []
    for slug, config in ARCHETYPES.items():
        emoji = config.get("emoji", "")
        links.append(f"""      <li class="wager">
        <a href="/archetypes/{slug}/" style="display:block; padding:12px;">
          <span class="wager-emoji">{emoji}</span>
          <span class="wager-body">
            <span class="wager-title">{config['h1']}</span>
            <span class="wager-quip">{config['description'][:80]}...</span>
          </span>
        </a>
      </li>""")

    body = f"""    <h1 class="page-title">bet archetypes</h1>
    <div class="page-intro">
      <p>Prediction markets produce the same kinds of bets over and over — weather panics, crypto moonshots, political chaos, celebrity wildcards. We call these archetypes. Each one has its own personality, its own rhythm, and its own kind of drama.</p>
    </div>

    <ul class="board">
{chr(10).join(links)}
    </ul>
"""

    html = page_shell(
        title="bet archetypes — dollar bets",
        description="Recurring prediction market narratives: weather freakouts, crypto moonshots, sports collapses, and more. The same kinds of bets keep showing up — here's why.",
        body=body,
        canonical="/archetypes/",
    )

    write_page("archetypes/index.html", html)


# ── Recap index page ───────────────────────────────────────

def generate_recap_index(boards):
    """Generate /recap/ index page linking to all weekly recaps."""
    weeks = defaultdict(list)
    for date_str, data in boards:
        try:
            dt = datetime.fromisoformat(date_str)
            week_start = dt - timedelta(days=dt.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
            weeks[week_key].append((date_str, data))
        except ValueError:
            continue

    if not weeks:
        return

    links = []
    for week_start_str in sorted(weeks.keys(), reverse=True):
        week_boards = weeks[week_start_str]
        ws = datetime.fromisoformat(week_start_str)
        we = ws + timedelta(days=6)
        week_label = f"{ws.strftime('%B %d')} – {we.strftime('%B %d, %Y')}"
        week_slug = f"week-of-{week_start_str}"

        # Count unique bets
        titles = set()
        for _, data in week_boards:
            for b in data.get("board", []):
                titles.add(b.get("title", ""))

        links.append(f"""      <li class="wager">
        <a href="/recap/{week_slug}/" style="display:block; padding:12px;">
          <span class="wager-emoji">📰</span>
          <span class="wager-body">
            <span class="wager-title">{week_label}</span>
            <span class="wager-quip">{len(titles)} markets · {len(week_boards)} days</span>
          </span>
        </a>
      </li>""")

    body = f"""    <h1 class="page-title">weekly recaps</h1>
    <div class="page-intro">
      <p>Every week, Dollar Bets looks back at the most interesting prediction markets from the daily board — the biggest longshots, the weirdest bets, and the markets that made people pay attention.</p>
    </div>

    <ul class="board">
{chr(10).join(links)}
    </ul>
"""

    html = page_shell(
        title="weekly recaps — dollar bets",
        description="Weekly recaps from Dollar Bets — the most interesting prediction markets, biggest longshots, and weirdest bets from each week.",
        body=body,
        canonical="/recap/",
    )

    write_page("recap/index.html", html)


# ── Helpers ─────────────────────────────────────────────────

def slugify(text):
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60].strip('-')


def write_page(rel_path, content):
    """Write an HTML file to the output directory."""
    full_path = os.path.join(OUTPUT_DIR, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)
    print(f"[generate] Wrote {rel_path}")


# ── Main ────────────────────────────────────────────────────

def main():
    print("[generate] Loading board data...")
    boards = load_all_boards()
    print(f"[generate] Found {len(boards)} daily boards")

    all_bets = flatten_all_bets(boards)
    print(f"[generate] {len(all_bets)} total bet appearances")

    # Ensure output dir exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Daily board
    print("[generate] Building daily board...")
    generate_daily_board(boards)

    # 2. Category/SEO hub pages
    print("[generate] Building category pages...")
    generate_category_pages(all_bets)

    # 3. Archetype pages
    print("[generate] Building archetype pages...")
    generate_archetype_index()
    generate_archetype_pages(all_bets)

    # 4. Weekly recaps
    print("[generate] Building weekly recaps...")
    generate_recap_index(boards)
    generate_weekly_recaps(boards)

    # 5. Market autopsies
    print("[generate] Building market autopsies...")
    generate_market_autopsies(all_bets)

    # 6. About page
    print("[generate] Building about page...")
    generate_about_page()

    # 7. Sitemap + robots.txt
    print("[generate] Building sitemap...")
    sitemap_pages = [
        ("/", 1.0),
        ("/about/", 0.7),
    ]
    for slug in CATEGORIES:
        sitemap_pages.append((f"/{slug}/", 0.8))
    sitemap_pages.append(("/archetypes/", 0.7))
    for slug in ARCHETYPES:
        sitemap_pages.append((f"/archetypes/{slug}/", 0.6))
    sitemap_pages.append(("/recap/", 0.7))
    # Add individual recap pages
    for date_str, _ in boards:
        try:
            dt = datetime.fromisoformat(date_str)
            week_start = dt - timedelta(days=dt.weekday())
            week_slug = f"week-of-{week_start.strftime('%Y-%m-%d')}"
            entry = (f"/recap/{week_slug}/", 0.5)
            if entry not in sitemap_pages:
                sitemap_pages.append(entry)
        except ValueError:
            pass
    # Add autopsy pages
    autopsy_candidates = [b for b in all_bets if b.get("payout", 0) >= 20]
    seen = set()
    for b in autopsy_candidates:
        t = b.get("title", "")
        if t not in seen:
            seen.add(t)
            s = slugify(t)
            if s:
                sitemap_pages.append((f"/autopsy/{s}/", 0.5))

    # Add content pages (from generate_content.py) to sitemap
    content_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
    if os.path.isdir(content_dir):
        import glob as globmod
        for filepath in globmod.glob(os.path.join(content_dir, "**", "*.json"), recursive=True):
            try:
                with open(filepath) as f:
                    cdata = json.load(f)
                canonical = cdata.get("seo", {}).get("canonical", "")
                if canonical:
                    priority = 0.7 if cdata.get("format") == "historical_story" else 0.8
                    entry = (canonical, priority)
                    if entry not in sitemap_pages:
                        sitemap_pages.append(entry)
            except (json.JSONDecodeError, IOError):
                pass
        # Hall of Filth index
        hof_stories = [1 for fp in globmod.glob(os.path.join(content_dir, "hall-of-filth", "*.json"))
                       if json.load(open(fp)).get("format") == "historical_story"]
        if hof_stories:
            entry = ("/hall-of-filth/", 0.8)
            if entry not in sitemap_pages:
                sitemap_pages.append(entry)

    generate_sitemap(sitemap_pages)
    generate_robots_txt()

    # Post-process: ensure ALL Kalshi URLs in output HTML have referral parameter
    print("[generate] Post-processing: adding referral parameter to all Kalshi URLs...")
    import re as _re
    _ref_pattern = _re.compile(r'https://kalshi\.com(/[^"&\s]*?)(?=")')
    def _add_referral(match):
        url = match.group(0)
        if "referral=" in url:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}referral={KALSHI_REFERRAL}"
    _kalshi_href_pattern = _re.compile(r'(href="|data-url=")https://kalshi\.com([^"]*)"')
    def _fix_href(match):
        prefix = match.group(1)
        url = f"https://kalshi.com{match.group(2)}"
        if "referral=" in url:
            return f'{prefix}{url}"'
        sep = "&" if "?" in url else "?"
        return f'{prefix}{url}{sep}referral={KALSHI_REFERRAL}"'
    _fixed_count = 0
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for fname in files:
            if not fname.endswith(".html"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "r") as f:
                content = f.read()
            new_content = _kalshi_href_pattern.sub(_fix_href, content)
            if new_content != content:
                with open(fpath, "w") as f:
                    f.write(new_content)
                _fixed_count += 1
    print(f"[generate] Referral URLs: patched {_fixed_count} files")

    print(f"[generate] Done. {len(sitemap_pages)} pages in sitemap.")


if __name__ == "__main__":
    main()
