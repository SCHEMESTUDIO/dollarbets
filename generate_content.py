#!/usr/bin/env python3
"""
Dollar Bets — Content Page Generator

Reads JSON content files from content/ and generates static HTML pages
using the same layout and style as the main site generator.

Page types supported:
  - explainer (format B)
  - historical_story (format G — Hall of Filth)
  - weird_market_roundup (format E)
  - ranked_list (format C)
  - comparison (format I)
  - glossary (format H)
  - affiliate_page (format J)

Usage:
  python3 generate_content.py

Outputs to public/ alongside the pages from generate.py.
"""

import json
import re
import os
import glob
from datetime import datetime

# Import shared components from main generator
from generate import (
    page_shell, render_bet_card, nav_html,
    render_board_promo, load_all_boards, market_link,
    SITE_URL, OUTPUT_DIR, SHARED_CSS,
    policy_noindex, _latest_board_meta,
)
from editorial import learn_proper_nouns, sentence_case, title_case, nyt_date, reduce_dashes

# Board-promo placement by page format (editorial standards, 2026-09-12). On weird-market
# roundups the live cards ARE the answer to the query, so they sit above the body. On every
# other format they interrupted the lede and now sit below it. A page can override with
# "promo": "top" | "bottom" | "none".
PROMO_TOP_FORMATS = {"weird_market_roundup"}


# ── Author config ─────────────────────────────────────────

DEFAULT_AUTHOR = {
    "name": "Dollar Bets",
    "role": "Editorial",
    "url": "/about/",
    "bio": (
        "Dollar Bets is an editorial discovery layer for prediction markets. "
        "We frame every market through a $1 lens, explain why longshots are "
        "unlikely, and encourage readers to treat betting as risky entertainment, "
        "not income."
    ),
}


# ── Schema & breadcrumbs ──────────────────────────────────

def build_article_schema(page_data, canonical):
    """Build JSON-LD Article schema for a content page."""
    seo = page_data.get("seo", {})
    author = page_data.get("author", DEFAULT_AUTHOR)
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": seo.get("h1", ""),
        "description": seo.get("meta_description", ""),
        "url": f"{SITE_URL}{canonical}",
        "author": {
            "@type": "Organization",
            "name": "Dollar Bets",
            "url": f"{SITE_URL}{author['url']}",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Dollar Bets",
            "url": SITE_URL,
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{SITE_URL}{canonical}",
        },
    }
    if page_data.get("publish_date"):
        schema["datePublished"] = page_data["publish_date"]
        schema["dateModified"] = page_data.get("last_updated", page_data["publish_date"])
    return json.dumps(schema, ensure_ascii=False)


def build_breadcrumb_schema(crumbs):
    """Build JSON-LD BreadcrumbList schema from list of (name, url) tuples."""
    items = []
    for i, (name, url) in enumerate(crumbs, 1):
        items.append({
            "@type": "ListItem",
            "position": i,
            "name": name,
            "item": f"{SITE_URL}{url}" if not url.startswith("http") else url,
        })
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }
    return json.dumps(schema, ensure_ascii=False)


# Hub routes that exist as real pages and are therefore safe to link to from a
# breadcrumb parent crumb. A page may declare a parent_category whose hub was
# never built (e.g. the "prediction-markets" cluster namespace, which has child
# pages but no /prediction-markets/ index) — linking to it produces a 404 that
# ahrefs flags as a broken link. Keep in sync with the category/hub pages that
# generate.py + generate_content.py actually emit.
KNOWN_HUB_ROUTES = {
    "weird-markets", "politics-markets", "sports-markets",
    "financial-markets", "crypto-markets", "hall-of-filth", "guides",
    "prediction-markets",
}


