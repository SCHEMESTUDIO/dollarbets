# GSC Weekly Analysis — Week of Oct 11–17, 2026

**Date range:** Oct 11–17, 2026 (7-day GSC window, data pulled Oct 19, 2026)  
**Report generated:** Oct 19, 2026 (Mon 06:45 UTC)  
**Data source:** Google Search Console API pull (gsc_pull.py) — gsc-data/weekly/2026-10-19/

---

## Executive Summary

**Totals (verified across Chart.csv, Devices.csv, Countries.csv, Pages.csv):**
- **Clicks:** 82 (+32% vs. Oct 4–10: 62) — **FRANCHISE GROWTH** ✅
- **Impressions:** 917 (+34% vs. Oct 4–10: 687) — **STRONG VOLUME GROWTH** ✅
- **CTR:** 8.9% (−0.1 pt vs. Oct 4–10: 9.0%) — flat, noise
- **Avg Position:** 4.1 (improved vs. Oct 4–10: 5.8) — **BETTER RANKINGS** ✅

**Geographic:** US-dominant (65/82 clicks = 79% weekly). Mobile-first (71/82 = 87% weekly). 
**Confidence:** HIGH — all totals cross-verified across Chart, Pages, Countries, Devices CSVs.

---

## FRANCHISE SCORECARD

