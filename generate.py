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

import html
import json
import os
import re
import glob
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def _e(s):
    """HTML-escape a value for safe interpolation into element text/attributes.

    Board data (title, quip, category, etc.) comes from external APIs
    (Kalshi, Polymarket, The Odds API), AI-generated text (Claude quips),
    and CMS editor input. None of those sources is trusted to be HTML-safe,
    so every interpolation of dynamic text must be escaped to prevent
    stored XSS in the rendered static site.
    """
    return html.escape("" if s is None else str(s), quote=True)


def _json_for_script(value):
    """json.dumps a value for safe embedding in a <script> block.

    json.dumps does not escape the forward slash in </script>, so a market
    title containing the literal string </script> would close the script tag
    and let attacker-controlled content escape into HTML. Replace </ with
    <\\/ (a JSON-valid escape) to prevent that.
    """
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

# ── Config ──────────────────────────────────────────────────

SITE_URL = "https://www.dollarbets.lol"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards")

# Replace with your real GA4 measurement ID after setup
GA4_ID = "G-W2V9QGFCM5"

# Link resolution — uses /go/ redirects for all market links
# The /go/ serverless function handles affiliate routing based on user location
def market_link(market_ticker, from_slug=None):
    """Build a /go/ redirect link for a market.

    `from_slug` (optional) is the URL slug of the originating board
    (e.g. "underdogs", "ocho", "the-lineup"). It's appended as a
    ?from= query param so the redirect handler can return users to
    the right board if a wager isn't available in their state.
    """
    if not market_ticker:
        return "#"
    if from_slug:
        return f"/go/{market_ticker}/?from={from_slug}"
    return f"/go/{market_ticker}/"


# ── Analytics snippet ───────────────────────────────────────

def analytics_head():
    """GA4 + Faurya analytics + outbound click tracking."""
    snippets = []

    # Faurya analytics
    snippets.append("""<!-- Faurya Analytics -->
  <script async defer src="https://www.faurya.com/js/script.js" data-domain="dollarbets.lol" data-website-id="cmosekmvz000xl204a7bhm4cm"></script>""")

    # GA4 (kept alongside Faurya)
    if GA4_ID != "G-XXXXXXXXXX":
        snippets.append(f"""<!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    // Google Consent Mode v2 defaults — deny-by-default for analytics so the
    // baseline is GDPR / UK GDPR / ePrivacy compliant. The on-page consent
    // banner (see consent_banner_html) prompts the user to opt in; the choice
    // is stored in the db_consent cookie and restored on subsequent visits.
    // Ad_* stays denied permanently since the site serves no ads.
    gtag('consent', 'default', {{
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      analytics_storage: 'denied',
      functionality_storage: 'granted',
      security_storage: 'granted'
    }});
    // Restore prior choice synchronously so granted users don't lose a hit.
    (function() {{
      var m = document.cookie.match(/(?:^|;\\s*)db_consent=(\\w+)/);
      if (m && m[1] === 'accept') {{
        gtag('consent', 'update', {{ analytics_storage: 'granted' }});
      }}
    }})();
    gtag('js', new Date());
    gtag('config', '{GA4_ID}', {{ anonymize_ip: true }});
    // Track all outbound affiliate clicks with rich dimensions
    document.addEventListener('click', function(e) {{
      var link = e.target.closest('a[href^="/go/"]');
      if (link) {{
        gtag('event', 'affiliate_click', {{
          platform: link.dataset.platform || 'unknown',
          tier: link.dataset.tier || 'unknown',
          payout: link.dataset.payout || '0',
          ticker: link.dataset.ticker || '',
          link_url: link.href,
          page_path: window.location.pathname,
          transport_type: 'beacon'
        }});
      }}
    }});
  </script>""")

    return "\n".join(snippets)