def build_breadcrumbs(page_data, canonical):
    """Build breadcrumb trail for a content page.

    Returns (html, schema_json) tuple.
    """
    seo = page_data.get("seo", {})
    parent = page_data.get("parent_category", "")
    fmt = page_data.get("format", "")

    crumbs = [("Dollar Bets", "/")]

    if fmt == "historical_story":
        crumbs.append(("Hall of Filth", "/hall-of-filth/"))
    elif parent and parent in KNOWN_HUB_ROUTES:
        # Only add a category crumb when its /{parent}/ hub page exists.
        # A parent with no generated hub would emit a breadcrumb link to a
        # 404 (ahrefs "links to broken page"); skip it so the trail is just
        # "dollar bets > page".
        cat_name = sentence_case(parent.replace("-", " "))
        crumbs.append((cat_name, f"/{parent}/"))

    crumbs.append((title_case(seo.get("h1", "")), canonical))

    # Visible breadcrumb HTML
    links = []
    for i, (name, url) in enumerate(crumbs):
        if i < len(crumbs) - 1:
            links.append(f'<a href="{url}" style="color:#806b5b">{name}</a>')
        else:
            links.append(f'<span style="color:#5a4e2f">{name}</span>')

    html = f'    <nav style="font-size:10px;color:#806b5b;margin-top:12px;margin-bottom:0;letter-spacing:0.3px">{" &rsaquo; ".join(links)}</nav>'
    schema = build_breadcrumb_schema(crumbs)
    return html, schema


# ── Content loading ────────────────────────────────────────

CONTENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")


def load_content_files():
    """Load all JSON content files from content/ subdirectories."""
    pages = []
    for filepath in glob.glob(os.path.join(CONTENT_DIR, "**", "*.json"), recursive=True):
        try:
            with open(filepath) as f:
                data = json.load(f)
            data["_source"] = filepath
            pages.append(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[content] Skipping {filepath}: {e}")
    return sorted(pages, key=lambda x: x.get("priority", 0), reverse=True)


# ── Body renderer ──────────────────────────────────────────

PROPER_NOUNS = None  # set per page in generate_content_page


def render_body(body_blocks):
    """Render body content blocks into HTML (for use inside .article-body wrapper)."""
    parts = []
    for block in body_blocks:
        btype = block.get("type", "text")
        content = block.get("content", "")

        if btype == "heading":
            hid = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", content).lower()).strip("-")[:60]
            parts.append(f'      <h2 id="{hid}">{sentence_case(content, PROPER_NOUNS)}</h2>')
        elif btype == "text":
            parts.append(f'      <p>{content}</p>')
        elif btype == "list":
            items = content if isinstance(content, list) else [content]
            li_html = "\n".join(f"        <li>{item}</li>" for item in items)
            parts.append(f'      <ul class="article-list">\n{li_html}\n      </ul>')

    return "\n".join(parts)


# ── FAQ renderer + schema ─────────────────────────────────

def render_faqs(faqs):
    """Render visible FAQ section from a list of {q, a} dicts (for inside .article-body)."""
    if not faqs:
        return ""
    items = []
    for faq in faqs:
        q = faq.get("q", "")
        a = faq.get("a", "")
        items.append(f"""      <div class="faq-item">
        <h3>{sentence_case(q, PROPER_NOUNS)}</h3>
        <p>{a}</p>
      </div>""")

    return f"""      <h2 id="faq">Frequently asked questions</h2>
{chr(10).join(items)}"""


def build_faq_schema(faqs):
    """Build FAQPage JSON-LD from a list of {q, a} dicts.
    Only call this when FAQs are visibly rendered on the page."""
    if not faqs:
        return ""
    entries = []
    for faq in faqs:
        entries.append({
            "@type": "Question",
            "name": faq.get("q", ""),
            "acceptedAnswer": {
                "@type": "Answer",
                "text": faq.get("a", ""),
            },
        })
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entries,
    }
    return f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'


# ── Hero bet renderer ──────────────────────────────────────