| Page | Weekly Clicks | Weekly Impr | CTR | Position | vs. Oct 4–10 | Status |
|------|--------------|------------|-----|----------|------------|--------|
| **/crazy-kalshi-bets/** | **75** | 812 | 9.2% | **3.6** | +41% clicks ↑ | 🔥 **ANCHOR SURGING** |
| **/funny-polymarket-bets/** | 3 | 57 | 5.3% | 6.6 | −40% clicks ↓ | ⚠️ **REGRESSED** |
| **Franchise total** | **78** | **869** | **8.9%** | **4.6** | +32% clicks ↑ | ✅ **NET POSITIVE** |

### Key Findings

1. **🔥 /crazy-kalshi-bets/ anchor is on a growth trajectory** — 75 clicks (+42% WoW) driven by core franchise queries at positions 1.8–5.0. "Weirdest kalshi markets" ranks pos 1.8 with 7 clicks, "craziest things you can bet on kalshi" pos 3.1 with 3 clicks. Stable 9.2% CTR. **ACTION: No changes needed — let this momentum run.**

2. **⚠️ /funny-polymarket-bets/ regressed from 5 → 3 clicks** — Position moved worse (6.6 vs. 8.6 last week, but impressions down 57→57, flat). Looking at page-detail queries: "funny prediction markets" pos 1.3 with 0 clicks suggests CTR issue on primary query cluster. The title/meta-description may not be converting at position 1. **CONFIDENCE: MEDIUM** — only 1 week of regression data. Monitor next week before acting. Flag for next week if trend continues.

3. **Geographic & device health: solid US dominance (79%) + mobile-first (87%)** — Mobile CTR 10.5% vs. Desktop 4.6%, confirming mobile users are more likely to click CTA. Canada (3 clicks, 13.6% CTR) and Brazil (3 clicks, 30% CTR) are strong secondary markets.

---

## Trend Deltas vs. Last Week

| Metric | Oct 4–10 | Oct 11–17 | Change | Interpretation |
|--------|----------|-----------|--------|-----------------|
| Sitewide clicks | 62 | 82 | +32% | **Strong organic growth.** Not driven by ranking improvements alone — impressions also up +34%, suggesting increased search volume or successful SERP presence expansion. |
| Avg position | 5.8 | 4.1 | −1.7 pts | **Positive.** Lower position numbers = higher SERP placement. No algorithm penalty; solid recovery from last week's slight degradation. |
| Franchise clicks | 59 | 78 | +32% | **In-line with sitewide growth.** Franchise pages are driving the growth — no dilution from commodity pages. |
| Mobile CTR | — | 10.5% | — | **Strong mobile engagement.** Desktop CTR only 4.6%, indicating franchise content resonates with mobile-first discovery (quick-hit curiosity search → tap). |

---

## Quick Wins (Franchise-Only Opportunities)

**Criteria:** Position 4–15, ≥2 impressions, 0 clicks, on a franchise page = low-hanging copy/metadata optimization.

### Identified Quick Wins (FRANCHISE PAGES ONLY)

1. **[FRANCHISE] "kalshi" (generic query) — 44 impressions, pos 3.2, 0 clicks on /crazy-kalshi-bets/**
   - **Context:** Top-ranking but no clicks suggests the page's title/meta-description doesn't match the bare-brand query intent. Users searching "kalshi" may be looking for a platform explainer, not a craziest-bets roundup. 
   - **Status:** Monitor only; this is not a franchise query and optimizing for bare-brand would dilute the page's core franchise positioning. **SKIP EXECUTION.**

2. **[NON-FRANCHISE] "best kalshi bets today" — 10 impressions, pos 10, 0 clicks on /crazy-kalshi-bets/**
   - **Issue:** Position 10 is too low for bulk clicks; the query cluster ("best kalshi bets") is commodity-adjacent (not "craziest" or "weirdest"). 
   - **Status:** Not a franchise quick win. **SKIP EXECUTION.**

**EXECUTIVE DECISION: Zero executable quick wins this week.** The franchise pages are already converting well on their core queries (9.2% CTR at pos 3.6 for /crazy-kalshi-bets/, top queries at 1.8–5.0). The 0-click opportunities are either on non-franchise queries or at positions too high for cost-effective tweaking.

---

## No Page Retirements Flagged

GSC Pages.csv shows all franchise pages performing above retirement threshold:
- /crazy-kalshi-bets/: 75 clicks, 9.2% CTR — **KEEP**
- /funny-polymarket-bets/: 3 clicks (down from 5, but still earning impressions; wait for 2+ weeks of regression before retiring)
- Hall of Filth pages: 0 clicks weekly but <5 impressions each = search visibility maintained, low-value, but not a cannialization risk

**ACTION: No retirements this week. Monitor /funny-polymarket-bets/ through Oct 25 before considering any changes.**

---

## Cannibalization Watch

**Page-detail query overlap check:**

1. **Query "weird kalshi bets" appears in:**
   - /crazy-kalshi-bets/: 8 clicks, pos 3.3 (primary)
   - Implied: no overlap seen in page-detail files (only crazy-kalshi-bets has dedicated file with this query)

2. **Query "funny prediction markets" appears in:**
   - /funny-polymarket-bets/: 0 clicks, pos 1.3 (primary, but failing to convert)
   - No evidence of secondary ranking; /funny-polymarket-bets/ owns this query

**FINDING: Zero cannibalization detected this week.** The franchise pages own their query clusters cleanly.

---

## Content Gaps & Opportunities

**Franchise coverage snapshot:**
- ✅ Kalshi craziest/weirdest/wildest: **SATISFIED** by /crazy-kalshi-bets/ (dominant, 75 clicks)
- ✅ Polymarket funny/crazy: **PARTIALLY SATISFIED** by /funny-polymarket-bets/ (regressing to 3 clicks)
- ⚠️ Polymarket-vs-Kalshi comparison: **UNDERSATURATED** — /polymarket-vs-kalshi-craziest-markets/ earned 0 clicks this week, position pos 8, only 1 impression tracked. Query "polymarket vs kalshi" appears 0 times in weekly Queries.csv. Opportunity: expand Polymarket differentiation content to capture emerging comparison demand (not yet visible in GSC but emerging in editorial).

---

## Executed This Run

**None.** Zero quick wins identified; no pages flagged for retirement; no title/meta edits made.

---

## Deploy Check — Oct 19

**HTTP status check on franchise pages (light verification):**
```
/crazy-kalshi-bets/ → 200 ✅ LIVE
/funny-polymarket-bets/ → 200 ✅ LIVE
```

All pages deployed and serving. No 404s or redirects detected. GSC URL Inspection (optional, heavy): 
- [/crazy-kalshi-bets/](https://search.google.com/search-console/inspect?resource_id=sc-domain%3Adollarbets.lol&id=https%3A%2F%2Fwww.dollarbets.lol%2Fcrazy-kalshi-bets%2F)
- [/funny-polymarket-bets/](https://search.google.com/search-console/inspect?resource_id=sc-domain%3Adollarbets.lol&id=https%3A%2F%2Fwww.dollarbets.lol%2Ffunny-polymarket-bets%2F)

---

## Data Quality Notes

- **Filters.csv:** Last 7 days, Web search type (no Image/News).
- **Chart.csv:** Daily breakdown Oct 11–17 verified ✅ (7 days: totals match aggregate).
- **Countries.csv, Devices.csv:** Totals match Pages/Queries within privacy thresholds ✅.
- **Page-detail queries:** Spot-checks confirm top query ranks and click distributions ✅.
- **Privacy threshold impact:** ~43 clicks fall into ungrouped "more" category (query totals 39 tracked, pages total 82). NORMAL — Google privacy settings hide low-volume queries after top 75.

---

## Recommendations for Next Week

1. **Monitor /funny-polymarket-bets/ through Oct 25.** If clicks remain <5 and CTR stays <6% for a second week, flag for title/meta review or content refresh.
2. **Capitalize on /crazy-kalshi-bets/ momentum.** Consider a sibling Polymarket equivalent ("Craziest Polymarket Bets") if a large franchise opportunity pool exists — current Polymarket coverage is scattered (0 clicks on /most-outrageous-polymarket-bets/, /weirdest-active-polymarket-markets-july-2026/, etc.).
3. **Internal linking audit:** Franchise pages (crazy-kalshi, funny-poly, etc.) should link to each other where topically relevant, to distribute the growing click volume and improve cross-discovery.

**SUCCESS CRITERIA FOR WEEK OF OCT 18–24:**
- /crazy-kalshi-bets/ ≥65 clicks (sustain or grow)
- Sitewide CTR ≥8.5% (maintain quality)
- /funny-polymarket-bets/ rebounds to ≥4 clicks (recovery signal)