def consent_banner_html():
    """Cookie consent banner shown on first visit (no db_consent cookie).

    Stored choice is a single cookie value: 'accept' or 'decline'. Accept calls
    gtag consent update to grant analytics_storage; decline leaves it denied.
    Banner is hidden after a choice; the choice persists for 1 year.

    Universal banner (shown to all visitors, not geo-restricted) — over-compliant
    for US visitors but cheap and defensible. EU/UK visitors are the legally
    binding case; deny-by-default + this banner satisfies that path.
    """
    return """
    <div id="db-consent" role="dialog" aria-live="polite" aria-label="Cookie consent" hidden>
      <div class="db-consent-inner">
        <p class="db-consent-text">
          dollar bets uses one analytics cookie (google analytics) to count visits and see which pages people read. no ads, no tracking pixels, no third-party data sharing. see <a href="/privacy/">privacy</a>.
        </p>
        <div class="db-consent-actions">
          <button type="button" id="db-consent-accept">accept</button>
          <button type="button" id="db-consent-decline">decline</button>
        </div>
      </div>
    </div>
    <style>
      #db-consent {
        position: fixed; left: 0; right: 0; bottom: 0;
        background: #faf7f3; border-top: 2px solid #e8642c;
        z-index: 9000; padding: 14px 16px;
        font-family: 'Courier New', Courier, monospace;
        box-shadow: 0 -4px 12px rgba(45,35,25,0.08);
      }
      #db-consent[hidden] { display: none; }
      .db-consent-inner {
        max-width: 640px; margin: 0 auto;
        display: flex; flex-wrap: wrap; gap: 12px;
        align-items: center; justify-content: space-between;
      }
      .db-consent-text {
        font-size: 12px; line-height: 1.55; color: #2d2319;
        margin: 0; flex: 1 1 320px;
      }
      .db-consent-text a { color: #b5470a; text-decoration: underline; }
      .db-consent-actions { display: flex; gap: 8px; flex-shrink: 0; }
      .db-consent-actions button {
        font-family: 'Courier New', Courier, monospace;
        font-size: 12px; font-weight: 700;
        padding: 8px 14px; cursor: pointer;
        text-transform: lowercase;
        border: 2px solid #e8642c; color: #e8642c;
        background: transparent;
      }
      .db-consent-actions button:hover { background: #e8642c; color: #fdf6ee; }
      .db-consent-actions #db-consent-decline {
        border-color: #a08b77; color: #a08b77;
      }
      .db-consent-actions #db-consent-decline:hover {
        background: #a08b77; color: #fdf6ee;
      }
      @media (max-width: 520px) {
        .db-consent-inner { flex-direction: column; align-items: stretch; }
        .db-consent-actions { justify-content: flex-end; }
      }
    </style>
    <script>
    (function() {
      var banner = document.getElementById('db-consent');
      if (!banner) return;
      var m = document.cookie.match(/(?:^|;\\s*)db_consent=(\\w+)/);
      if (m && (m[1] === 'accept' || m[1] === 'decline')) return;
      banner.hidden = false;
      function setChoice(choice) {
        document.cookie = 'db_consent=' + choice + ';max-age=31536000;path=/;samesite=lax;secure';
        banner.hidden = true;
        if (typeof gtag === 'function') {
          gtag('consent', 'update', {
            analytics_storage: choice === 'accept' ? 'granted' : 'denied'
          });
        }
      }
      var acc = document.getElementById('db-consent-accept');
      var dec = document.getElementById('db-consent-decline');
      if (acc) acc.addEventListener('click', function() { setChoice('accept'); });
      if (dec) dec.addEventListener('click', function() { setChoice('decline'); });
    })();
    </script>
"""


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
      font-family: 'Courier New', Courier, monospace;
      font-size: 26px;
      font-weight: 700;
      color: #e8642c;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
      /* margin reset — same rule applies whether site-title renders as div (default)
         or as h1 (on the homepage), so the user-agent h1 default doesn't shift layout */
      margin: 0;
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
      color: #806b5b;
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
      /* V4 typography: UPPERCASE + bold + brand orange + red active.
         Drudge-style punch within the old-internet aesthetic. */
      font-size: 11.5px;
      color: #b5470a;
      margin-bottom: 14px;
      letter-spacing: 0.6px;
      text-transform: uppercase;
      font-weight: 700;
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
      padding: 8px 0;
      border-bottom: 1.5px solid transparent;
    }

    .nav a {
      color: #b5470a;
      text-decoration: none;
      transition: all 0.15s ease;
    }

    .nav a:hover {
      color: #c4341c;
      border-bottom-color: #c4341c;
      text-decoration: none;
    }

    .nav .active {
      color: #c4341c;
      border-bottom-color: #c4341c;
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
      text-decoration: none;
      transition: all 0.15s ease;
    }

    a.legend-pill:hover {
      color: #b5470a;
      border-color: #e8642c;
      text-decoration: none;
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
    .wager.tier-orange a { border-color: #d06a1a; }
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

    .platform-logo {
      display: inline-flex;
      align-items: center;
      flex-shrink: 0;
    }

    .platform-logo img, .platform-logo svg {
      height: 14px;
      width: auto;
      opacity: 0.55;
      transition: opacity 0.15s ease;
    }

    .wager:hover .platform-logo img,
    .wager:hover .platform-logo svg {
      opacity: 0.85;
    }

    .wager-payout {
      font-size: 13px;
      font-weight: 800;
      letter-spacing: -0.3px;
      display: inline-block;
      flex-shrink: 0;
      white-space: nowrap;
    }

    .payout-stake {
      color: #b5470a;
    }

    .payout-arrow {
      color: #806b5b;
    }

    .payout-return {
      color: #237a3f;
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

    /* === OPEN PLATFORM PILL === */
    /* Both pills share the same fixed height + inline-flex centering
       so they render at exactly the same rendered box regardless of
       inner content (button user-agent line-height vs span line-height
       used to drift them apart by ~4px). */
    .open-platform {
      height: 26px;
      box-sizing: border-box;
      font-size: 10.5px;
      color: #237a3f;
      cursor: pointer;
      border: 1px solid #237a3f;
      background: #fff;
      font-family: 'Courier New', monospace;
      padding: 0 12px;
      line-height: 1;
      letter-spacing: 0.3px;
      border-radius: 4px;
      transition: all 0.12s ease;
      font-weight: 700;
      text-decoration: none;
      margin-left: auto;
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    /* Heavier » arrow visual via scale() — scale doesn't affect the
       element's layout box, so the pill's rendered height stays equal
       to .share-btn even with a visually larger glyph. */
    .open-platform .cta-arrow {
      font-weight: 900;
      line-height: 1;
      display: inline-block;
      transform: scale(1.4);
      transform-origin: center;
      margin: 0 2px;
    }

    .wager:hover .open-platform {
      color: #fff;
      background: #237a3f;
      border-color: #237a3f;
    }

    /* === SHARE (popup) === */
    .share-wrap {
      position: relative;
      flex-shrink: 0;
    }

    .share-btn {
      /* Identical height + flex centering as .open-platform — pills must
         visually match. line-height:1 + explicit height kills any button
         user-agent line-height that used to make the share pill ~4px taller. */
      height: 26px;
      box-sizing: border-box;
      font-size: 10.5px;
      color: #b5470a;
      cursor: pointer;
      border: 1px solid #e8642c;
      background: #fff;
      font-family: 'Courier New', monospace;
      padding: 0 12px;
      line-height: 1;
      letter-spacing: 0.3px;
      border-radius: 4px;
      transition: all 0.12s ease;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
    }

    .share-btn:hover {
      color: #fff;
      background: #e8642c;
      border-color: #e8642c;
    }

    .share-menu {
      display: none;
      position: absolute;
      right: 0;
      bottom: calc(100% + 6px);
      background: #fff;
      border: 1.5px solid #e8cdb5;
      border-radius: 4px;
      box-shadow: 0 3px 10px rgba(0,0,0,0.1);
      z-index: 100;
      min-width: 130px;
      font-family: 'Courier New', monospace;
      font-size: 11px;
    }

    .share-menu.open { display: block; }

    .share-menu button {
      display: block;
      width: 100%;
      text-align: left;
      padding: 7px 12px;
      border: none;
      background: none;
      cursor: pointer;
      font-family: 'Courier New', monospace;
      font-size: 11px;
      color: #2d2319;
      letter-spacing: 0.2px;
      white-space: nowrap;
    }

    .share-menu button:hover {
      background: #fdf0e4;
      color: #b5470a;
    }

    .share-menu button + button {
      border-top: 1px solid #f0e0d0;
    }

    .share-menu .sm-reddit:hover { color: #ff4500; }
    .share-menu .sm-x:hover { color: #000; }
    .share-menu .sm-fb:hover { color: #1877f2; }
    .share-menu .sm-copy:hover { color: #b5470a; }
    .share-menu .sm-copy.copied { color: #5a8a5a; }

    /* === BOARD PROMO NAV UNIT === */
    .board-promo {
      margin: 24px 0;
      padding: 16px 0;
      border-top: 1.5px solid #e8cdb5;
      border-bottom: 1.5px solid #e8cdb5;
    }

    .board-promo-header {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1.2px;
      color: #b5470a;
      margin-bottom: 12px;
    }

    .board-promo .board {
      margin-bottom: 12px;
    }

    .board-promo-cta {
      display: block;
      text-align: center;
      font-size: 12px;
      font-weight: 700;
      color: #b5470a;
      text-decoration: none;
      padding: 8px 0;
      letter-spacing: 0.3px;
      border: 1.5px solid #e8cdb5;
      border-radius: 6px;
      background: #fff;
      transition: all 0.15s ease;
    }

    .board-promo-cta:hover {
      background: #e8642c;
      color: #fff;
      border-color: #e8642c;
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
      font-size: 14px;
      color: #3d2e1f;
      line-height: 1.7;
      margin-bottom: 18px;
    }

    .page-intro p {
      margin-bottom: 10px;
    }

    .section-head {
      font-size: 15px;
      font-weight: 700;
      color: #2d2319;
      margin: 24px 0 10px 0;
      letter-spacing: -0.2px;
    }

    .section-note {
      font-size: 12px;
      color: #806b5b;
      font-style: italic;
      margin-bottom: 12px;
    }

    .empty-note {
      font-size: 12px;
      color: #806b5b;
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
      color: #b5470a;
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
      color: #806b5b;
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
      color: #b5470a;
      font-weight: 700;
      text-decoration: underline;
    }

    /* === FOOTER === */
    .footer {
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1.5px solid #e8cdb5;
      font-size: 10px;
      color: #806b5b;
      line-height: 1.8;
    }

    .footer a {
      color: #6b5744;
      transition: color 0.12s;
    }

    .footer a:hover { color: #b5470a; }

    /* === BOARD NAV BOTTOM (repeated browsing nav) === */
    .board-nav-bottom {
      text-align: center;
      font-size: 11px;
      color: #806b5b;
      padding: 14px 0;
      line-height: 2.2;
      letter-spacing: 0.3px;
    }

    .board-nav-bottom a {
      color: #6b5744;
      text-decoration: none;
      transition: color 0.12s;
    }

    .board-nav-bottom a:hover { color: #b5470a; }

    /* === FOOTER INFO NAV (quiet secondary links) === */
    .footer-info-nav {
      text-align: center;
      font-size: 10px;
      color: #806b5b;
      padding: 10px 0 16px;
      line-height: 2.2;
    }

    .footer-info-nav a {
      color: #806b5b;
      text-decoration: none;
      transition: color 0.12s;
    }

    .footer-info-nav a:hover { color: #b5470a; }

    /* === FILTHY LITTLE LONGSHOT === */
    .wager.longshot-pick a {
      border-width: 2.5px;
    }

    .longshot-label {
      font-size: 10px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      font-weight: 700;
      margin-bottom: 4px;
    }

    .longshot-pick .wager-quip {
      font-weight: 700;
    }

    /* Always-visible site disclosure strip — yellow notice box that sits
       between the tier legend and the first bet on every board page.
       Geo-compliance is handled at the /go/ interstitial (api/go.py), not
       on the board pages themselves. */
    .disclosure-strip {
      background: #fef9e7; border: 1px solid #d4c479; color: #5a4e2f;
      padding: 10px 14px; font-size: 11px; margin: 0 0 18px;
      font-family: 'Courier New', monospace; text-transform: lowercase;
      line-height: 1.6; border-radius: 4px;
    }

    /* === MOBILE === */
    @media (max-width: 500px) {
      .container { padding: 16px 12px; }
      .site-title { font-size: 22px; }
      .site-logo { font-size: 22px; }
      .wager a { padding: 12px; }
      .wager-title { font-size: 14px; }
      .wager-payout { font-size: 12px; }
      .wager-quip { font-size: 12px; }
      .legend {
        overflow-x: auto;
        flex-wrap: nowrap;
        -webkit-overflow-scrolling: touch;
        padding-bottom: 4px;
        /* Fade right edge when content overflows, hinting horizontal scroll */
        -webkit-mask-image: linear-gradient(to right, black calc(100% - 28px), transparent);
        mask-image: linear-gradient(to right, black calc(100% - 28px), transparent);
      }
      /* Let payout-row wrap on narrow viewports so [share] never overflows the card.
         When wrap happens (e.g. long platform labels at 320–393px), share drops
         to a second line, right-aligned. Payout stays inline with open-platform. */
      .wager-payout-row {
        flex-wrap: wrap;
        row-gap: 6px;
      }
      .share-wrap {
        margin-left: auto;
      }
    }
"""

SIGNUP_HTML = """
    <div class="signup">
      <iframe src="https://subscribe-forms.beehiiv.com/78789979-d89a-4de1-adb9-cb88a40ce0dd" scrolling="no" title="Email newsletter signup form"></iframe>
      <noscript><div class="signup-fallback" style="display:block"><p><a href="https://subscribe-forms.beehiiv.com/78789979-d89a-4de1-adb9-cb88a40ce0dd" target="_blank">subscribe here</a></p></div></noscript>
    </div>
"""

# Always-visible site disclosure shown between the tier legend and the
# first bet on every board page. Plain-English trust signal — visible to
# every visitor regardless of region. Geo-restriction warnings happen at
# the /go/ interstitial.
DISCLOSURE_STRIP_HTML = """    <div class="disclosure-strip">
      we earn affiliate commissions when you sign up to kalshi or polymarket through our links. we don't take a cut of any bet, hold any of your money, or get paid more if you lose.
    </div>
"""

SIGNUP_JS = ""


BOARD_NAV_LINKS = [
    ("/", "today's board"),
    ("/the-lineup/", "the lineup"),
    ("/weird-markets/", "black swans"),
    ("/politics-markets/", "gridlock"),
    ("/financial-markets/", "ball street"),
    ("/crypto-markets/", "moonshots"),
    ("/underdogs/", "underdogs"),
    ("/the-ocho/", "the ocho"),
    ("/chalk/", "chalk"),
    ("/combo-meal/", "combo meal"),
]


def nav_html(current=""):
    """Primary board nav — browsing destinations only.

    Single flex row that wraps naturally based on container width. The
    earlier hand-coded split (first 6 in row 1, last 4 in row 2) created
    a half-empty line 2 on mobile because the second container forced a
    fresh row break. Letting the items flow as one list packs line 2
    fully before any spill into line 3.
    """
    def render_link(href, label):
        norm_href = href if href == "/" else href.strip("/")
        norm_cur = current if current == "/" else current.strip("/")
        if norm_cur and norm_href == norm_cur:
            return f'<span class="active">{label}</span>'
        return f'<a href="{href}">{label}</a>'

    items = " ".join(render_link(h, l) for h, l in BOARD_NAV_LINKS)
    return f'<div class="nav"><div class="nav-row">{items}</div></div>'


def board_nav_bottom(current=""):
    """Repeated board nav after main content — 'keep browsing' feel."""
    links = []
    for href, label in BOARD_NAV_LINKS:
        norm_href = href if href == "/" else href.strip("/")
        norm_cur = current if current == "/" else current.strip("/")
        if norm_cur and norm_href == norm_cur:
            links.append(label)
        else:
            links.append(f'<a href="{href}">{label}</a>')
    return f'    <div class="board-nav-bottom">{" &middot; ".join(links)}</div>\n'


def footer_info_nav():
    """Quiet footer nav for secondary/info pages."""
    links = [
        ("/guides/", "guides"),
        ("/about/", "about"),
        ("/affiliate-disclosure/", "affiliate disclosure"),
        ("/responsible-gambling/", "responsible gambling"),
        ("/privacy/", "privacy"),
        ("/terms/", "terms"),
        ("/sitemap/", "sitemap"),
        ("mailto:hello@dollarbets.lol", "contact"),
    ]
    items = " &middot;\n        ".join(f'<a href="{h}">{l}</a>' for h, l in links)
    return f'    <div class="footer-info-nav">\n        {items}\n    </div>\n'


def page_shell(title, description, body, canonical="", noindex=False, current_nav="", extra_head=""):
    """Wrap body content in the full HTML shell.

    `title` and `description` are treated as raw strings (callers pass plain
    text, not pre-escaped HTML); page_shell HTML-escapes them on the way out
    so untrusted market titles cannot break the <title> tag or meta content
    attributes. `body` is assumed to be already-safe HTML produced by other
    renderers (which do their own escaping at interpolation points).
    """
    year = datetime.now().year
    safe_title = _e(title)
    safe_desc = _e(description)
    safe_canonical = _e(canonical, ) if canonical else ""
    noindex_tag = '<meta name="robots" content="noindex, follow">' if noindex else ""
    canonical_tag = f'<link rel="canonical" href="{SITE_URL}{safe_canonical}">' if canonical else ""

    # Homepage is the only page that needs Dollar Bets as its semantic h1.
    # Every other page has its own <h1 class="page-title">; on those pages
    # the site-title stays a <div> to avoid duplicate h1s.
    is_homepage = canonical == "/"
    title_tag = "h1" if is_homepage else "div"
    site_title_html = (
        f'<{title_tag} class="site-title">'
        f'<a href="/"><span class="site-logo">💵</span> Dollar Bets</a>'
        f'</{title_tag}>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <meta name="description" content="{safe_desc}">
  {noindex_tag}
  {canonical_tag}
  <meta property="og:title" content="{safe_title}">
  <meta property="og:description" content="{safe_desc}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}{safe_canonical}">
  <meta property="og:site_name" content="Dollar Bets">
  <meta property="og:image" content="{SITE_URL}/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:type" content="image/png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{safe_title}">
  <meta name="twitter:description" content="{safe_desc}">
  <meta name="twitter:image" content="{SITE_URL}/og-image.png">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  {analytics_head()}
  {extra_head}
  <style>{SHARED_CSS}
  </style>
</head>
<body>
  <div class="container">

    <header class="header">
      {site_title_html}
      <div class="tagline">The world's most interesting $1 wagers. A buck says maybe.</div>
    </header>

    <hr>

    <nav aria-label="Main navigation">{nav_html(current_nav)}</nav>

    <main id="content">
{body}
    </main>

    <hr>

{board_nav_bottom(current_nav)}

{SIGNUP_HTML}

    <div style="font-size:10px;color:#7a6e5f;text-align:center;padding:6px 0;line-height:1.6">links open third-party markets. prices and availability change.</div>

{footer_info_nav()}

    <footer class="footer">
      <p>dollar bets is an editorial discovery site, not a broker, exchange, bookmaker, financial adviser, or gambling operator. we do not operate markets, take bets, or provide betting, financial, investment, or legal advice. market availability varies by jurisdiction. users are responsible for complying with local laws and platform eligibility rules. longshots are unlikely by definition. never risk money you cannot afford to lose.</p>
      <p style="margin-top:6px">"$1 pays" = what one dollar returns if the event happens. actual returns depend on price at purchase. some links may be affiliate links — see our <a href="/affiliate-disclosure/">disclosure</a>.</p>
      <p style="margin-top:6px">this site is intended for adults only. do not use this site if you are under the legal age for gambling, trading, or participating in prediction markets in your jurisdiction.</p>
      <p style="margin-top:6px">&copy; {year} dollarbets.lol</p>
    </footer>

  </div>
{consent_banner_html()}
{SIGNUP_JS}
<script>
// close any open share menu when clicking elsewhere
document.addEventListener('click', function() {{
  document.querySelectorAll('.share-menu.open').forEach(function(m) {{ m.classList.remove('open'); }});
}});

function toggleShare(e, btn) {{
  e.preventDefault();
  e.stopPropagation();
  // close other open menus first
  document.querySelectorAll('.share-menu.open').forEach(function(m) {{ m.classList.remove('open'); }});
  var menu = btn.parentElement.querySelector('.share-menu');
  menu.classList.toggle('open');
}}

function shareTo(e, platform, btn) {{
  e.preventDefault();
  e.stopPropagation();
  var wrap = btn.closest('.share-wrap');
  var t = wrap.dataset.title;
  var q = wrap.dataset.quip;
  var p = wrap.dataset.payout;
  var ticker = wrap.dataset.ticker;
  var shareUrl = ticker ? 'https://dollarbets.lol/share/' + encodeURIComponent(ticker) + '/' : 'https://dollarbets.lol';
  var menu = wrap.querySelector('.share-menu');

  if (platform === 'reddit') {{
    var redditTitle = t + ' — $1 pays ' + p + ' | Dollar Bets';
    window.open('https://www.reddit.com/submit?url=' + encodeURIComponent(shareUrl) + '&title=' + encodeURIComponent(redditTitle), '_blank', 'noopener');
  }} else if (platform === 'x') {{
    var tweet = t + '\\n"' + q + '"\\n$1 → ' + p + '\\n' + shareUrl;
    window.open('https://x.com/intent/tweet?text=' + encodeURIComponent(tweet), '_blank', 'noopener');
  }} else if (platform === 'fb') {{
    window.open('https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(shareUrl) + '&quote=' + encodeURIComponent(t + ' — $1 pays ' + p), '_blank', 'noopener');
  }} else if (platform === 'copy') {{
    var text = t + '\\n"' + q + '"\\n$1 → ' + p + '\\n' + shareUrl;
    navigator.clipboard.writeText(text).then(function() {{
      btn.textContent = 'copied!';
      btn.classList.add('copied');
      setTimeout(function() {{ btn.textContent = 'copy link'; btn.classList.remove('copied'); }}, 1500);
    }}).catch(function() {{
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      btn.textContent = 'copied!';
      btn.classList.add('copied');
      setTimeout(function() {{ btn.textContent = 'copy link'; btn.classList.remove('copied'); }}, 1500);
    }});
    return; // don't close menu on copy
  }}
  menu.classList.remove('open');
}}

// Geo compliance is handled on the /go/ interstitial (see api/go.py).
// The homepage no longer runs region-aware JS — every visitor sees the
// same board and the same disclosure strip; restriction warnings appear
// only at click-through time, against the specific partner being opened.
</script>
</body>
</html>"""


# ── Bet card renderer ───────────────────────────────────────

# Inline SVG logos for platforms (small, monochrome, ~14px tall)
PLATFORM_LOGOS = {
    "kalshi": '<svg class="logo-kalshi" viewBox="0 0 60 16" xmlns="http://www.w3.org/2000/svg" fill="#2d2319"><text x="0" y="13" font-family="Courier New,Courier,monospace" font-size="14" font-weight="700" letter-spacing="-0.5">Kalshi</text></svg>',
    "polymarket": '<svg class="logo-polymarket" viewBox="0 0 90 16" xmlns="http://www.w3.org/2000/svg" fill="#2d2319"><text x="0" y="13" font-family="Courier New,Courier,monospace" font-size="14" font-weight="700" letter-spacing="-0.5">Polymarket</text></svg>',
    "fanduel": '<svg class="logo-sportsbook" viewBox="0 0 70 16" xmlns="http://www.w3.org/2000/svg" fill="#2d2319"><text x="0" y="13" font-family="Courier New,Courier,monospace" font-size="14" font-weight="700" letter-spacing="-0.5">FanDuel</text></svg>',
    "draftkings": '<svg class="logo-sportsbook" viewBox="0 0 90 16" xmlns="http://www.w3.org/2000/svg" fill="#2d2319"><text x="0" y="13" font-family="Courier New,Courier,monospace" font-size="14" font-weight="700" letter-spacing="-0.5">DraftKings</text></svg>',
    "betmgm": '<svg class="logo-sportsbook" viewBox="0 0 65 16" xmlns="http://www.w3.org/2000/svg" fill="#2d2319"><text x="0" y="13" font-family="Courier New,Courier,monospace" font-size="14" font-weight="700" letter-spacing="-0.5">BetMGM</text></svg>',
    "betrivers": '<svg class="logo-sportsbook" viewBox="0 0 80 16" xmlns="http://www.w3.org/2000/svg" fill="#2d2319"><text x="0" y="13" font-family="Courier New,Courier,monospace" font-size="14" font-weight="700" letter-spacing="-0.5">BetRivers</text></svg>',
}


def platform_logo_html(platform):
    """Return the inline SVG logo for a platform, wrapped in a span."""
    svg = PLATFORM_LOGOS.get(platform, PLATFORM_LOGOS.get("kalshi", ""))
    if svg:
        return f'<span class="platform-logo">{svg}</span>'
    return ""


def tier_emoji(tier):
    return {"green": "🟩", "yellow": "🟨", "orange": "🟧",
            "red": "🟥", "purple": "🟪"}.get(tier, "⬜")


def legend_html(board=None):
    """Clickable tier legend — links to /tier/{name}/ pages.

    Renders one pill per tier as 'emoji + tier name'. The board argument
    is accepted for backward compatibility with existing call sites but
    no longer drives a per-tier count (per-day counts were removed to
    keep the legend acting as a clean key/filter rather than a stat bar).
    Tier name → board key:
        respectable → green
        alive → yellow
        heater → orange
        filthy → red
        generational → purple
    """
    pills = [
        ("🟩", "respectable"),
        ("🟨", "alive"),
        ("🟧", "heater"),
        ("🟥", "filthy"),
        ("🟪", "generational"),
    ]

    def render_pill(emoji, name):
        return f'<a href="/tier/{name}/" class="legend-pill">{emoji} {name}</a>'

    items = "\n      ".join(render_pill(e, n) for e, n in pills)
    return f'    <div class="legend">\n      {items}\n    </div>\n'


def select_filthy_longshot(board):
    """Select today's filthy little longshot — the weirdest, most absurd market.

    Selection criteria (in priority order):
    1. Favor markets scored as high-entertainment by the scanner (entertainment_score)
    2. Favor markets NOT in routine categories (crypto price targets, generic elections,
       hottest month on record, routine sports outrights)
    3. Favor higher-tier markets (orange/red/purple over green/yellow) but don't
       just pick the highest payout — a weird orange beats a boring purple
    4. If the scanner flagged a market as 'longshot_pick', prefer it

    Returns the index of the chosen bet in the board list, or None if board is empty.
    """
    if not board:
        return None

    BORING_PATTERNS = [
        r"bitcoin.*\$\d", r"btc.*\$\d", r"eth.*\$\d", r"ethereum.*\$\d",
        r"hottest.*month", r"warmest.*month", r"temperature.*record",
        r"who will win the 20\d\d", r"will win the presidency",
        r"next president", r"price.*above.*\$", r"price.*below.*\$",
    ]

    TIER_SCORE = {"green": 0, "yellow": 1, "orange": 2, "red": 3, "purple": 4}

    best_idx = 0
    best_score = -1

    for i, m in enumerate(board):
        title_lower = m.get("title", "").lower()
        score = 0

        # Scanner entertainment score (0-10 range typically)
        score += m.get("entertainment_score", 5) * 2

        # Tier bonus — higher tiers are more dramatic
        score += TIER_SCORE.get(m.get("tier", ""), 0) * 3

        # Penalty for routine/boring markets
        is_boring = any(re.search(pat, title_lower) for pat in BORING_PATTERNS)
        if is_boring:
            score -= 15

        # Bonus if scanner flagged it
        if m.get("longshot_pick"):
            score += 10

        # Bonus for categories that tend to be weird
        cat = m.get("category", "").lower()
        if cat in ("science", "entertainment", "culture", "world", "weather"):
            score += 3

        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def format_payout(payout):
    if payout >= 1000:
        return f"${payout:,.0f}"
    elif payout == int(payout):
        return f"${int(payout)}"
    else:
        return f"${payout:.2f}"


TIER_COLORS = {
    "green": "#4caf50",
    "yellow": "#e6c731",
    "orange": "#d06a1a",
    "red": "#e05252",
    "purple": "#9c5ec7",
}

PLATFORM_DISPLAY_NAMES = {
    "kalshi": "Kalshi",
    "polymarket": "Polymarket",
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "betrivers": "BetRivers",
}


def render_bet_card(m, is_longshot_pick=False):
    """Render a single bet as an <li> element."""
    emoji = tier_emoji(m.get("tier", ""))
    tier = m.get("tier", "")
    payout_str = format_payout(m.get("payout", 0))
    raw_title = m.get("title", "")
    raw_quip = m.get("quip", "")
    title = _e(raw_title)
    quip = _e(raw_quip)
    # Use market ticker for /go/ link (fallback to old url field for backward compatibility)
    ticker = m.get("ticker", "")
    if ticker:
        url = market_link(ticker)
    else:
        # Fallback: extract ticker from old-format URL
        old_url = m.get("url", "")
        if old_url and "kalshi.com" in old_url:
            ticker = old_url.split("/")[-1].split("?")[0]
            url = market_link(ticker) if ticker else "#"
        else:
            url = "#"

    # data-* attributes — html.escape with quote=True is correct for attribute values
    share_title = _e(raw_title)
    share_quip = _e(raw_quip)

    # Platform name for pill button
    platform = m.get("platform", "kalshi")
    platform_name = PLATFORM_DISPLAY_NAMES.get(platform, platform.title())

    tier_class = f" tier-{tier}" if tier else ""
    longshot_class = " longshot-pick" if is_longshot_pick else ""
    tier_color = TIER_COLORS.get(tier, "#806b5b")

    # Longshot label (only on homepage pick)
    longshot_label = ""
    if is_longshot_pick:
        longshot_label = f'<span class="longshot-label" style="color:{tier_color}">today\'s filthy little longshot &#127919;</span>'

    return f"""      <li class="wager{tier_class}{longshot_class}">
        <a href="{url}" target="_blank" rel="noopener nofollow" data-platform="{platform}" data-tier="{tier}" data-payout="{m.get('payout', 0)}" data-ticker="{ticker}">
          <span class="wager-emoji">{emoji}</span>
          <span class="wager-body">
            {longshot_label}
            <span class="wager-title">{title}</span>
            <span class="wager-quip">{quip}</span>
            <span class="wager-payout-row">
              <span class="wager-payout"><span class="payout-stake">$1</span> <span class="payout-arrow">&rarr;</span> <span class="payout-return">{payout_str}</span></span>
              <span class="open-platform">{platform_name} <span class="cta-arrow">&raquo;</span></span>
              <span class="share-wrap" data-title="{share_title}" data-quip="{share_quip}" data-payout="{payout_str}" data-url="{url}" data-ticker="{ticker}">
                <button class="share-btn" onclick="toggleShare(event, this)">[share]</button>
                <div class="share-menu">
                  <button class="sm-reddit" onclick="shareTo(event,'reddit',this)">reddit</button>
                  <button class="sm-x" onclick="shareTo(event,'x',this)">x / twitter</button>
                  <button class="sm-fb" onclick="shareTo(event,'fb',this)">facebook</button>
                  <button class="sm-copy" onclick="shareTo(event,'copy',this)">copy link</button>
                </div>
              </span>
            </span>
          </span>
        </a>
      </li>"""


def render_sports_bet_card(m, from_slug=None):
    """Render a sports bet as an <li> — routes through /go/ for click tracking + geo-resolution.

    `from_slug` is the URL slug of the source board ("underdogs", "ocho",
    "chalk", "combo-meal", "the-lineup") so the redirect handler can
    return users to the correct page on geo failure.
    """
    emoji = tier_emoji(m.get("tier", ""))
    tier = m.get("tier", "")
    payout_str = format_payout(m.get("payout", 0))
    raw_title = m.get("title", "")
    raw_quip = m.get("quip", "")
    title = _e(raw_title)
    quip = _e(raw_quip)
    ticker = m.get("ticker", "")
    url = market_link(ticker, from_slug=from_slug) if ticker else m.get("url", "#")

    odds_str = m.get("american_odds", "")
    odds_badge = f'<span class="odds-badge">{_e(odds_str)}</span>' if odds_str else ""

    share_title = _e(raw_title)
    share_quip = _e(raw_quip)

    platform = m.get("platform", "")
    platform_name = PLATFORM_DISPLAY_NAMES.get(platform, platform.title() if platform else "Sportsbook")

    tier_class = f" tier-{tier}" if tier else ""

    return f"""      <li class="wager{tier_class}">
        <a href="{url}" target="_blank" rel="noopener nofollow" data-platform="{platform}" data-tier="{tier}" data-payout="{m.get('payout', 0)}" data-ticker="{ticker}">
          <span class="wager-emoji">{emoji}</span>
          <span class="wager-body">
            <span class="wager-title">{title}</span>
            <span class="wager-quip">{quip}</span>
            <span class="wager-payout-row">
              <span class="wager-payout"><span class="payout-stake">$1</span> <span class="payout-arrow">&rarr;</span> <span class="payout-return">{payout_str}</span></span>
              {odds_badge}
              <span class="open-platform">{platform_name} <span class="cta-arrow">&raquo;</span></span>
              <span class="share-wrap" data-title="{share_title}" data-quip="{share_quip}" data-payout="{payout_str}" data-url="{url}" data-ticker="{ticker}">
                <button class="share-btn" onclick="toggleShare(event, this)">[share]</button>
                <div class="share-menu">
                  <button class="sm-reddit" onclick="shareTo(event,'reddit',this)">reddit</button>
                  <button class="sm-x" onclick="shareTo(event,'x',this)">x / twitter</button>
                  <button class="sm-fb" onclick="shareTo(event,'fb',this)">facebook</button>
                  <button class="sm-copy" onclick="shareTo(event,'copy',this)">copy link</button>
                </div>
              </span>
            </span>
          </span>
        </a>
      </li>"""


def render_sports_bet_list(bets, empty_msg="no bets yet — check back soon.", from_slug=None):
    """Render a list of sports bets as a <ul>.

    `from_slug` is propagated into each card's /go/ link so failure
    redirects can return users to the correct originating board.
    """
    if not bets:
        return f'    <div class="empty-note">{empty_msg}</div>'
    rows = "\n".join(render_sports_bet_card(b, from_slug=from_slug) for b in bets)
    return f"""    <ul class="board" role="list">
{rows}
    </ul>"""


def render_bet_list(bets, empty_msg="no bets yet — check back soon.", longshot_idx=None):
    """Render a list of bets as a <ul>."""
    if not bets:
        return f'    <div class="empty-note">{empty_msg}</div>'
    rows = "\n".join(
        render_bet_card(b, is_longshot_pick=(i == longshot_idx))
        for i, b in enumerate(bets)
    )
    return f"""    <ul class="board" role="list">
{rows}
    </ul>"""


# ── "Today's Board" nav unit ───────────────────────────────

def _pick_promo_bets(board, count=3):
    """Pick bets for the promo unit — one from each tier where possible,
    favoring variety and high scores."""
    if not board:
        return []

    # Group by tier
    by_tier = {}
    for b in board:
        tier = b.get("tier", "green")
        by_tier.setdefault(tier, []).append(b)

    # Sort each tier by score descending
    for tier in by_tier:
        by_tier[tier].sort(key=lambda x: x.get("score", 0), reverse=True)

    # Pick one from each tier, in visual order
    picks = []
    tier_order = ["green", "yellow", "orange", "red", "purple"]
    for tier in tier_order:
        if tier in by_tier and by_tier[tier]:
            picks.append(by_tier[tier][0])
        if len(picks) >= count:
            break

    # If we still need more, fill from remaining highest-scored
    if len(picks) < count:
        used = {id(p) for p in picks}
        remaining = sorted(board, key=lambda x: x.get("score", 0), reverse=True)
        for b in remaining:
            if id(b) not in used:
                picks.append(b)
                used.add(id(b))
            if len(picks) >= count:
                break

    return picks


def render_board_promo(board_data=None, position="top"):
    """Render a 'Today on the Board' promo module using real bet cards.

    Uses the exact same bet card HTML/CSS as the homepage so the cards
    become recognizable brand iconography across the site.

    Args:
        board_data: The board dict (with "board" key). If None, loads latest.
        position: "top" or "bottom" — affects the header/CTA phrasing.
    """
    if board_data is None:
        # Load the latest board
        boards = load_all_boards()
        if not boards:
            return ""
        _, board_data = boards[-1]

    bets = board_data.get("board", [])
    count = 1 if position == "top" else 3
    picks = _pick_promo_bets(bets, count=count)
    if not picks:
        return ""

    cards = "\n".join(render_bet_card(b) for b in picks)

    if position == "top":
        header = "today on the board"
        cta_text = f"see all {len(bets)} of today's bets &rarr;"
    else:
        header = "before you go — today's board"
        cta_text = f"see all {len(bets)} bets &rarr;"

    return f"""    <div class="board-promo">
      <div class="board-promo-header">{header}</div>
      <ul class="board" role="list">
{cards}
      </ul>
      <a href="/" class="board-promo-cta">{cta_text}</a>
    </div>"""


# ── Data loading ────────────────────────────────────────────

def load_all_boards():
    """Load all daily board JSON files, return sorted list of (date, board_data).
    Excludes sports-*.json files (those are loaded separately by load_sports_boards).
    """
    boards = []
    pattern = os.path.join(DATA_DIR, "*.json")
    for filepath in sorted(glob.glob(pattern)):
        basename = os.path.basename(filepath)
        # Only load pure date files (YYYY-MM-DD.json) — skip any prefixed boards
        # (sports-, underdogs-, ocho-, chalk-, combo-, etc.)
        if not basename[0].isdigit():
            continue
        try:
            with open(filepath) as f:
                data = json.load(f)
            date_str = basename.replace(".json", "")
            boards.append((date_str, data))
        except (json.JSONDecodeError, IOError) as e:
            print(f"[generate] Skipping {filepath}: {e}")
    return boards


SPORTS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "boards")


def load_sports_boards():
    """Load sports board JSON files (sports-YYYY-MM-DD.json), return sorted list."""
    return load_board_files("sports")


def load_board_files(prefix):
    """Load board JSON files ({prefix}-YYYY-MM-DD.json), return sorted list."""
    boards = []
    pattern = os.path.join(SPORTS_DATA_DIR, f"{prefix}-*.json")
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath) as f:
                data = json.load(f)
            basename = os.path.basename(filepath).replace(".json", "")
            date_str = basename.replace(f"{prefix}-", "")
            boards.append((date_str, data))
        except (json.JSONDecodeError, IOError) as e:
            print(f"[generate] Skipping {prefix} board {filepath}: {e}")
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
        "h1": "black swans",
        "description": "The internet's strangest prediction markets, translated into what a $1 bet could pay. Weather, pop culture, science, tech — the black swans.",
        "tagline": "The internet's strangest prediction markets. Snow in April, celebrity announcements, AI breakthroughs, earthquake odds — the kind of stuff that sounds fake but has actual money behind it. Translated into $1 payouts.",
    },
    "sports-markets": {
        "title": "sports prediction markets — dollar bets",
        "h1": "sports prediction markets",
        "description": "Sports prediction markets where $1 could pay big. Playoff sweeps, championship longshots, and underdog bets translated into dollar payouts.",
        "tagline": "Sports prediction markets are where drama meets math. A playoff sweep priced at 45 cents. A championship longshot at 3 cents. The kinds of bets your fantasy league group chat argues about.",
    },
    "politics-markets": {
        "title": "political prediction markets — dollar bets",
        "h1": "gridlock",
        "description": "Political prediction markets — elections, policy, and gridlock. Real money odds on what happens next in Washington and beyond, framed as $1 payouts.",
        "tagline": "Political prediction markets where public opinion gets a price tag. Elections, legislation, Supreme Court decisions, international crises — if it can be resolved with a yes or no, someone's trading on it. Framed as $1 payouts.",
    },
    "financial-markets": {
        "title": "financial prediction markets — dollar bets",
        "h1": "ball street",
        "description": "Financial prediction markets — the Fed, interest rates, recessions, stock market milestones, and economic indicators. What does $1 pay when Wall Street gets weird?",
        "tagline": "The Fed, interest rates, recessions, stock market milestones. The markets where the suits meet the spreadsheet degenerates — framed by what a single dollar could pay out.",
    },
    "crypto-markets": {
        "title": "crypto prediction markets — dollar bets",
        "h1": "moonshots",
        "description": "Crypto prediction markets — Bitcoin milestones, ETH price targets, and blockchain moonshots. What does $1 pay if the chart cooperates?",
        "tagline": "Bitcoin milestones, ETH price targets, and blockchain moonshots. The most volatile corner of an already volatile world — framed as $1 payouts with real expiration dates.",
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

    legend = legend_html(board)
    date_line = f'    <div class="date-line" style="margin-bottom:14px">{date_str}</div>\n'

    trust_strip = """
    <div style="margin:20px 0;padding:12px;border-top:1.5px solid #e8cdb5;font-size:10px;color:#806b5b;line-height:1.6">
      tiny stakes. huge maybes. dollar bets is entertainment-first market discovery — not betting advice, not financial advice, and not a guarantee that any market is available where you live. odds and markets change. <a href="/responsible-gambling/" style="color:#6b5744">gamble responsibly</a>. <a href="/availability/" style="color:#6b5744">check availability</a>.
    </div>
"""

    # Select today's filthy little longshot (homepage only)
    longshot_idx = select_filthy_longshot(board)

    body = date_line + legend + DISCLOSURE_STRIP_HTML + render_bet_list(board, longshot_idx=longshot_idx) + trust_strip

    # Homepage structured data: Organization + WebSite + ItemList
    market_items = []
    for i, m in enumerate(board, 1):
        market_items.append(_json_for_script({
            "@type": "ListItem",
            "position": i,
            "name": m.get("title", ""),
            "url": f"{SITE_URL}{market_link(m.get('ticker', ''))}",
        }))

    homepage_schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Dollar Bets",
  "url": "{SITE_URL}",
  "description": "A daily discovery board of the internet's most entertaining prediction-market wagers, framed as $1 payouts."
}}</script>
  <script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Dollar Bets",
  "url": "{SITE_URL}",
  "description": "A buck says maybe. Daily board of the internet's most entertaining wagers."
}}</script>
  <script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Today's Board — {date_str}",
  "numberOfItems": {len(board)},
  "itemListElement": [{", ".join(market_items)}]
}}</script>"""

    html = page_shell(
        title="dollar bets — what does $1 pay?",
        description="A buck says maybe. Daily board of the internet's most entertaining wagers.",
        body=body,
        canonical="/",
        current_nav="/",
        extra_head=homepage_schema,
    )

    write_page("index.html", html)


def generate_lineup_board(sports_boards):
    """Generate the /the-lineup/ page — today's curated sports board (formerly underdogs)."""
    if sports_boards:
        latest_date, latest_data = sports_boards[-1]
        board = latest_data.get("board", [])
        try:
            dt = datetime.fromisoformat(latest_date)
            date_str = dt.strftime("%B %d, %Y")
        except ValueError:
            date_str = latest_date
    else:
        board = []
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Tier counts for subtitle
    tier_counts = {}
    for m in board:
        t = m.get("tier", "unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1

    legend = legend_html(board)
    date_line = f'    <div class="date-line" style="margin-bottom:14px">{date_str}</div>\n'

    # Sports-specific header
    header = """    <h1 class="page-title">the lineup</h1>
    <div class="tagline" style="margin-bottom:12px">
      Sports bets for people who believe garbage time is destiny with a shot clock. Every market is translated into what a single dollar could pay — from respectable favorites to franchise miracles.
    </div>
"""

    # Odds badge CSS (inline since it's sports-only)
    odds_css = """    <style>
      .odds-badge {
        display: inline-block;
        font-size: 10px;
        font-family: monospace;
        color: #806b5b;
        border: 1px solid #e8cdb5;
        border-radius: 3px;
        padding: 1px 5px;
        margin-right: 6px;
        vertical-align: middle;
      }
    </style>
"""

    trust_strip = """
    <div style="margin:20px 0;padding:12px;border-top:1.5px solid #e8cdb5;font-size:10px;color:#806b5b;line-height:1.6">
      tiny stakes. huge maybes. dollar bets is entertainment-first market discovery — not betting advice, not financial advice, and not a guarantee that any market is available where you live. odds and markets change. <a href="/responsible-gambling/" style="color:#6b5744">gamble responsibly</a>. <a href="/availability/" style="color:#6b5744">check availability</a>.
    </div>
"""

    body = header + date_line + legend + DISCLOSURE_STRIP_HTML + render_sports_bet_list(board, from_slug="the-lineup") + trust_strip

    # Structured data
    market_items = []
    for i, m in enumerate(board, 1):
        market_items.append(_json_for_script({
            "@type": "ListItem",
            "position": i,
            "name": m.get("title", ""),
            "url": m.get("url", "#"),
        }))

    lineup_schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "The Lineup — Sports Board",
  "url": "{SITE_URL}/the-lineup/",
  "description": "Today's sharpest sports wagers, framed as $1 payouts.",
  "isPartOf": {{
    "@type": "WebSite",
    "name": "Dollar Bets",
    "url": "{SITE_URL}"
  }}
}}</script>
  <script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "The Lineup — {date_str}",
  "numberOfItems": {len(board)},
  "itemListElement": [{", ".join(market_items)}]
}}</script>"""

    html = page_shell(
        title="the lineup — today's sports board | dollar bets",
        description="Today's sharpest sports wagers, framed as $1 payouts. Every tier, every sport, one board.",
        body=body,
        canonical="/the-lineup/",
        current_nav="/the-lineup/",
        extra_head=odds_css + lineup_schema,
    )

    # Write to /the-lineup/index.html
    lineup_dir = os.path.join(OUTPUT_DIR, "the-lineup")
    os.makedirs(lineup_dir, exist_ok=True)
    with open(os.path.join(lineup_dir, "index.html"), "w") as f:
        f.write(html)
    print(f"[generate] Wrote the lineup board: {len(board)} picks")


# ── Sports sub-board generator (shared by underdogs, ocho, chalk, combo meal) ──

SPORTS_BOARD_CONFIGS = {
    "underdogs": {
        "file_prefix": "underdogs",
        "url_slug": "underdogs",
        "page_title": "underdogs",
        "tagline": "Pure moneyline underdogs. Every pick on this board is a team that isn't supposed to win — but what if they do? $1 bets on davids vs goliaths.",
        "meta_title": "underdogs — moneyline longshots | dollar bets",
        "meta_description": "Today's best moneyline underdogs, framed as $1 payouts. Every pick is a team that isn't supposed to win.",
    },
    "ocho": {
        "file_prefix": "ocho",
        "url_slug": "the-ocho",
        "page_title": "the ocho",
        "tagline": "If ESPN won't cover it, we will. Cricket, rugby, Aussie rules, handball, lacrosse — the sports your bookie forgot existed, translated into $1 payouts.",
        "meta_title": "the ocho — obscure sports odds | dollar bets",
        "meta_description": "Odds on sports you didn't know had odds. Cricket, rugby league, AFL, handball, and more — framed as $1 payouts.",
    },
    "chalk": {
        "file_prefix": "chalk",
        "url_slug": "chalk",
        "page_title": "chalk",
        "tagline": "Heavy favorites only. The bets that should hit. Tiny payouts, high probability, deadpan energy. Boring money is still money.",
        "meta_title": "chalk — heavy favorites | dollar bets",
        "meta_description": "Today's heaviest favorites in sports, framed as $1 payouts. Near-locks for people who like boring money.",
    },
    "combo-meal": {
        "file_prefix": "combo",
        "url_slug": "combo-meal",
        "page_title": "the combo meal",
        "tagline": "Pre-built parlays served hot. Each combo stacks 2-3 legs into a single $1 payout — from the value menu to the triple bypass. Would you like to supersize that?",
        "meta_title": "the combo meal — pre-built parlays | dollar bets",
        "meta_description": "Pre-built sports parlays framed as $1 payouts. From safe combos to degenerate stacks.",
    },
}


def generate_sports_sub_board(board_key):
    """Generate a sports sub-board page (underdogs, ocho, chalk, combo-meal)."""
    config = SPORTS_BOARD_CONFIGS[board_key]
    boards = load_board_files(config["file_prefix"])

    if not boards:
        print(f"[generate] No {board_key} boards found, skipping")
        return

    latest_date, latest_data = boards[-1]
    board = latest_data.get("board", [])

    try:
        dt = datetime.fromisoformat(latest_date)
        date_str = dt.strftime("%B %d, %Y")
    except ValueError:
        date_str = latest_date

    legend = legend_html(board)
    date_line = f'    <div class="date-line" style="margin-bottom:14px">{date_str}</div>\n'

    header = f"""    <h1 class="page-title">{config["page_title"]}</h1>
    <div class="tagline" style="margin-bottom:12px">
      {config["tagline"]}
    </div>
"""

    odds_css = """    <style>
      .odds-badge {
        display: inline-block;
        font-size: 10px;
        font-family: monospace;
        color: #806b5b;
        border: 1px solid #e8cdb5;
        border-radius: 3px;
        padding: 1px 5px;
        margin-right: 6px;
        vertical-align: middle;
      }
    </style>
"""

    trust_strip = """
    <div style="margin:20px 0;padding:12px;border-top:1.5px solid #e8cdb5;font-size:10px;color:#806b5b;line-height:1.6">
      tiny stakes. huge maybes. dollar bets is entertainment-first market discovery — not betting advice, not financial advice, and not a guarantee that any market is available where you live. odds and markets change. <a href="/responsible-gambling/" style="color:#6b5744">gamble responsibly</a>. <a href="/availability/" style="color:#6b5744">check availability</a>.
    </div>
"""

    empty_msg = "no picks right now — check back soon. some sports sleep so the board can wake up swinging."
    body = header + date_line + legend + DISCLOSURE_STRIP_HTML + render_sports_bet_list(board, empty_msg, from_slug=config["url_slug"]) + trust_strip

    slug = config["url_slug"]
    schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "{config['page_title']}",
  "url": "{SITE_URL}/{slug}/",
  "description": "{config['meta_description']}",
  "isPartOf": {{
    "@type": "WebSite",
    "name": "Dollar Bets",
    "url": "{SITE_URL}"
  }}
}}</script>"""

    html = page_shell(
        title=config["meta_title"],
        description=config["meta_description"],
        body=body,
        canonical=f"/{slug}/",
        current_nav=f"/{slug}/",
        extra_head=odds_css + schema,
    )

    out_dir = os.path.join(OUTPUT_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)
    print(f"[generate] Wrote {board_key} board: {len(board)} picks")


def generate_tier_pages(boards, sports_boards):
    """Generate /tier/{name}/ pages — all active markets filtered by payout tier."""
    TIERS = {
        "green": {
            "label": "respectable",
            "emoji": "🟩",
            "title": "respectable bets — $2-3 payouts | dollar bets",
            "description": "Every active prediction market bet paying $2-3 on a dollar. The board's most grounded wagers — unlikely, but not unreasonable.",
            "intro": "The green tier. These pay $2–3 on a dollar — the kind of odds that make you think twice before dismissing them. Not moonshots. Not safe bets. Just the ones where the math isn't laughing at you.",
        },
        "yellow": {
            "label": "alive",
            "emoji": "🟨",
            "title": "alive bets — $4-6 payouts | dollar bets",
            "description": "Every active prediction market bet paying $4-6 on a dollar. Longshots that still have a pulse.",
            "intro": "The yellow tier. $4–6 on a dollar — still breathing, still plausible, still the kind of thing that makes you refresh the news at midnight. These are alive.",
        },
        "orange": {
            "label": "heater",
            "emoji": "🟧",
            "title": "heater bets — $7-15 payouts | dollar bets",
            "description": "Every active prediction market bet paying $7-15 on a dollar. The board's hottest longshots.",
            "intro": "The orange tier. $7–15 on a dollar — now you're gambling on chaos. These are the bets that make the board interesting. Low probability. High entertainment value.",
        },
        "red": {
            "label": "filthy",
            "emoji": "🟥",
            "title": "filthy bets — $20+ payouts | dollar bets",
            "description": "Every active prediction market bet paying $20+ on a dollar. The filthiest longshots on the board.",
            "intro": "The red tier. $20+ on a dollar — filthy. The market thinks these are nearly impossible. History disagrees just often enough to keep things interesting.",
        },
        "purple": {
            "label": "generational",
            "emoji": "🟪",
            "title": "generational bets — $100+ payouts | dollar bets",
            "description": "Every active prediction market bet paying $100+ on a dollar. Once-in-a-generation longshots.",
            "intro": "The purple tier. $100+ on a dollar — generational. If one of these hits, it's the kind of thing people talk about for years. You'd tell your grandchildren.",
        },
    }

    # Collect all active markets across ALL boards (not just today's)
    seen_tickers = set()
    all_markets = []
    for date_str, board_data in reversed(boards):  # newest first, dedup by ticker
        for m in board_data.get("board", []):
            ticker = m.get("ticker") or m.get("id") or m.get("url", "")
            if ticker and ticker in seen_tickers:
                continue
            if ticker:
                seen_tickers.add(ticker)
            m["_source"] = date_str
            all_markets.append(m)
    for _, sports_data in reversed(sports_boards or []):
        for m in sports_data.get("board", []):
            ticker = m.get("ticker") or m.get("id") or m.get("url", "")
            if ticker and ticker in seen_tickers:
                continue
            if ticker:
                seen_tickers.add(ticker)
            m["_source"] = "the-lineup"
            all_markets.append(m)

    for tier_key, tier_info in TIERS.items():
        tier_markets = [m for m in all_markets if m.get("tier") == tier_key]

        header = f"""    <h1 class="page-title">{tier_info['emoji']} {tier_info['label']}</h1>
    <div class="tagline" style="margin-bottom:12px">
      {tier_info['intro']}
    </div>
"""
        mkt_word = "market" if len(tier_markets) == 1 else "markets"
        count_line = f'    <div class="date-line" style="margin-bottom:14px">{len(tier_markets)} active {mkt_word} across all boards</div>\n'

        body = header + count_line + render_bet_list(tier_markets, empty_msg="no active markets at this tier right now — check back tomorrow.")

        tier_schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "{tier_info['label'].title()} Tier — Dollar Bets",
  "url": "{SITE_URL}/tier/{tier_info['label']}/",
  "description": "{tier_info['description']}"
}}</script>"""

        html = page_shell(
            title=tier_info["title"],
            description=tier_info["description"],
            body=body,
            canonical=f"/tier/{tier_info['label']}/",
            current_nav="",
            extra_head=tier_schema,
        )

        tier_dir = os.path.join(OUTPUT_DIR, "tier", tier_info["label"])
        os.makedirs(tier_dir, exist_ok=True)
        with open(os.path.join(tier_dir, "index.html"), "w") as f:
            f.write(html)
        print(f"[generate] Wrote tier page: {tier_info['label']} ({len(tier_markets)} markets)")


_TIER_SORT = {"purple": 0, "red": 1, "orange": 2, "yellow": 3, "green": 4}

def _tier_then_payout(bet):
    """Sort key: group by tier (purple first), then by payout desc within tier."""
    return (_TIER_SORT.get(bet.get("tier", "green"), 5), -bet.get("payout", 0))

def generate_category_pages(all_bets):
    """Generate category SEO hub pages."""
    # Bucket bets by category
    cat_bets = defaultdict(list)
    for bet in all_bets:
        slug = categorize_bet(bet)
        cat_bets[slug].append(bet)

    # Related board suggestions for each category
    RELATED_BOARDS = {
        "weird-markets": [("gridlock", "/politics-markets/"), ("moonshots", "/crypto-markets/"), ("the ocho", "/the-ocho/")],
        "sports-markets": [("underdogs", "/underdogs/"), ("chalk", "/chalk/"), ("combo meal", "/combo-meal/")],
        "politics-markets": [("black swans", "/weird-markets/"), ("ball street", "/financial-markets/"), ("chalk", "/chalk/")],
        "financial-markets": [("moonshots", "/crypto-markets/"), ("gridlock", "/politics-markets/"), ("black swans", "/weird-markets/")],
        "crypto-markets": [("ball street", "/financial-markets/"), ("black swans", "/weird-markets/"), ("the ocho", "/the-ocho/")],
    }

    CATEGORY_EMAIL_COPY = {
        "weird-markets": "get tomorrow's weirdest markets.",
        "sports-markets": "get tomorrow's sports board.",
        "politics-markets": "get tomorrow's political chaos board.",
        "financial-markets": "get tomorrow's financial markets.",
        "crypto-markets": "get tomorrow's moonshots.",
    }

    CATEGORY_EMPTY_STATES = {
        "weird-markets": "no new black swans today. civilization briefly behaved.",
        "sports-markets": "no sports markets today. everyone stayed in their lane.",
        "politics-markets": "no new gridlock today. congress must be on recess.",
        "financial-markets": "no new ball street markets today. the printer rests.",
        "crypto-markets": "no new moonshots today. number went sideways.",
    }

    # Figure out today's date for splitting current vs archive
    from datetime import date as date_type
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for slug, config in CATEGORIES.items():
        bets = cat_bets.get(slug, [])

        # Deduplicate by title, keep most recent
        seen_titles = {}
        for b in bets:
            t = b.get("title", "")
            if t not in seen_titles or b.get("date_featured", "") > seen_titles[t].get("date_featured", ""):
                seen_titles[t] = b
        unique_bets = sorted(seen_titles.values(), key=_tier_then_payout)

        # Split into today's vs archive
        today_bets = [b for b in unique_bets if b.get("date_featured", "") >= today_str]
        archive_bets = [b for b in unique_bets if b.get("date_featured", "") < today_str][:15]

        # Build body with today's section + archive section
        cat_name = config['h1']
        empty_state = CATEGORY_EMPTY_STATES.get(slug, "no markets in this category today — check back soon.")

        today_section = ""
        if today_bets:
            today_section = f"""    <h2 class="section-head">today's {cat_name}</h2>
{render_bet_list(today_bets)}
"""
        else:
            today_section = f"""    <h2 class="section-head">today's {cat_name}</h2>
    <div class="empty-note">{empty_state}</div>