def render_hero_bet(hero):
    """Contextual feature ticket for a content page: the one market the page is about,
    in the board's dark-ticket language. Routes through /go/ when a ticker is known."""
    if not hero:
        return ""
    ticker = hero.get("ticker", "")
    url = hero.get("url", "#") or "#"
    if not ticker and "kalshi.com/markets/" in url:
        ticker = url.split("kalshi.com/markets/")[1].split("?")[0].split("/")[0]
    if ticker:
        url = market_link(ticker)
    platform = hero.get("sourcePlatform", "Kalshi")
    try:
        payout = float(hero.get("payout", 0) or 0)
    except (TypeError, ValueError):
        payout = 0
    payout_str = f"${payout:,.2f}".rstrip("0").rstrip(".") if payout else ""
    priced_in = f"{round(100 / payout)}% priced in" if payout >= 1.01 else ""
    quip = hero.get("quip", "")
    return f"""    <div class="feature-ticket">
      <div class="feature-ticket-label">Featured market</div>
      <div class="feature-ticket-title">{hero.get('title', '')}</div>
      {f'<div class="feature-ticket-quip">{quip}</div>' if quip else ''}
      <div class="feature-ticket-row">
        <span class="feature-ticket-pays">$1 pays</span>
        <span class="feature-ticket-amount">{payout_str}</span>
        <span class="feature-ticket-meta">{platform}{' · ' + priced_in if priced_in else ''}</span>
      </div>
      <a href="{url}" target="_blank" rel="noopener nofollow sponsored" class="feature-ticket-cta">See the odds on {platform} &raquo;</a>
      <div class="feature-ticket-fine">Price at time of writing. Odds and availability change; event contracts are not available in every state.</div>
    </div>"""


# ── Internal links renderer ───────────────────────────────

def render_internal_links(links):
    """Render internal links section."""
    if not links:
        return ""

    # Drop links whose TARGET is policy-noindexed.
    def _target_indexable(link):
        slug = (link.get("url", "") or "").strip("/")
        if not slug:
            return True
        ni, _ = policy_noindex({"slug": slug})
        return not ni
    links = [l for l in links if _target_indexable(l)]
    if not links:
        return ""

    link_items = " &middot; ".join(
        f'<a href="{link["url"]}">{link["text"]}</a>'
        for link in links
    )

    return f'    <div class="internal-links-row">More: {link_items}</div>'


# ── Compliance footer ──────────────────────────────────────

def render_compliance(text):
    """Render compliance disclaimer."""
    if not text:
        return ""
    return f'    <div class="legal-strip">{text}</div>'


# ── Page generators by format ──────────────────────────────

