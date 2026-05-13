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
import os
import glob
from datetime import datetime

# Import shared components from main generator
from generate import (
    page_shell, render_bet_card, nav_html,
    render_board_promo, load_all_boards,
    SITE_URL, OUTPUT_DIR, SHARED_CSS,
)


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
            "@type": "Person",
            "name": author["name"],
            "url": f"{SITE_URL}{author['url']}",
            "jobTitle": author.get("role", ""),
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


def build_breadcrumbs(page_data, canonical):
    """Build breadcrumb trail for a content page.

    Returns (html, schema_json) tuple.
    """
    seo = page_data.get("seo", {})
    parent = page_data.get("parent_category", "")
    fmt = page_data.get("format", "")

    crumbs = [("dollar bets", "/")]

    if fmt == "historical_story":
        crumbs.append(("hall of filth", "/hall-of-filth/"))
    elif parent:
        # Use parent category name from slug
        cat_name = parent.replace("-", " ")
        crumbs.append((cat_name, f"/{parent}/"))

    crumbs.append((seo.get("h1", "").lower(), canonical))

    # Visible breadcrumb HTML
    links = []
    for i, (name, url) in enumerate(crumbs):
        if i < len(crumbs) - 1:
            links.append(f'<a href="{url}" style="color:#888">{name}</a>')
        else:
            links.append(f'<span style="color:#555">{name}</span>')

    html = f'    <nav style="font-size:10px;color:#7a6e5f;margin-bottom:10px;letter-spacing:0.3px">{" &rsaquo; ".join(links)}</nav>'
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

def render_body(body_blocks):
    """Render body content blocks into HTML."""
    parts = []
    for block in body_blocks:
        btype = block.get("type", "text")
        content = block.get("content", "")

        if btype == "heading":
            parts.append(f'    <h2 class="section-head">{content}</h2>')
        elif btype == "text":
            parts.append(f'    <div class="page-intro"><p>{content}</p></div>')
        elif btype == "list":
            items = content if isinstance(content, list) else [content]
            li_html = "\n".join(f"      <li>{item}</li>" for item in items)
            parts.append(f'    <ul style="font-family:-apple-system,\'Segoe UI\',Helvetica,Arial,sans-serif;font-size:15px;color:#3d2e1f;line-height:1.7;margin:0 0 14px 20px;list-style:disc">\n{li_html}\n    </ul>')

    return "\n\n".join(parts)


# ── FAQ renderer + schema ─────────────────────────────────