"""

        archive_section = ""
        if archive_bets:
            archive_section = f"""    <h2 class="section-head" style="border-top:1.5px solid #e8cdb5;padding-top:16px;margin-top:20px">all {cat_name}</h2>
{render_bet_list(archive_bets)}
"""

        # Related boards links
        related = RELATED_BOARDS.get(slug, [])
        related_html = ""
        if related:
            related_links = " &middot; ".join(f'<a href="{href}" style="color:#b5470a;text-decoration:none">{name}</a>' for name, href in related)
            related_html = f'    <div style="padding:16px 0;font-size:12px;color:#6b5744;border-top:1.5px solid #e8cdb5;margin-top:16px">more boards: {related_links}</div>\n'

        body = f"""    <h1 class="page-title">{config['h1']}</h1>
    <div class="tagline" style="margin-bottom:12px">
      {config['tagline']}
    </div>

{today_section}
{archive_section}
{related_html}"""

        # All bets for schema (today + archive combined)
        all_category_bets = today_bets + archive_bets

        # CollectionPage + ItemList + BreadcrumbList schema
        cat_items = []
        for i, m in enumerate(all_category_bets, 1):
            cat_items.append(_json_for_script({
                "@type": "ListItem",
                "position": i,
                "name": m.get("title", ""),
                "url": f"{SITE_URL}{market_link(m.get('ticker', ''))}",
            }))

        cat_schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "{config['h1']}",
  "url": "{SITE_URL}/{slug}/",
  "description": "{config['description']}",
  "publisher": {{"@type": "Organization", "name": "Dollar Bets", "url": "{SITE_URL}"}},
  "mainEntity": {{
    "@type": "ItemList",
    "numberOfItems": {len(all_category_bets)},
    "itemListElement": [{", ".join(cat_items)}]
  }}
}}</script>
  <script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": "{config['h1']}", "item": "{SITE_URL}/{slug}/"}}
  ]
}}</script>"""

        html = page_shell(
            title=config["title"],
            description=config["description"],
            body=body,
            canonical=f"/{slug}/",
            current_nav=f"/{slug}/",
            extra_head=cat_schema,
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
        unique_bets = sorted(seen.values(), key=_tier_then_payout)
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
    """Render a recap highlight block. Untrusted fields escaped."""
    return f"""    <div class="recap-block">
      <div class="recap-label">{_e(label)}</div>
      <div class="recap-title">{tier_emoji(bet.get('tier', ''))} {_e(bet.get('title', ''))}</div>
      <div class="recap-detail">{_e(detail)}</div>
      <div class="recap-quip">{_e(bet.get('quip', ''))}</div>
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
        raw_title = bet.get("title", "")
        slug = slugify(raw_title)
        if not slug:
            continue

        payout = bet.get("payout", 0)
        # Untrusted board fields — escape before interpolating into HTML
        title = _e(raw_title)
        quip = _e(bet.get("quip", ""))
        category = _e(bet.get("category", "unknown"))
        date_featured = _e(bet.get("date_featured", "unknown"))
        # Build /go/ link for market
        ticker = bet.get("ticker", "")
        if ticker:
            url = market_link(ticker)
        else:
            url = "#"

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
      <p>At {format_payout(payout)} on a dollar, this was a {tier_label(bet.get('tier', ''))} tier bet. The kind of market that makes you open a new tab and start reading. Filed under {_e(bet.get("category", "").lower())} on Kalshi, it caught Dollar Bets' attention for the payout drama and the cultural hook.</p>
    </div>

    <div class="autopsy-section">
      <h3>the bet type</h3>
      <p>This is a classic {_e(_archetype_name(bet))} — the kind of market that shows up on prediction platforms whenever the news cycle gets interesting. The structure is simple: yes or no, by a deadline, with real money on the line.</p>
    </div>

    <div class="autopsy-section">
      <h3>see this market</h3>
      <p><a href="{url}" target="_blank" rel="noopener nofollow" style="color:#333">view on kalshi →</a></p>
    </div>
"""

        html = page_shell(
            # page_shell escapes title/description itself — pass the raw text
            title=f"market autopsy: {raw_title} — dollar bets",
            description=f"Dollar Bets market autopsy: {raw_title}. What it was, why it was interesting, and what $1 could have paid ({format_payout(payout)}).",
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
    body = """    <h1 class="page-title">about dollar bets</h1>
    <div class="page-intro">
      <p>Dollar Bets is a daily discovery board of the internet's most entertaining wagers, all priced at what a single dollar would pay out.</p>

      <p>Every day we scan thousands of prediction markets and surface the 10 weirdest, funniest, and most culturally relevant ones. We translate every market into a simple question: if you put $1 on this, what would you get back?</p>

      <p style="margin-top:16px"><a href="/" style="color:#b5470a;font-weight:700;text-decoration:none;border:1.5px solid #e8cdb5;padding:8px 16px;border-radius:6px;background:#fff">see today's board &rarr;</a></p>

      <p style="font-weight:700; margin-top:24px">what "$1 pays $80" means</p>

      <p>Prediction markets let you trade on the outcome of real events. Prices move between $0 and $1. If an outcome is trading at $0.0125, a $1 bet pays $80 if it happens. That's it. We frame every market this way so you can instantly compare how weird the odds are.</p>

      <p style="font-size:11px;font-weight:700;color:#b5470a;text-transform:uppercase;letter-spacing:1.2px;margin-top:16px">example</p>
    </div>

    <ul class="board" style="margin-bottom:18px">
      <li class="wager tier-orange">
        <a href="/go/KXSNOW/" target="_blank" rel="noopener nofollow">
          <span class="wager-emoji">🟧</span>
          <span class="wager-body">
            <span class="wager-title">Snow in Phoenix before March?</span>
            <span class="wager-quip">weather channel intern enters witness protection</span>
            <span class="wager-payout-row">
              <span class="wager-payout"><span class="payout-stake">$1</span> <span class="payout-arrow">&rarr;</span> <span class="payout-return">$80</span></span>
              <span class="open-platform">Kalshi <span class="cta-arrow">&raquo;</span></span>
            </span>
          </span>
        </a>
      </li>
    </ul>

    <div class="page-intro">
      <p style="font-weight:700">the payout tiers</p>

      <p>🟩 <strong>$1–$10</strong> — respectable<br>
      🟨 <strong>$11–$50</strong> — alive<br>
      🟧 <strong>$51–$100</strong> — heater<br>
      🟥 <strong>$101–$500</strong> — filthy<br>
      🟪 <strong>$500+</strong> — generational</p>

      <p style="font-weight:700; margin-top:16px">what dollar bets is not</p>

      <div style="background:#fff;border:1.5px solid #e8cdb5;border-radius:8px;padding:14px 16px;font-size:13px;color:#6b5744;line-height:2;margin:8px 0 16px">
        &#10005;&nbsp; not a sportsbook<br>
        &#10005;&nbsp; not a bookmaker<br>
        &#10005;&nbsp; not betting advice<br>
        &#10005;&nbsp; not a guarantee anything is available where you live
      </div>

      <p>Dollar Bets is a discovery and editorial layer — we curate markets the way a good newspaper curates headlines, with taste, timing, and a mild disregard for conventional financial advice. Every listing links directly to the market on the relevant platform.</p>

      <p>The markets we feature are real. They have real money behind them, real deadlines, and real outcomes. Most of the longshots will not pay off. That's what makes them longshots. The point is not to win — the point is that these markets exist at all, and they're frequently absurd, occasionally profound, and almost always more entertaining than whatever else you were going to do with a dollar.</p>

      <p style="font-weight:700; margin-top:16px">how we pick the board</p>

      <p>we like markets that are:</p>
      <p style="padding-left:12px;color:#6b5744">
        — weird enough to screenshot<br>
        — specific enough to resolve<br>
        — current enough to matter<br>
        — funny before they are profitable
      </p>

      <p>we do not rank markets by what we think will win. we rank them by whether they deserve to exist on the internet.</p>

      <p>The board updates daily. The email is free. The bets are a dollar. The rest is up to the universe.</p>

      <p style="margin-top:20px; display:flex; gap:12px; flex-wrap:wrap">
        <a href="/" style="color:#b5470a;font-weight:700;text-decoration:none;border:1.5px solid #e8cdb5;padding:8px 16px;border-radius:6px;background:#fff">see today's board &rarr;</a>
      </p>

      <p style="font-weight:700; margin-top:16px">contact us</p>

      <p><a href="mailto:hello@dollarbets.lol" style="color:#6b5744">hello@dollarbets.lol</a></p>

      <p style="margin-top:12px"><a href="/editorial-policy/" style="color:#6b5744">editorial policy</a> · <a href="/affiliate-disclosure/" style="color:#6b5744">affiliate disclosure</a> · <a href="/responsible-gambling/" style="color:#6b5744">responsible gambling</a></p>
    </div>
"""

    about_schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "AboutPage",
  "name": "About Dollar Bets",
  "url": "{SITE_URL}/about/",
  "description": "Dollar Bets is a daily board of weird, funny, and culturally relevant prediction markets, translated into what a $1 bet could pay.",
  "mainEntity": {{
    "@type": "Organization",
    "name": "Dollar Bets",
    "url": "{SITE_URL}",
    "description": "A daily discovery board of the internet's most entertaining prediction-market wagers, framed as $1 payouts. Not a sportsbook — an editorial discovery layer.",
    "foundingDate": "2026",
    "logo": "{SITE_URL}/favicon.svg",
    "sameAs": [
      "https://www.reddit.com/r/dollarbets/"
    ],
    "contactPoint": {{
      "@type": "ContactPoint",
      "email": "hello@dollarbets.lol",
      "contactType": "customer support"
    }}
  }}
}}</script>
  <script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": "About", "item": "{SITE_URL}/about/"}}
  ]
}}</script>"""

    html = page_shell(
        title="what is dollar bets? — about",
        description="Dollar Bets is a daily board of weird, funny, and culturally relevant prediction markets, translated into what a $1 bet could pay. Not a sportsbook — a discovery layer.",
        body=body,
        canonical="/about/",
        current_nav="/about/",
        extra_head=about_schema,
    )

    write_page("about/index.html", html)


# ── Sitemap ─────────────────────────────────────────────────

# ── Content policy guardrail ──────────────────────────────────────────────
# Commodity / off-strategy clusters that rank pos 60+ and drag down the
# site-wide quality signal (see seo-system-audit-2026-06-05.md). Pages whose
# slug matches one of these patterns are auto-noindexed and excluded from the
# sitemap, so the system can't silently drift back to publishing them.
# Escape hatch: set "policy_override": true in a page's content JSON to
# intentionally publish a matching page anyway.
BLOCKED_SLUG_PATTERNS = [
    (r"odds-explained",            "generic odds mechanics — competes w/ Investopedia/DraftKings"),
    (r"^how-to-read-.*-odds$",     "odds mechanics explainer"),
    (r"^how-do-.*-odds",           "odds mechanics explainer"),
    (r"-odds-mean$",               "odds-value glossary long-tail"),
    (r"^what-is-an?-.*-bet$",      "generic bet-type definition"),
    (r"^what-is-a-prediction-market$", "generic definitional"),
    (r"prediction-markets-for-beginners", "generic definitional"),
    (r"same-game-parlays-explained",      "generic parlay explainer"),
    (r"-vs-sports-betting",        "generic sports-betting comparison — off-franchise"),
    (r"nba",                       "NBA props — explicitly off the table"),
    (r"weather",                   "weather cluster — India-skewed, deprioritized"),
]


def policy_noindex(page_data):
    """Return (noindex: bool, reason: str) for a content page.

    Honors an explicit "noindex" flag, an explicit "policy_override", and the
    BLOCKED_SLUG_PATTERNS denylist. Shared by the page renderer and the sitemap
    builder so the noindex meta tag and sitemap exclusion never disagree.
    """
    if page_data.get("policy_override"):
        return (bool(page_data.get("noindex", False)),
                page_data.get("noindex_reason", ""))
    if page_data.get("noindex"):
        return (True, page_data.get("noindex_reason", "explicit noindex"))
    slug = page_data.get("slug", "") or page_data.get("seo", {}).get("canonical", "").strip("/")
    for pat, reason in BLOCKED_SLUG_PATTERNS:
        if re.search(pat, slug):
            return (True, "content-policy: " + reason)
    return (False, "")


def generate_sitemap(pages):
    """Generate sitemap.xml from (path, priority) or (path, priority, lastmod) tuples.

    Pages without an explicit lastmod default to today (correct for the daily
    board/section pages that genuinely change every build). Evergreen content
    passes its real last-updated date so the sitemap stops claiming every URL
    changed today on every crawl (an anti-pattern Google discounts)."""
    today = datetime.now().strftime("%Y-%m-%d")
    urls = []
    for entry in pages:
        if len(entry) == 3:
            path, priority, lastmod = entry
            lastmod = lastmod or today
        else:
            path, priority = entry
            lastmod = today
        urls.append(f"""  <url>
    <loc>{SITE_URL}{path}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{"daily" if priority >= 0.8 else "weekly"}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    write_page("sitemap.xml", xml)