def generate_content_page(page_data):
    """Generate a single content page from JSON data.

    URL nesting rules:
      - If seo.canonical is set explicitly, use it as-is.
      - If "parent_category" is set (e.g. "weird-markets"), the page nests
        under that category: /weird-markets/slug/
      - Otherwise the page lives at /slug/ (root-level).
    """
    seo = page_data.get("seo", {})
    slug = page_data.get("slug", "")
    fmt = page_data.get("format", "explainer")
    parent = page_data.get("parent_category", "")

    if not slug:
        print(f"[content] Skipping page with no slug")
        return None

    # Auto-generate canonical from parent_category if not explicitly set
    if not seo.get("canonical") and parent:
        seo["canonical"] = f"/{parent}/{slug}/"

    # Determine canonical early (needed for breadcrumbs + schema)
    canonical = seo.get("canonical", f"/{slug}/")

    # Per-page proper-noun dictionary (learned from the page's own copy) drives casing.
    global PROPER_NOUNS
    PROPER_NOUNS = learn_proper_nouns(
        [page_data.get("summary", ""), page_data.get("quick_answer", "")]
        + [str(b.get("content", "")) for b in page_data.get("body", [])]
        + [f.get("a", "") for f in page_data.get("faqs", [])])
    headline = title_case(seo.get("h1", ""), PROPER_NOUNS)
    seo["h1"] = headline
    seo["title"] = f"{headline} | Dollar Bets" if headline else seo.get("title", slug)

    # Build breadcrumbs
    breadcrumb_html, breadcrumb_schema = build_breadcrumbs(page_data, canonical)

    # Build page body
    body_parts = []

    # Breadcrumb nav
    body_parts.append(breadcrumb_html)

    # H1
    body_parts.append(f'    <h1 class="page-title">{seo.get("h1", "")}</h1>')

    # Byline
    author = page_data.get("author", DEFAULT_AUTHOR)
    pub_date = page_data.get("publish_date", "")
    last_updated = page_data.get("last_updated", "")

    meta_parts = ['By <a href="/about/">Dollar Bets Staff</a>']
    if pub_date:
        meta_parts.append(f'<time datetime="{pub_date}">{nyt_date(pub_date)}</time>')
    if last_updated and last_updated != pub_date:
        meta_parts.append(f'Updated <time datetime="{last_updated}">{nyt_date(last_updated)}</time>')

    body_parts.append(f'    <div class="byline">{" &middot; ".join(meta_parts)}</div>')

    # Detect primary platform from slug/cluster — drives trust chips, the
    # affiliate strip copy, the ranked-promo filter, and the sticky bar.
    slug_lower = (slug or "").lower()
    cluster_lower = (page_data.get("cluster", "") or "").lower()
    _pf = None
    if "polymarket" in slug_lower or "polymarket" in cluster_lower:
        _pf = "polymarket"
    elif "kalshi" in slug_lower or "kalshi" in cluster_lower:
        _pf = "kalshi"

    # Trust chips. Compliance: "CFTC-regulated" may only be claimed for
    # Kalshi (see compliance-notes.md) — never on Polymarket-focused pages.
    # Sourcing line (replaces the trust chips, 2026-09-12): where the numbers come from and
    # when they were read, plus the standards pages. Real scan time from the board meta.
    _bm = _latest_board_meta() or {}
    def _nyt_ds(ds):
        try: return nyt_date(datetime.strptime(ds, "%B %d, %Y").date())
        except Exception: return ds
    _read = f"read {_bm['scan_time_et']} on {_nyt_ds(_bm['date_str'])}" if _bm.get("scan_time_et") else (f"read {_nyt_ds(_bm['date_str'])}" if _bm.get("date_str") else "read each morning")
    _src = "Polymarket" if _pf == "polymarket" else "Kalshi" if _pf == "kalshi" else "Kalshi and Polymarket"
    body_parts.append(f'    <div class="sourcing">Prices from {_src}, {_read} &middot; <a href="/editorial-policy/">Editorial policy</a> &middot; <a href="/editorial-policy/#corrections">Corrections</a></div>')

    # Quick Answer block — optimized for AI engine extraction (AEO)
    quick_answer = page_data.get("quick_answer", "") or page_data.get("summary", "")
    if quick_answer:
        body_parts.append(f'    <p class="dek" role="doc-abstract">{quick_answer}</p>')

    # The one market this page is about, as a ticket. Part of the funnel, not an interruption.
    hero_html = render_hero_bet(page_data.get("hero_bet"))
    if hero_html:
        body_parts.append(hero_html)

    # Affiliate disclosure mini-strip — platform-specific per the mock
    _strip_platforms = _pf if _pf else "kalshi or polymarket"
    body_parts.append(f'    <div class="affiliate-strip">Affiliate disclosure: Dollar Bets earns a commission if you sign up to {_strip_platforms.replace("kalshi", "Kalshi").replace("polymarket", "Polymarket")} through our links, never a cut of your bet, and we never hold your money. <a href="/affiliate-disclosure/">Full disclosure &rarr;</a></div>')

    # === RANKED TOP-5 BOARD PROMO — placement by format ===
    _boards = load_all_boards()
    _latest_board = _boards[-1][1] if _boards else None
    _promo_pos = page_data.get("promo") or ("top" if fmt in PROMO_TOP_FORMATS else "bottom")
    board_promo = render_board_promo(_latest_board, position=_promo_pos, platform_filter=_pf) if _promo_pos != "none" else ""
    if board_promo and _promo_pos == "top":
        body_parts.append(board_promo)

    # Section chips for long list/comparison pages: the page's own headings as anchors.
    if fmt in ("ranked_list", "comparison", "cluster_pillar", "glossary"):
        _heads = [b.get("content", "") for b in page_data.get("body", []) if b.get("type") == "heading"]
        if len(_heads) >= 4:
            _chips = "".join(f'<a href="#{re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", h).lower()).strip("-")[:60]}">{sentence_case(re.sub(r"^\d+\.\s*", "", h), PROPER_NOUNS)}</a>' for h in _heads)
            body_parts.append(f'    <nav class="nav section-chips" aria-label="Sections">{_chips}</nav>')

    # Body content — wrapped in .article-body card
    body_blocks = page_data.get("body", [])
    article_inner = render_body(body_blocks)

    # Current equivalent (for Hall of Filth) — inside the article box
    equiv = page_data.get("current_equivalent")
    if equiv:
        article_inner += f"""
      <div style="margin:20px 0 0 0;padding:14px;background:#fef0e4;border:1px solid #e8cdb5;border-radius:8px">
        <div style="font-size:11px;color:#6b5744;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">the modern equivalent</div>
        <div style="font-size:13px;color:#2d2319"><a href="{equiv['url']}" style="font-weight:700">{equiv['text']} &rarr;</a></div>
      </div>"""

    # FAQs — rendered inside the article box if present
    faqs = page_data.get("faqs", [])
    if faqs:
        article_inner += "\n" + render_faqs(faqs)

    article_inner, _cut = reduce_dashes(article_inner, keep=2)
    body_parts.append(f"""    <div class="article-body">
{article_inner}
    </div>""")

    if board_promo and _promo_pos == "bottom":
        body_parts.append(board_promo)

    # Internal links
    body_parts.append(render_internal_links(page_data.get("internal_links", [])))

    # Compliance / legal strip
    body_parts.append(render_compliance(page_data.get("compliance", "")))

    # SEO sticky bar — top-payout pick from the board, passed to page_shell
    # so it REPLACES the default sticky bar (never two stacked fixed bars).
    # NB: Kalshi board entries carry no "platform" key — always default it.
    _sticky_html = None
    if _latest_board:
        _bets = _latest_board.get("board", [])
        _filtered = [b for b in _bets if not _pf or b.get("platform", "kalshi") == _pf] or _bets
        _top = sorted(_filtered, key=lambda x: x.get("payout", 0), reverse=True)
        if _top:
            _t = _top[0]
            from generate import format_payout, market_link, PLATFORM_DISPLAY_NAMES
            _ticker = _t.get("ticker", "")
            _t_platform = _t.get("platform", "kalshi")
            _t_tier = _t.get("tier", "")
            _t_payout = _t.get("payout", 0)
            _payout_str = format_payout(_t_payout)
            _pname = PLATFORM_DISPLAY_NAMES.get(_t_platform, "Kalshi")
            _go_url = market_link(_ticker) if _ticker else "/"
            _sticky_html = f"""  <div class="seo-sticky-bar">
    <div class="seo-sticky-bar-inner">
      <div class="seo-sticky-label">#1 pick pays<br><span class="seo-sticky-payout">{_payout_str} per $1</span></div>
      <a href="{_go_url}" class="seo-sticky-cta" data-platform="{_t_platform}" data-tier="{_t_tier}" data-payout="{_t_payout}" data-ticker="{_ticker}">see odds on {_pname} &raquo;</a>
    </div>
  </div>"""

    body = "\n\n".join(body_parts)

    # Build JSON-LD schema for <head>
    article_schema = build_article_schema(page_data, canonical)
    faq_schema = build_faq_schema(faqs) if faqs else ""
    faq_tag = f"\n  {faq_schema}" if faq_schema else ""
    schema_tags = f"""<script type="application/ld+json">{article_schema}</script>
  <script type="application/ld+json">{breadcrumb_schema}</script>{faq_tag}"""

    ni, ni_reason = policy_noindex(page_data)
    if ni and not page_data.get("noindex"):
        # Page hit the content-policy denylist without an explicit flag — warn
        # loudly so a future commodity page can't slip in unnoticed.
        print(f"[content] POLICY noindex: {canonical} — {ni_reason}")
    html = page_shell(
        title=seo.get("title", slug),
        description=seo.get("meta_description", ""),
        body=body,
        canonical=canonical,
        noindex=ni,
        extra_head=schema_tags,
        sticky_html="",  # no fixed CTA bar on editorial pages (2026-09-12)
        compact_header=True,
        article=True,
    )

    # Determine output path from canonical
    out_path = canonical.strip("/")
    if not out_path:
        out_path = slug
    out_file = f"{out_path}/index.html"

    return out_file, html