def render_faqs(faqs):
    """Render visible FAQ section from a list of {q, a} dicts."""
    if not faqs:
        return ""
    items = []
    for faq in faqs:
        q = faq.get("q", "")
        a = faq.get("a", "")
        items.append(f"""      <div style="margin-bottom:14px">
        <h3 style="font-size:14px;font-weight:700;color:#2d2319;margin-bottom:4px">{q}</h3>
        <div class="page-intro"><p>{a}</p></div>
      </div>""")

    return f"""    <h2 class="section-head">frequently asked questions</h2>
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
    """Render a hero betting slip for a content page."""
    if not hero:
        return ""

    note = hero.get("note", "")
    note_html = f'<div style="font-size:10px;color:#7a6e5f;margin-top:4px;font-style:italic">{note}</div>' if note else ""

    # Optional disclaimer fields
    disclaimer_parts = []
    if hero.get("sourcePlatform"):
        disclaimer_parts.append(f'Source: {hero["sourcePlatform"]}.')
    disclaimer_parts.append("Odds and availability may change.")
    if hero.get("marketType") == "prediction_market":
        disclaimer_parts.append("Event contracts may not be available in all jurisdictions.")
    else:
        disclaimer_parts.append("Check platform terms before taking action.")
    disclaimer = " ".join(disclaimer_parts)

    note_html_inv = ""
    if note:
        note_html_inv = f'<div style="font-size:10px;color:rgba(255,255,255,0.6);margin-top:4px;font-style:italic">{note}</div>'

    return f"""    <div style="margin:18px 0;padding:14px;background:#e8642c;border-radius:6px">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:rgba(255,255,255,0.7);margin-bottom:4px">featured market</div>
      <div style="font-size:15px;font-weight:700;color:#fff;margin-bottom:4px">{hero.get('title', '')}</div>
      <div style="font-size:14px;font-weight:700;color:#ffecd6">$1 &rarr; ${hero.get('payout', 0):,}</div>
      <div style="font-size:11.5px;color:rgba(255,255,255,0.65);font-style:italic;margin-top:4px">{hero.get('quip', '')}</div>
      {note_html_inv}
      <div style="font-size:9px;color:rgba(255,255,255,0.45);margin-top:6px;line-height:1.5">{disclaimer}</div>
    </div>"""


# ── Internal links renderer ───────────────────────────────

def render_internal_links(links):
    """Render internal links section."""
    if not links:
        return ""

    link_items = " · ".join(
        f'<a href="{link["url"]}" style="color:#666">{link["text"]}</a>'
        for link in links
    )

    return f"""    <div style="margin:20px 0;padding:12px;border-top:1px solid #e8e7e0;font-size:11px;color:#6b5744">
      more: {link_items}
    </div>"""


# ── Compliance footer ──────────────────────────────────────

def render_compliance(text):
    """Render compliance disclaimer."""
    if not text:
        return ""
    return f'    <div style="font-size:10px;color:#b0afa8;line-height:1.6;margin:14px 0">{text}</div>'


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

    # Build breadcrumbs
    breadcrumb_html, breadcrumb_schema = build_breadcrumbs(page_data, canonical)

    # Build page body
    body_parts = []

    # Breadcrumb nav
    body_parts.append(breadcrumb_html)

    # H1
    body_parts.append(f'    <h1 class="page-title">{seo.get("h1", "")}</h1>')

    # Byline + date line
    author = page_data.get("author", DEFAULT_AUTHOR)
    pub_date = page_data.get("publish_date", "")
    last_updated = page_data.get("last_updated", "")

    meta_parts = []
    meta_parts.append(f'by <a href="{author["url"]}" style="color:#555">{author["name"]}</a>')
    if pub_date:
        meta_parts.append(pub_date)
    if last_updated and last_updated != pub_date:
        meta_parts.append(f'updated {last_updated}')

    body_parts.append(f'    <div class="date-line" style="margin-bottom:14px">{" · ".join(meta_parts)}</div>')

    # Quick Answer block — optimized for AI engine extraction (AEO)
    quick_answer = page_data.get("quick_answer", "")
    if quick_answer:
        body_parts.append(f'    <div class="quick-answer" style="font-size:13.5px;color:#2d2319;line-height:1.7;margin:10px 0 16px 0;padding:12px 14px;border-left:3px solid #e8642c;background:#fff;border:1px solid #e8e7e0;border-radius:3px" role="doc-abstract"><strong>Quick answer:</strong> {quick_answer}</div>')
    else:
        # Fallback to summary as tl;dr if no quick_answer
        summary = page_data.get("summary", "")
        if summary:
            body_parts.append(f'    <div style="font-size:13px;color:#333;line-height:1.7;margin:10px 0 16px 0;padding:10px 12px;border-left:3px solid #e8642c;background:#fff;border:1px solid #e8e7e0;border-left:3px solid #e8642c;border-radius:3px"><strong>tl;dr:</strong> {summary}</div>')

    # Hero bet
    hero = page_data.get("hero_bet")
    if hero:
        body_parts.append(render_hero_bet(hero))

    # === TODAY'S BOARD PROMO (top position) ===
    # Load board data once, reuse for both placements
    _boards = load_all_boards()
    _latest_board = _boards[-1][1] if _boards else None
    top_promo = render_board_promo(_latest_board, position="top")
    if top_promo:
        body_parts.append(top_promo)

    # Body content — wrapped in a white card for readability
    body_blocks = page_data.get("body", [])
    article_inner = render_body(body_blocks)

    # Current equivalent (for Hall of Filth) — inside the article box
    equiv = page_data.get("current_equivalent")
    if equiv:
        article_inner += f"""\n\n    <div style="margin:20px 0 0 0;padding:14px;background:#f5f4ef;border:1px solid #e8e7e0;border-radius:3px">
      <div style="font-size:11px;color:#6b5744;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">the modern equivalent</div>
      <div style="font-size:13px;color:#333"><a href="{equiv['url']}" style="color:#333;font-weight:700">{equiv['text']} &rarr;</a></div>
    </div>"""

    # FAQs — rendered inside the article box if present
    faqs = page_data.get("faqs", [])
    if faqs:
        article_inner += "\n\n" + render_faqs(faqs)

    body_parts.append(f"""    <div style="background:#fff;border:1.5px solid #e8e7e0;border-radius:8px;padding:20px 18px;margin:16px 0">
{article_inner}
    </div>""")

    # Internal links
    body_parts.append(render_internal_links(page_data.get("internal_links", [])))

    # === TODAY'S BOARD PROMO (bottom position) ===
    bottom_promo = render_board_promo(_latest_board, position="bottom")
    if bottom_promo:
        body_parts.append(bottom_promo)

    # Compliance
    body_parts.append(render_compliance(page_data.get("compliance", "")))

    body = "\n\n".join(body_parts)

    # Build JSON-LD schema for <head>
    article_schema = build_article_schema(page_data, canonical)
    faq_schema = build_faq_schema(faqs) if faqs else ""
    faq_tag = f"\n  {faq_schema}" if faq_schema else ""
    schema_tags = f"""<script type="application/ld+json">{article_schema}</script>
  <script type="application/ld+json">{breadcrumb_schema}</script>{faq_tag}"""

    html = page_shell(
        title=seo.get("title", slug),
        description=seo.get("meta_description", ""),
        body=body,
        canonical=canonical,
        extra_head=schema_tags,
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
        <a href="{canonical}" style="display:block; padding:12px;">
          <span class="wager-emoji">🟪</span>
          <span class="wager-body">
            <span class="wager-title">{seo.get('h1', '')}</span>
            <span class="wager-payout">$1 &rarr; ${payout:,}</span>
            <span class="wager-quip">{hero.get('quip', '') if hero else ''}</span>
          </span>
        </a>
      </li>""")

    body = f"""    <h1 class="page-title">hall of filth</h1>
    <div class="page-intro">
      <p>The greatest longshot wins in history. Each one reframed as what $1 would have returned. These are the bets that broke the math, the bookmakers, and the brains of everyone watching.</p>
      <p>Every story here links back to today's board — because the modern equivalents of Leicester City and Buster Douglas are being priced right now. Somewhere on Kalshi, there's a market at 3 cents that everyone thinks is a joke. Most of the time, they're right. But not always.</p>
    </div>

    <h2 class="section-head">the stories</h2>

    <ul class="board">
{chr(10).join(links)}
    </ul>

    <div style="margin:20px 0;padding:12px;border-top:1px solid #e8e7e0;font-size:11px;color:#6b5744">
      more: <a href="/" style="color:#666">today's best $1 bets</a> · <a href="/sports-markets/" style="color:#666">today's underdogs</a>
    </div>

    <div style="font-size:10px;color:#b0afa8;line-height:1.6;margin:14px 0">All historical odds and returns are illustrative unless otherwise noted. Past results do not predict future outcomes. Longshots are longshots for a reason.</div>
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
        <a href="{seo.get("canonical", "")}" style="display:block; padding:12px;">
          <span class="wager-body">
            <span class="wager-title">{seo.get("h1", "")}</span>
            <span class="wager-quip">{seo.get("meta_description", "")}</span>
          </span>
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

    body = f"""    <h1 class="page-title">guides</h1>
    <div class="page-intro">
      <p>Everything you wanted to know about prediction markets, odds, and $1 bets — explained without jargon, without hype, and without pretending we know the future.</p>
    </div>

    <div class="section-note">{count_note}</div>

{sections_html}

    <div style="margin:20px 0;padding:12px;border-top:1px solid #e8e7e0;font-size:11px;color:#6b5744">
      more: <a href="/" style="color:#666">today's board</a> · <a href="/hall-of-filth/" style="color:#666">hall of filth</a> · <a href="/about/" style="color:#666">about dollar bets</a>
    </div>
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