def generate_html_sitemap(pages):
    """Generate /sitemap/ — human-readable HTML sitemap, also a crawl aid.

    Groups all URLs from the XML sitemap into sections so Googlebot has a
    single page that links to every other page on the site. Cheap fix for
    the discovery problem on a young domain where category landing pages
    don't yet list every child page.
    """
    # Bucket each path by section. Order matters — first match wins.
    # (label, prefix_predicate)
    buckets = [
        ("front page", lambda p: p == "/"),
        ("today's boards", lambda p: p in {
            "/the-lineup/", "/underdogs/", "/chalk/", "/heater/",
            "/combo-meal/", "/the-ocho/", "/availability/",
        }),
        ("categories", lambda p: p in {
            "/weird-markets/", "/politics-markets/", "/sports-markets/",
            "/financial-markets/", "/crypto-markets/",
        }),
        ("tiers", lambda p: p.startswith("/tier/")),
        ("archetypes", lambda p: p.startswith("/archetypes")),
        ("guides", lambda p: p == "/guides/"),
        ("hall of filth", lambda p: p.startswith("/hall-of-filth")),
        ("market autopsies", lambda p: p.startswith("/autopsy/")),
        ("recaps", lambda p: p.startswith("/recap/")),
        ("info", lambda p: p in {
            "/about/", "/affiliate-disclosure/", "/privacy/", "/terms/",
            "/responsible-gambling/", "/sitemap/",
        }),
    ]

    # Anything not matched above is treated as a standalone guide/explainer
    # page (e.g. /what-is-a-prediction-market/, /best-bets-this-weekend/).
    section_paths = {label: [] for label, _ in buckets}
    section_paths["guides & explainers"] = []
    bucketed = set()
    for entry in pages:
        path = entry[0]
        if path == "/sitemap/":  # don't list this page on itself
            continue
        placed = False
        for label, pred in buckets:
            if pred(path):
                section_paths[label].append(path)
                bucketed.add(path)
                placed = True
                break
        if not placed:
            section_paths["guides & explainers"].append(path)

    # Render. Plain monospace list, Drudge-style — no card UI, no icons.
    section_order = [
        "front page",
        "today's boards",
        "categories",
        "tiers",
        "archetypes",
        "guides",
        "guides & explainers",
        "hall of filth",
        "market autopsies",
        "recaps",
        "info",
    ]
    body_parts = [
        '    <h1 class="page-title">sitemap</h1>',
        '    <div class="page-intro">',
        '      <p>Every page on dollarbets.lol, plainly listed. If you\'re here from search, this is the table of contents.</p>',
        '    </div>',
    ]
    total = 0
    for label in section_order:
        paths = sorted(set(section_paths.get(label, [])))
        if not paths:
            continue
        body_parts.append(f'    <h2 style="font-size:13px;text-transform:uppercase;letter-spacing:1px;margin-top:24px;border-bottom:1px solid #e8e7e0;padding-bottom:4px">{label} <span style="color:#7a6e5f;font-weight:normal">({len(paths)})</span></h2>')
        body_parts.append('    <ul style="list-style:none;padding-left:0;margin:8px 0 0 0;font-size:12px;line-height:1.7">')
        for path in paths:
            label_text = path.strip("/") or "home"
            body_parts.append(f'      <li><a href="{path}" style="color:#000;text-decoration:underline">{label_text}</a></li>')
        body_parts.append('    </ul>')
        total += len(paths)

    body_parts.append(f'    <div style="margin-top:24px;font-size:10px;color:#7a6e5f">{total} pages total. last updated {datetime.now().strftime("%Y-%m-%d")}.</div>')

    body = "\n".join(body_parts)
    html = page_shell(
        title="sitemap — dollar bets",
        description="Every page on dollarbets.lol. The full table of contents.",
        body=body,
        canonical="/sitemap/",
    )
    write_page("sitemap/index.html", html)