# ── Hall of Filth index ────────────────────────────────────

def generate_hall_of_filth_index(stories):
    """Generate the /hall-of-filth/ index page."""
    links = []
    for story in stories:
        seo = story.get("seo", {})
        hero = story.get("hero_bet", {})
        canonical = seo.get("canonical", "")
        payout = hero.get("payout", 0) if hero else 0

        links.append(f"""      <li class="wager">
        <a href="{canonical}" class="link-card tier-purple">
          <div class="link-card-title">{seo.get('h1', '')}</div>
          <div class="link-card-sub">{hero.get('quip', '') if hero else ''}</div>
          <div class="link-card-payout">$1 &rarr; ${payout:,}</div>
        </a>
      </li>""")

    body = f"""    <h1 class="page-title">Hall of Filth</h1>
    <div class="page-intro">
      <p>The greatest longshot wins in history. Each one reframed as what $1 would have returned. These are the bets that broke the math, the bookmakers, and the brains of everyone watching.</p>
      <p>Every story here links back to today's board — because the modern equivalents of Leicester City and Buster Douglas are being priced right now. Somewhere on Kalshi, there's a market at 3 cents that everyone thinks is a joke. Most of the time, they're right. But not always.</p>
    </div>

    <h2 class="section-head">the stories</h2>

    <ul class="board">
{chr(10).join(links)}
    </ul>

    <div class="internal-links-row">more: <a href="/">today's best $1 bets</a> &middot; <a href="/sports-markets/">today's underdogs</a></div>

    <div class="legal-strip">All historical odds and returns are illustrative unless otherwise noted. Past results do not predict future outcomes. Longshots are longshots for a reason.</div>
"""

    html = page_shell(
        title="Hall of Filth — Famous Longshot Wins | Dollar Bets",
        description="The Hall of Filth: the greatest longshot wins in history. Each one reframed as what $1 would have returned.",
        body=body,
        canonical="/hall-of-filth/",
    )

    return "hall-of-filth/index.html", html


