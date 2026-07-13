# Content Brief — Listicle Factory Resumption

**Date:** 2026-05-18
**Period analyzed:** GSC last 7 days (2026-05-10 to 2026-05-16)
**Comparison baseline:** GSC last 3 months snapshot (pulled 2026-05-12)

---

## 1. State of play

| Metric | Prior 3mo | Last 7 days | Read |
|---|---|---|---|
| Clicks | 6 | 15 | Growing, but small absolute numbers |
| Impressions | 124 | 406 | ~3× — driven by new pages getting indexed |
| Avg position | 18 | 33-53 | Worse — Google testing site against more queries |
| Top-CTR page | /crazy-kalshi-bets/ 16.67% | /crazy-kalshi-bets/ 12.66% | Still the workhorse |

The position decline is structural, not a regression. New pages enter search at low ranks; the average drops as more thin-relevance content gets indexed. Watch top-page positions, not site average.

**Confidence on growth direction:** medium. 15 clicks is statistical noise. The pattern of *which* queries convert is the higher-confidence signal — that's what this brief acts on.

---

## 2. What works (high confidence)

**One pattern accounts for 100% of click revenue: `[adjective] [platform] [bets|markets|predictions]`**

Click-getters in the period:
- "most outrageous polymarket bets" — 1 click / 4 imp / pos 5.5
- "weirdest kalshi bets" — 1 click / 4 imp / pos 6.25
- "polymarket crazy bets" — 1 click / 4 imp / pos 9.25

Plus the two workhorse pages:
- /crazy-kalshi-bets/ — 10 clicks / 79 imp / 12.66% CTR / pos 7.58
- /funny-polymarket-bets/ — 3 clicks / 93 imp / 3.23% CTR / pos 9.09

`/crazy-kalshi-bets/` is overperforming its position (industry baseline CTR at position 7-8 is 2-3%; this page is at 12.66%). Title and meta description are doing real work. Reuse them as the template.

`/funny-polymarket-bets/` underperforms its position. Audit the snippet — possibly the page title/description doesn't match the listicle promise as cleanly.

**Vocabulary harvested from GSC queries** — use these as substitution slots in titles and URL slugs:

- **Adjectives:** craziest, weirdest, funniest, most outrageous, most ridiculous, most absurd, crazy, weird, funny, outrageous, ridiculous, absurd
- **Platforms:** Kalshi, Polymarket, prediction market(s)
- **Nouns:** bets, markets, predictions, things, questions
- **Timeframes (optional):** today, this week, this month, 2026

---

## 3. Demand clusters worth building for

Three clusters Google is showing the site for. Listed by total impressions in the 7-day window.

### Cluster A: NBA prop bets — DEPRIORITIZE

50+ impressions across "best nba prop bets today/tonight" variants. Current page `/best-prop-bets-today-nba/` ranks position 68. This category is dominated by FanDuel, DraftKings, Action Network, RotoWire — sites with order-of-magnitude more authority. **Confidence we can't win this in 6 months: high.** Don't write more NBA prop pages. Let the existing page sit.

### Cluster B: Weather betting — LEAN IN

28+ impressions across 10+ variants:
- "weather betting" (6 imp, pos 52)
- "how to bet on weather" (4 imp, pos 88)
- "weather betting sites" (4 imp, pos 33)
- "weather betting website" (4 imp, pos 47)
- "weather gambling" (4 imp, pos 54)
- "bet on the weather" (3 imp, pos 58)
- "weather betting app" (1 imp, pos 25)
- "weather bet" (1 imp, pos 58)
- "bet on weather" (1 imp, pos 60)

Existing page `/weather-betting-markets/` getting 34 imp at pos 46. Real niche, low competition, fits Kalshi product (Kalshi has actual weather markets).

**Build 3-5 weather pages:**
- `/weather-betting/` — short slug, captures the head term
- `/weather-betting-sites/` — directly targets the cluster
- `/can-you-bet-on-the-weather/` — question variant
- `/weirdest-weather-bets-on-kalshi/` — listicle pattern × cluster
- `/weather-prediction-markets-this-month/` — listicle pattern × cluster × timeframe

### Cluster C: Election betting — LEAN IN

14+ impressions across "can you bet on the election" variants. Current page `/can-you-legally-bet-on-elections/` ranks pos 20.6 — closest-to-clickable of any new cluster.

**Build 3 election pages:**
- `/can-you-bet-on-the-2028-election/` — forward-looking, low competition
- `/weirdest-election-prediction-markets/` — listicle × cluster
- `/craziest-political-bets-on-polymarket/` — listicle × platform × cluster

### Cluster D: Educational ("what is X", "X explained") — DEPRIORITIZE

~40 impressions across 20+ variants, positions 70-95. Not ranking, won't rank without backlinks the site doesn't have. Stop generating educational content. Don't 410 the existing pages (they provide internal link juice) — just stop writing more, and demote them in sitemap priority.

### Cluster E: Specific named markets — OPPORTUNISTIC