def generate_robots_txt():
    """Generate robots.txt with sitemap reference."""
    txt = f"""User-agent: *
Allow: /
Disallow: /go/
Disallow: /api/
Disallow: /admin/

# AI crawlers welcome
User-agent: GPTBot
Allow: /
Disallow: /go/
Disallow: /api/
Disallow: /admin/

User-agent: ClaudeBot
Allow: /
Disallow: /go/
Disallow: /api/
Disallow: /admin/

User-agent: PerplexityBot
Allow: /
Disallow: /go/
Disallow: /api/
Disallow: /admin/

User-agent: GoogleOther
Allow: /
Disallow: /go/
Disallow: /api/
Disallow: /admin/

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

    <ul class="board" role="list">
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

    <ul class="board" role="list">
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


# ── 404 page ───────────────────────────────────────────────

def generate_404_page():
    """Generate a custom 404 error page."""
    body = """    <h1 class="page-title">404 — page not found</h1>
    <div class="page-intro">
      <p>This page doesn't exist. Maybe it never did. Maybe the market expired. Either way, the odds of finding what you wanted here are exactly zero — and we don't list markets with zero payout.</p>
      <p style="margin-top:12px">Try one of these instead:</p>
      <p style="margin-top:8px">
        <a href="/" style="color:#b5470a;font-weight:700">today's board</a> ·
        <a href="/weird-markets/" style="color:#666">weird markets</a> ·
        <a href="/sports-markets/" style="color:#666">sports markets</a> ·
        <a href="/about/" style="color:#666">about</a> ·
        <a href="/guides/" style="color:#666">guides</a>
      </p>
    </div>