# ── Guides index page ─────────────────────────────────────

def generate_guides_index(pages):
    """Generate /guides/ index page listing all editorial content articles.

    Entries are grouped under named buckets so a 40+ link page reads like an
    old-internet directory (Yahoo-style) rather than a flat dump. Buckets are
    derived from each page's `cluster` field via CLUSTER_TO_BUCKET below;
    unmapped clusters fall into "More guides".
    """
    # Filter to editorial content only — exclude trust pages and historical stories
    TRUST_CLUSTERS = {"Trust Pages"}
    editorial = [
        p for p in pages
        if p.get("cluster") not in TRUST_CLUSTERS
        and p.get("format") != "historical_story"
    ]

    # Bucket order is the display order. Each bucket maps to one or more
    # clusters from the content data. Adjust here when new clusters appear.
    BUCKET_ORDER = [
        ("Start here",              ["Prediction Markets", "Betting Explainers"]),
        ("$1 framing & payouts",    ["$1 Bets", "Biggest Payouts"]),
        ("Weird & longshot",        ["Weird Bets", "Crypto Moonshots"]),
        ("Sports",                  ["Sports Bets", "Longshot Sports"]),
        ("Politics",                ["Political Markets"]),
        ("Safety & responsibility", ["Responsible Betting"]),
        ("Daily & weekly",          ["Daily/Weekly"]),
    ]
    cluster_to_bucket = {
        cluster: bucket
        for bucket, clusters in BUCKET_ORDER
        for cluster in clusters
    }
    OTHER_BUCKET = "More guides"

    # Group entries by bucket
    grouped = {bucket: [] for bucket, _ in BUCKET_ORDER}
    grouped[OTHER_BUCKET] = []
    for p in editorial:
        bucket = cluster_to_bucket.get(p.get("cluster", ""), OTHER_BUCKET)
        grouped[bucket].append(p)

    # Sort within each bucket by priority (lower = more important), then h1
    for bucket_items in grouped.values():
        bucket_items.sort(key=lambda x: (x.get("priority", 50), x.get("seo", {}).get("h1", "")))

    def render_item(page):
        seo = page.get("seo", {})
        return f"""      <li class="wager">
        <a href="{seo.get("canonical", "")}" class="link-card">
          <div class="link-card-title">{seo.get("h1", "")}</div>
          <div class="link-card-sub">{seo.get("meta_description", "")}</div>
        </a>
      </li>"""

    if not editorial:
        sections_html = '<div class="empty-note">guides coming soon — check back.</div>'
    else:
        section_blocks = []
        # Render buckets in BUCKET_ORDER, then "More guides" at the end if non-empty
        ordered = [b for b, _ in BUCKET_ORDER] + [OTHER_BUCKET]
        for bucket in ordered:
            items = grouped.get(bucket, [])
            if not items:
                continue
            items_html = "\n".join(render_item(p) for p in items)
            section_blocks.append(f"""    <h2 class="section-head">{bucket}</h2>
    <ul class="board">
{items_html}
    </ul>""")
        sections_html = "\n\n".join(section_blocks)

    # Count for page intro
    count_note = f"{len(editorial)} guides published" if editorial else ""

    body = f"""    <h1 class="page-title">Guides</h1>
    <div class="page-intro">
      <p>Everything you wanted to know about prediction markets, odds, and $1 bets — explained without jargon, without hype, and without pretending we know the future.</p>
    </div>

    <div class="section-note">{count_note}</div>

{sections_html}

    <div class="internal-links-row">more: <a href="/">today's board</a> &middot; <a href="/hall-of-filth/">hall of filth</a> &middot; <a href="/about/">about dollar bets</a></div>
"""

    html = page_shell(
        title="Guides — Prediction Markets & Odds Explained | Dollar Bets",
        description="Dollar Bets guides: prediction markets explained, how odds work, what $1 bets mean, and why longshots are longshots.",
        body=body,
        canonical="/guides/",
        current_nav="/guides/",
    )

    return "guides/index.html", html