"obama federally charged before 2027? prediction market" — 6 imp, pos 9.5. Almost-clickable.
"2026 gyeonggi province gubernatorial election winner prediction market" — 2 imp, pos 3.5.
"ukraine coup attempt by june 30? prediction market" — 1 imp, pos 18.

These are auto-generated share/OG pages picking up specific-market searches. **High confidence:** if the scanner picks up notable markets (high public interest, named entities), the share page will accrue impressions. Worth promoting the existing share pages with better internal links from the main listicle pages.

---

## 4. Generator changes (concrete)

### `generate_content.py` — add a listicle template

Inputs:
- Current board JSON (`data/boards/YYYY-MM-DD.json`) for market content
- A template config specifying `adjective`, `platform`, `noun`, `timeframe`, `topic_filter` (optional)
- The shared editorial style guide (already in `data/style-guide.json`)

URL pattern: `/{adjective}-{platform}-{noun}[-{timeframe}]/`

Title pattern: `The {Adjective_Cap} {Platform_Cap} {Noun_Cap}{ " " + Timeframe_Cap if timeframe}` (match the /crazy-kalshi-bets/ pattern that's winning).

Meta description pattern: 1-line setup + the dollar-bet hook. Use /crazy-kalshi-bets/ as the reference — its 12.66% CTR is the bar.

Body: 8-15 market cards from the current board, filtered by:
- `topic_filter` if specified (e.g., topic_filter="weather" → only weather-cluster markets)
- Sorted by oddity/entertainment score (already computed in `scanner.py`)
- Each card: bold title → 1-line setup quip → odds → $X-to-win-$1 framing → /go/ link

No "why it loses" sections (existing rule in memory).

### `gsc_analyze.py` — emit a content queue

New output: `data/content-queue.json` containing candidate page specs.

Eligibility for the queue (run daily):
1. Query has ≥5 impressions in the last 7 days
2. No existing page with a matching slug (compare query slug to existing URLs)
3. Query matches one of: the productive adjective × platform pattern, the weather cluster, the election cluster, or specific-named-market pattern
4. Query is *not* educational ("what is", "how do", "explained", "meaning")

Each queue item:
```json
{
  "query": "weather betting sites",
  "impressions_7d": 4,
  "current_position": 33.75,
  "proposed_slug": "weather-betting-sites",
  "template": "topic-cluster",
  "topic_filter": "weather",
  "approved": false
}
```

Manual approval gate (`approved: true` flag set by hand) before generation. Avoids generating pages for spam queries, fluke queries, or queries that drift from strategy.

### `scanner.py` — no changes needed

It already produces the data the listicles consume. The topic_filter in the template should pattern-match against existing market metadata (Kalshi event categories, custom-clusters.json).

### `analyze_taste.py` style guide — weight listicle voice

The existing guide handles quip tone. Add an explicit principle: "Pages in listicle format should open with a short hook (not a definition), use the dollar framing in the first paragraph, and end with a CTA to the live board — not a recap."

### Sitemap priorities (`generate.py → generate_html_sitemap()`)

- Listicle pages (slug matches the adjective × platform pattern): `priority=0.9`
- Topic-cluster pages (weather, election): `priority=0.8`
- Specific-market share pages: `priority=0.7`
- Educational pages ("what-is-", "betting-odds-explained", etc.): `priority=0.3`
- Demote educational from main nav and from internal cross-links

---

## 5. Cadence

- **Listicle pages:** 3-5 per week, generated from the current board.
- **Topic-cluster pages:** 2-3 per week (weather + election clusters until they show clicks, then expand).
- **Specific-market share pages:** already automatic via scanner. No change.
- **Educational pages:** zero.

---

## 6. Success criteria (review at 2026-06-18, 30 days)

Trigger conditions for "this is working":
- 30-50 new listicle/cluster pages live
- ≥5 pages ranking at position <15 for their target query (current: 2)
- Clicks/week trending toward 50+ (current: ~15)
- /crazy-kalshi-bets/ pattern replicated successfully — at least 3 sibling pages getting >5 clicks each

Trigger conditions for "reassess":
- <10 new pages live (execution failure, not strategy failure)
- New pages ranking position >30 — means the template isn't transferring the /crazy-kalshi-bets/ magic
- Clicks/week flat or declining

If the strategy works on listicles but fails on cluster pages, narrow to listicles only. If both fail, the bottleneck is domain authority, not content type — and the answer is backlinks, not more pages.

---

## 7. Out of scope

- Educational/definitional content (deprioritize, don't delete)
- NBA / sports-specific prop pages (unwinnable category)
- Backlink/outreach strategy (separate workstream)
- New content categories beyond weather + election (revisit once those show clicks)

---

## 8. Confidence summary

- **High confidence:** the adjective × platform pattern works; educational pages don't rank and won't; NBA prop is unwinnable.
- **Medium confidence:** weather and election clusters will convert at the listicle template; specific volumes for any 30-day target.
- **Low confidence:** 7-day data is small. The pattern is real; the magnitudes aren't reliable.