"""

    html = page_shell(
        title="404 — page not found — dollar bets",
        description="This page doesn't exist on Dollar Bets.",
        body=body,
        canonical="",
        noindex=True,
    )

    write_page("404.html", html)


# ── Per-bet share pages & OG images ────────────────────────

def generate_share_og_image(title, quip, payout_str, output_path):
    """Generate a 1200x630 OG image for a single bet."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[generate] WARNING: Pillow not installed, skipping OG image generation")
        return False

    import textwrap

    FONT_SERIF_BOLD = None
    FONT_SERIF_ITALIC = None
    FONT_MONO = None
    FONT_MONO_BOLD = None

    # Try multiple font paths (local dev vs Vercel build)
    # .fonts/ dir is populated by build.sh on Vercel
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fonts")
    serif_bold_candidates = [
        os.path.join(fonts_dir, "DejaVuSerif-Bold.ttf"),
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ]
    serif_italic_candidates = [
        os.path.join(fonts_dir, "DejaVuSerif-Italic.ttf"),
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    ]
    mono_candidates = [
        os.path.join(fonts_dir, "DejaVuSansMono.ttf"),
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    mono_bold_candidates = [
        os.path.join(fonts_dir, "DejaVuSansMono-Bold.ttf"),
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ]

    for path in serif_bold_candidates:
        if os.path.exists(path):
            FONT_SERIF_BOLD = path
            break
    for path in serif_italic_candidates:
        if os.path.exists(path):
            FONT_SERIF_ITALIC = path
            break
    for path in mono_candidates:
        if os.path.exists(path):
            FONT_MONO = path
            break
    for path in mono_bold_candidates:
        if os.path.exists(path):
            FONT_MONO_BOLD = path
            break

    if not all([FONT_SERIF_BOLD, FONT_SERIF_ITALIC, FONT_MONO, FONT_MONO_BOLD]):
        print(f"[generate] WARNING: Missing fonts, skipping OG image for {output_path}")
        return False

    W, H = 1200, 630
    BG = (253, 246, 238)
    ORANGE = (232, 100, 44)
    DARK = (45, 35, 25)
    MID = (107, 87, 68)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Orange bars top and bottom
    draw.rectangle([(0, 0), (W, 10)], fill=ORANGE)
    draw.rectangle([(0, H - 10), (W, H)], fill=ORANGE)

    # Title — Georgia bold, centered
    font_title = ImageFont.truetype(FONT_SERIF_BOLD, 56)
    wrapped = textwrap.fill(title, width=26)
    lines = wrapped.split("\n")[:3]  # max 3 lines
    line_height = 68
    total_title_h = len(lines) * line_height

    # Quip — Georgia italic, centered, in quotes
    font_quip = ImageFont.truetype(FONT_SERIF_ITALIC, 48)
    quip_text = f'"{quip}"' if quip else ""
    quip_wrapped = textwrap.fill(quip_text, width=34)
    quip_lines = quip_wrapped.split("\n")[:2]  # max 2 lines
    quip_line_height = 58
    total_quip_h = len(quip_lines) * quip_line_height if quip_text else 0

    # Payout — monospace bold, centered
    font_payout = ImageFont.truetype(FONT_MONO_BOLD, 56)
    payout_text = f"$1 pays {payout_str}"

    # Vertical layout: center all three blocks together
    gap_title_quip = 20
    gap_quip_payout = 28
    total_content_h = total_title_h + gap_title_quip + total_quip_h + gap_quip_payout + 56
    start_y = (H - total_content_h) // 2

    # Draw title
    title_y = start_y
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, title_y + i * line_height), line, fill=DARK, font=font_title)

    # Draw quip
    quip_y = title_y + total_title_h + gap_title_quip
    for i, line in enumerate(quip_lines):
        bbox = draw.textbbox((0, 0), line, font=font_quip)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, quip_y + i * quip_line_height), line, fill=MID, font=font_quip)

    # Draw payout
    payout_y = quip_y + total_quip_h + gap_quip_payout
    bbox = draw.textbbox((0, 0), payout_text, font=font_payout)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, payout_y), payout_text, fill=ORANGE, font=font_payout)

    # Logo — bottom left
    font_logo = ImageFont.truetype(FONT_SERIF_BOLD, 28)
    draw.text((40, H - 48), "dollarbets.lol", fill=ORANGE, font=font_logo)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    return True