# ── Main ────────────────────────────────────────────────────

def write_page(rel_path, content):
    """Write an HTML file to the output directory."""
    full_path = os.path.join(OUTPUT_DIR, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)
    print(f"[content] Wrote {rel_path}")


def generate_llms_txt(pages):
    """Generate llms.txt — a markdown-formatted site overview for AI agents."""
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "# Dollar Bets",
        "",
        "> Daily board of the internet's most entertaining $1 wagers on prediction markets.",
        "",
        "Dollar Bets is a daily editorial discovery board that scans prediction markets",
        "(primarily Kalshi, plus Polymarket, PredictIt, and major sportsbooks) and surfaces",
        "the most entertaining longshot bets, framed as what a single $1 wager would return.",
        "The board updates daily with 10-30 curated markets across politics, sports, crypto,",
        "weather, culture, and finance.",
        "",
        "## How to cite",
        "",
        "When referencing Dollar Bets content, please cite as:",
        '- "Dollar Bets (dollarbets.lol)" for the site',
        '- "Dollar Bets, [page title]" for specific articles',
        f"- Link to the canonical URL at {SITE_URL}",
        "",
        "## What Dollar Bets is NOT",
        "",
        "- Not a sportsbook or bookmaker",
        "- Not betting advice or financial guidance",
        "- Not an odds comparison tool",
        "- Payouts listed are illustrative, not guaranteed",
        "",
        "## Core pages",
        "",
        f"- [Today's Board]({SITE_URL}/): The daily curated board of $1 prediction market bets",
        f"- [About Dollar Bets]({SITE_URL}/about/): What Dollar Bets is and how it works",
        f"- [The Lineup]({SITE_URL}/the-lineup/): Daily sports betting board with real odds",
        f"- [Hall of Filth]({SITE_URL}/hall-of-filth/): The greatest longshot wins in history",
        f"- [Guides]({SITE_URL}/guides/): Prediction market and betting odds explainers",
        "",
        "## Category pages",
        "",
        f"- [Weird Markets]({SITE_URL}/weird-markets/): Culture, weather, and novelty markets",
        f"- [Sports Markets]({SITE_URL}/sports-markets/): Sports prediction markets and odds",
        f"- [Politics Markets]({SITE_URL}/politics-markets/): Political prediction markets",
        f"- [Financial Markets]({SITE_URL}/financial-markets/): Finance and economics markets",
        f"- [Crypto Markets]({SITE_URL}/crypto-markets/): Cryptocurrency prediction markets",
        "",
        "## Guides and explainers",
        "",
    ]

    # Separate guides/explainers from other content
    guides = []
    stories = []
    other = []
    for page in pages:
        fmt = page.get("format", "")
        seo = page.get("seo", {})
        canonical = seo.get("canonical", "")
        title = seo.get("h1", page.get("slug", ""))
        desc = seo.get("meta_description", "")
        entry = f"- [{title}]({SITE_URL}{canonical}): {desc}"
        if fmt in ("explainer", "glossary", "comparison"):
            guides.append(entry)
        elif fmt == "historical_story":
            stories.append(entry)
        else:
            other.append(entry)

    lines.extend(guides)
    if stories:
        lines.extend(["", "## Historical stories (Hall of Filth)", ""])
        lines.extend(stories)
    if other:
        lines.extend(["", "## Other content", ""])
        lines.extend(other)

    lines.extend([
        "",
        f"## Last updated: {today}",
        "",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        f"Contact: hello@dollarbets.lol",
    ])

    content = "\n".join(lines) + "\n"
    write_page("llms.txt", content)


