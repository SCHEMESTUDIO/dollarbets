#!/usr/bin/env python3
"""
Dollar Bets — Google Search Console Analysis Script

Reads GSC CSV exports and produces a prioritized SEO action report.

Usage:
  1. Export "Search results" from GSC (Queries tab) as CSV
  2. Export "Search results" from GSC (Pages tab) as CSV
  3. Run:  python3 gsc_analyze.py queries.csv pages.csv

Output: Markdown report to stdout (pipe to file if desired).

Analysis:
  - High impressions, low CTR queries (need better titles/descriptions)
  - High impressions, zero clicks (not compelling enough)
  - Queries ranking positions 4–20 (striking distance)
  - Pages with impressions but weak CTR
  - Pages with zero impressions (not indexed or not ranking)
  - Cannibalization risks (multiple URLs for same query)
  - Opportunities for new explainers
  - Opportunities to retitle existing pages
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime


def read_csv(filepath):
    """Read a GSC CSV export, return list of dicts."""
    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize column names (GSC uses varying capitalization)
            clean = {}
            for k, v in row.items():
                key = k.strip().lower().replace(" ", "_")
                clean[key] = v.strip() if v else ""
            rows.append(clean)
    return rows


def parse_float(val, default=0.0):
    try:
        return float(val.replace(",", "").replace("%", ""))
    except (ValueError, AttributeError):
        return default


def analyze_queries(rows):
    """Analyze query-level GSC data."""
    queries = []
    for row in rows:
        queries.append({
            "query": row.get("top_queries", row.get("query", row.get("queries", ""))),
            "clicks": parse_float(row.get("clicks", "0")),
            "impressions": parse_float(row.get("impressions", "0")),
            "ctr": parse_float(row.get("ctr", "0")),
            "position": parse_float(row.get("position", row.get("average_position", "0"))),
        })
    return [q for q in queries if q["query"]]


def analyze_pages(rows):
    """Analyze page-level GSC data."""
    pages = []
    for row in rows:
        pages.append({
            "page": row.get("top_pages", row.get("page", row.get("pages", ""))),
            "clicks": parse_float(row.get("clicks", "0")),
            "impressions": parse_float(row.get("impressions", "0")),
            "ctr": parse_float(row.get("ctr", "0")),
            "position": parse_float(row.get("position", row.get("average_position", "0"))),
        })
    return [p for p in pages if p["page"]]


def report_header():
    return f"""# Dollar Bets — GSC Analysis Report
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---
"""


def report_striking_distance(queries):
    """Queries ranking 4-20 with decent impressions — easiest wins."""
    hits = [q for q in queries if 4 <= q["position"] <= 20 and q["impressions"] >= 10]
    hits.sort(key=lambda x: x["impressions"], reverse=True)

    out = "## Striking distance (position 4–20)\n"
    out += "These queries are close to page 1 or top 3. Small improvements could yield big traffic gains.\n\n"
    if not hits:
        return out + "*No queries in striking distance with 10+ impressions.*\n\n"

    out += "| Query | Pos | Impr | Clicks | CTR |\n|-------|-----|------|--------|-----|\n"
    for q in hits[:30]:
        out += f"| {q['query']} | {q['position']:.1f} | {q['impressions']:.0f} | {q['clicks']:.0f} | {q['ctr']:.1f}% |\n"
    return out + "\n"


def report_high_impressions_low_ctr(queries):
    """High impressions but low CTR — title/description problem."""
    hits = [q for q in queries if q["impressions"] >= 50 and q["ctr"] < 2.0]
    hits.sort(key=lambda x: x["impressions"], reverse=True)

    out = "## High impressions, low CTR (<2%)\n"
    out += "People see the listing but don't click. Consider rewriting title tags and meta descriptions.\n\n"
    if not hits:
        return out + "*No queries matching this pattern.*\n\n"

    out += "| Query | Impr | CTR | Pos | Action |\n|-------|------|-----|-----|--------|\n"
    for q in hits[:20]:
        action = "Rewrite title + meta" if q["position"] <= 10 else "Improve content + title"
        out += f"| {q['query']} | {q['impressions']:.0f} | {q['ctr']:.1f}% | {q['position']:.1f} | {action} |\n"
    return out + "\n"


def report_zero_clicks(queries):
    """Impressions but literally zero clicks."""
    hits = [q for q in queries if q["impressions"] >= 20 and q["clicks"] == 0]
    hits.sort(key=lambda x: x["impressions"], reverse=True)

    out = "## Impressions with zero clicks\n"
    out += "These queries are showing up but nobody clicks. Likely a mismatch between query intent and your listing.\n\n"
    if not hits:
        return out + "*No zero-click queries with 20+ impressions.*\n\n"

    out += "| Query | Impr | Pos | Suggestion |\n|-------|------|-----|------------|\n"
    for q in hits[:20]:
        suggestion = "Add Quick Answer block" if q["position"] <= 10 else "Create dedicated page"
        out += f"| {q['query']} | {q['impressions']:.0f} | {q['position']:.1f} | {suggestion} |\n"
    return out + "\n"


def report_weak_pages(pages):
    """Pages with impressions but weak CTR."""
    hits = [p for p in pages if p["impressions"] >= 20 and p["ctr"] < 3.0]
    hits.sort(key=lambda x: x["impressions"], reverse=True)

    out = "## Pages with weak CTR (<3%)\n"
    out += "These pages are ranking but not converting impressions to clicks.\n\n"
    if not hits:
        return out + "*No weak-CTR pages.*\n\n"

    out += "| Page | Impr | CTR | Pos | Action |\n|------|------|-----|-----|--------|\n"
    for p in hits[:20]:
        url = p["page"].replace("https://dollarbets.lol", "")
        action = "Rewrite title/meta" if p["position"] <= 10 else "Improve content depth"
        out += f"| {url} | {p['impressions']:.0f} | {p['ctr']:.1f}% | {p['position']:.1f} | {action} |\n"
    return out + "\n"


def report_dead_pages(pages):
    """Pages with zero impressions — possibly not indexed."""
    hits = [p for p in pages if p["impressions"] == 0]

    out = "## Pages with zero impressions\n"
    out += "These pages may not be indexed, or may be targeting queries with no search volume.\n\n"
    if not hits:
        return out + "*All pages have some impressions.*\n\n"

    for p in hits[:20]:
        url = p["page"].replace("https://dollarbets.lol", "")
        out += f"- {url}\n"
    return out + "\n"


def report_new_explainer_opportunities(queries):
    """Queries containing question words that might need dedicated pages."""
    question_words = ["what", "how", "why", "is", "can", "does", "are", "will"]
    hits = []
    for q in queries:
        words = q["query"].lower().split()
        if words and words[0] in question_words and q["impressions"] >= 5:
            hits.append(q)
    hits.sort(key=lambda x: x["impressions"], reverse=True)

    out = "## New explainer opportunities\n"
    out += "Question-format queries that might deserve their own page.\n\n"
    if not hits:
        return out + "*No question queries detected.*\n\n"

    out += "| Query | Impr | Clicks | Pos |\n|-------|------|--------|-----|\n"
    for q in hits[:20]:
        out += f"| {q['query']} | {q['impressions']:.0f} | {q['clicks']:.0f} | {q['position']:.1f} |\n"
    return out + "\n"


def report_summary(queries, pages):
    """Top-level summary stats."""
    total_impressions = sum(q["impressions"] for q in queries)
    total_clicks = sum(q["clicks"] for q in queries)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
    avg_pos = sum(q["position"] for q in queries) / len(queries) if queries else 0

    out = "## Summary\n\n"
    out += f"- **Total queries:** {len(queries)}\n"
    out += f"- **Total impressions:** {total_impressions:,.0f}\n"
    out += f"- **Total clicks:** {total_clicks:,.0f}\n"
    out += f"- **Average CTR:** {avg_ctr:.1f}%\n"
    out += f"- **Average position:** {avg_pos:.1f}\n"
    if pages:
        out += f"- **Pages tracked:** {len(pages)}\n"
    return out + "\n---\n\n"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gsc_analyze.py queries.csv [pages.csv]")
        print("  Export CSVs from Google Search Console → Search Results → Export")
        sys.exit(1)

    queries_file = sys.argv[1]
    pages_file = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Reading queries from {queries_file}...", file=sys.stderr)
    query_rows = read_csv(queries_file)
    queries = analyze_queries(query_rows)
    print(f"  Found {len(queries)} queries", file=sys.stderr)

    pages = []
    if pages_file:
        print(f"Reading pages from {pages_file}...", file=sys.stderr)
        page_rows = read_csv(pages_file)
        pages = analyze_pages(page_rows)
        print(f"  Found {len(pages)} pages", file=sys.stderr)

    # Generate report
    report = report_header()
    report += report_summary(queries, pages)
    report += report_striking_distance(queries)
    report += report_high_impressions_low_ctr(queries)
    report += report_zero_clicks(queries)
    report += report_new_explainer_opportunities(queries)

    if pages:
        report += report_weak_pages(pages)
        report += report_dead_pages(pages)

    report += "---\n\n*Report generated by gsc_analyze.py. All recommendations are suggestions — review before acting.*\n"

    print(report)


if __name__ == "__main__":
    main()