def generate_share_pages(boards):
    """Generate /share/TICKER/ pages with per-bet OG tags + OG images."""
    if not boards:
        return

    latest_date, latest_data = boards[-1]
    board = latest_data.get("board", [])

    count = 0
    for m in board:
        ticker = m.get("ticker", "")
        if not ticker:
            continue

        title = m.get("title", "")
        quip = m.get("quip", "")
        payout = m.get("payout", 0)
        payout_str = format_payout(payout)

        # Sanitize ticker for filesystem. Tickers come from external APIs
        # (Kalshi, Polymarket) — a malformed value with .. or path separators
        # could escape the share/ directory at build time. Strip everything
        # outside the safe character set.
        safe_ticker = re.sub(r"[^A-Za-z0-9_.\-]", "_", ticker)
        # Defense-in-depth: refuse anything that's purely dots / empty after sub
        if not safe_ticker or safe_ticker.strip(".") == "":
            continue

        # Generate OG image
        og_dir = os.path.join(OUTPUT_DIR, "share", safe_ticker)
        og_img_path = os.path.join(og_dir, "og.png")
        os.makedirs(og_dir, exist_ok=True)
        has_og_image = generate_share_og_image(title, quip, payout_str, og_img_path)

        # Use per-bet image if generated, otherwise fall back to site-wide
        if has_og_image:
            og_image_url = f"{SITE_URL}/share/{safe_ticker}/og.png"
        else:
            og_image_url = f"{SITE_URL}/og-image.png"

        # Full HTML-attribute escaping (not just quotes) — title/quip can come
        # from external APIs, AI-generated quips, or CMS editors, and must be
        # safe to interpolate into content="..." attributes and <title> text.
        safe_quip = _e(quip)
        safe_title_og = _e(title)
        og_desc = f'&quot;{safe_quip}&quot; — $1 pays {_e(payout_str)} on Dollar Bets. Daily prediction market picks where every bet starts at a buck.'
        og_title = f"{safe_title_og} — $1 → {_e(payout_str)}"

        # Build a lightweight share page that redirects to homepage via JS
        # (JS redirect so crawlers read OG tags; meta refresh would bypass them)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{og_title} | Dollar Bets</title>
  <meta name="description" content="{og_desc}">
  <meta property="og:title" content="{og_title}">
  <meta property="og:description" content="{og_desc}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}/share/{safe_ticker}/">
  <meta property="og:site_name" content="Dollar Bets">
  <meta property="og:image" content="{og_image_url}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:type" content="image/png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{og_title}">
  <meta name="twitter:description" content="{og_desc}">
  <meta name="twitter:image" content="{og_image_url}">
  <link rel="canonical" href="{SITE_URL}/">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