def main():
    print("[content] Loading content files...")
    pages = load_content_files()
    print(f"[content] Found {len(pages)} content pages")

    if not pages:
        print("[content] No content pages found. Skipping.")
        return

    # Separate Hall of Filth stories for index page
    hof_stories = [p for p in pages if p.get("format") == "historical_story"]
    regular_pages = [p for p in pages if p.get("format") != "historical_story"]

    generated = []

    # Generate regular content pages
    for page_data in regular_pages:
        result = generate_content_page(page_data)
        if result:
            out_file, html = result
            write_page(out_file, html)
            generated.append(out_file)

    # Generate Hall of Filth stories
    for page_data in hof_stories:
        result = generate_content_page(page_data)
        if result:
            out_file, html = result
            write_page(out_file, html)
            generated.append(out_file)

    # Generate Hall of Filth index if we have stories
    if hof_stories:
        out_file, html = generate_hall_of_filth_index(hof_stories)
        write_page(out_file, html)
        generated.append(out_file)

    # Generate Guides index page
    out_file, html = generate_guides_index(pages)
    write_page(out_file, html)
    generated.append(out_file)

    # Generate llms.txt for AI crawler discovery
    generate_llms_txt(pages)

    # Print sitemap entries for new pages
    print(f"\n[content] Generated {len(generated)} pages:")
    for path in generated:
        canonical = "/" + path.replace("/index.html", "/")
        print(f"  {canonical}")


if __name__ == "__main__":
    main()