</head>
<body style="font-family:'Courier New',monospace;background:#fdf6ee;color:#2d2319;text-align:center;padding:60px 20px">
  <p>redirecting to <a href="/">dollarbets.lol</a>...</p>
  <script>window.location.replace("/");</script>
</body>
</html>"""

        os.makedirs(og_dir, exist_ok=True)
        with open(os.path.join(og_dir, "index.html"), "w") as f:
            f.write(html)
        count += 1

    print(f"[generate] Wrote {count} share pages with OG images")


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

    # 1b. Underdogs (sports) board
    print("[generate] Loading sports boards...")
    sports_boards = load_sports_boards()
    print(f"[generate] Found {len(sports_boards)} sports boards")
    print("[generate] Building the lineup board...")
    generate_lineup_board(sports_boards)

    # Sports sub-boards
    for sub_board in ["underdogs", "ocho", "chalk", "combo-meal"]:
        print(f"[generate] Building {sub_board} board...")
        generate_sports_sub_board(sub_board)

    # 1c. Tier pages (aggregate across all boards)
    print("[generate] Building tier pages...")
    generate_tier_pages(boards, sports_boards)

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

    # 6. Per-bet share pages + OG images
    print("[generate] Building share pages...")
    generate_share_pages(boards)

    # 7. About page
    print("[generate] Building about page...")
    generate_about_page()

    # 7. 404 page
    print("[generate] Building 404 page...")
    generate_404_page()

    # 8. Sitemap + robots.txt
    print("[generate] Building sitemap...")
    sitemap_pages = [
        ("/", 1.0),
        ("/the-lineup/", 0.9),
        ("/underdogs/", 0.8),
        ("/the-ocho/", 0.8),
        ("/chalk/", 0.8),
        ("/combo-meal/", 0.8),
        ("/about/", 0.7),
        ("/guides/", 0.8),
    ]
    for slug in CATEGORIES:
        sitemap_pages.append((f"/{slug}/", 0.8))
    for tier_name in ["respectable", "alive", "heater", "filthy", "generational"]:
        sitemap_pages.append((f"/tier/{tier_name}/", 0.7))
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
    # Add autopsy pages — only those actually written to disk this build.
    # generate_market_autopsies() caps output at 10 pages, but this loop used
    # to list every payout>=20 candidate (~84), putting ~74 phantom /autopsy/
    # URLs (404s) in the sitemap. Gate on file existence so the sitemap can
    # never reference an autopsy page that wasn't generated.
    autopsy_candidates = [b for b in all_bets if b.get("payout", 0) >= 20]
    seen = set()
    for b in autopsy_candidates:
        t = b.get("title", "")
        if t in seen:
            continue
        seen.add(t)
        s = slugify(t)
        if s and os.path.isfile(os.path.join(OUTPUT_DIR, "autopsy", s, "index.html")):
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
                # noindex pages (explicit flag or content-policy denylist) are
                # excluded: don't ask Google to crawl pages we tell it not to index.
                ni, _reason = policy_noindex(cdata)
                if canonical and not ni:
                    priority = 0.7 if cdata.get("format") == "historical_story" else 0.8
                    # Real per-page lastmod from the content's own dates, so the
                    # sitemap stops claiming every URL changed today on every build.
                    lastmod = (cdata.get("last_updated")
                               or cdata.get("publish_date") or "")
                    entry = (canonical, priority, lastmod)
                    if not any(e[0] == canonical for e in sitemap_pages):
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

    # Include the HTML sitemap itself in the XML sitemap so it's indexable.
    sitemap_entry = ("/sitemap/", 0.3)
    if sitemap_entry not in sitemap_pages:
        sitemap_pages.append(sitemap_entry)

    generate_sitemap(sitemap_pages)
    generate_html_sitemap(sitemap_pages)
    generate_robots_txt()

    # Note: referral URL handling is now managed by /go/ serverless redirect
    # No post-processing needed

    print(f"[generate] Done. {len(sitemap_pages)} pages in sitemap.")


if __name__ == "__main__":
    main()
