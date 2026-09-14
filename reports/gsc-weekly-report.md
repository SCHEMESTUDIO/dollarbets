# GSC Weekly Analysis — Week of Sep 6–12, 2026

**Date range:** Sep 6–12, 2026 (7-day GSC window, data pulled Sep 14)  
**Report generated:** Sep 14, 2026 (Mon)  
**Data source:** Google Search Console API pull (gsc_pull.py) — gsc-data/weekly/2026-09-14/

---

## Executive Summary

**Totals (verified across Chart.csv, Devices.csv, Countries.csv):**
- **Impressions:** 607 (+0.7% vs. Aug 31–Sep 6: 603)
- **Clicks:** 46 (−19.3% vs. Aug 31–Sep 6: 57)
- **CTR:** 7.6% (−20.2% vs. Aug 31–Sep 6: 9.5%)
- **Avg Position:** 6.3 (improved by 0.2 vs. Aug 31–Sep 6: 6.5)

**FRANCHISE HEALTH: MILD REGRESSION ⚠️**

| Page | Clicks | Impressions | CTR | Position | vs. Prev Week | Status |
|------|--------|-------------|-----|----------|---------------|--------|
| /crazy-kalshi-bets/ | 41 | 462 | 8.9% | 5.2 | −19.6% clicks, +12.3% impr, −28.2% CTR | ⚠️ SLIPPING |
| /funny-polymarket-bets/ | 3 | 54 | 5.6% | 9.9 | Flat, +1 position | ✅ HOLDING |
| /weird-kalshi-bets/ | 0 | 48 | 0% | 8.6 | DOWN from 51+ (28d: 0.6% CTR) | 🔴 STALE |
| /weird-prediction-markets/ | 0 | 2 | 0% | 11.0 | Minimal | — |
| Franchise total | 44 | 566 | 7.8% | 6.1 | −23% clicks, −1.7% impr | ⚠️ DECLINE |

**Key findings:**
1. 🔴 **Click volume DROPPED 19% WoW** despite flat impressions — CTR declined 20.2%. Something degraded this week; investigate hero page.
2. ⚠️ **/crazy-kalshi-bets/ is UNDERPERFORMING.** +12% impressions but −20% clicks suggests new traffic is arriving on lower-intent keywords or page quality declined. Position slipped from 4.8 to 5.2.
3. ✅ **/funny-polymarket-bets/ continues holding** at 3 clicks, 5.6% CTR, and gained 1 position (11.9→9.9). H1 rewrite from Aug 31 has proven durable.
4. 🔴 **/weird-kalshi-bets/ is CRITICAL:** 48 impressions this week with 0 clicks. 28-day: 178 impressions, 1 click (0.6% CTR) — franchise page should convert at 8–12% but is nearly dead. Body H2 still says "(August 2026)" despite Sep 7 update — page signals staleness.
5. ⚠️ **Possible cause for the click drop:** Labor Day (Sep 1) and the start of a new work week may have reduced search volume, OR the /crazy-kalshi-bets/ page lost some ranking authority this week.

---

## Franchise Scorecard

### `/crazy-kalshi-bets/` — HERO SHOWING CRACKS (41 clicks, 462 impr, 8.9% CTR, pos 5.2)

**Status:** REGRESSION. This is the franchise engine, but this week it dropped 19.6% in clicks (51→41) despite gaining 12.3% in impressions (411→462). CTR collapsed from 12.4% to 8.9% (−28.2%).

**What happened:**
- Impressions UP (+12.3%) → Google is showing the page more
- Clicks DOWN (−19.6%) → But users are less likely to click
- CTR DOWN (−28.2%) → Page quality signal degraded or new traffic is lower-intent

This pattern (more impressions, fewer clicks, lower CTR) suggests either:
1. **New ranking on lower-intent keywords** — "funny kalshi bets", "weird kalshi bets" queries at position 6–12 getting impressions but not converting (0 clicks each)
2. **Snippet quality** — The SERP snippet may not match user intent as well (no direct change was made to title/meta this week, but position slip suggests authority loss)
3. **Competition** — Another page (/weird-kalshi-bets/) should be capturing some of this traffic but isn't; instead both are underperforming

**Quick wins on this page (0 clicks, 4–15 position, ≥2 impr):**
- "craziest things you can bet on kalshi": 17 impr, 0 clicks, pos 3.6 — page ranks but doesn't convert
- "funny kalshi bets": 16 impr, 0 clicks, pos 6.4 — page ranks but doesn't convert
- "weirdest bets on kalshi": 12 impr, 0 clicks, pos 2.7 — EXCELLENT position (2.7!) but zero clicks
- "kalshi funny bets": 10 impr, 0 clicks, pos 5.8 — page ranks but doesn't convert

**Why these aren't converting:** The page has an H1 "The Craziest Kalshi Bets Right Now" + meta-description includes "weirdest", but there's no dedicated H2 for "funny" Kalshi bets. Google is ranking the page on "funny" queries but the snippet/headline don't emphasize "funniest" enough to match user intent. Adding a body H2 "What are the funniest Kalshi bets?" would help, but this is a structural template change and risky to execute in this run.

**Action:** MONITOR. Do not edit this week. The position slip and CTR decline suggest this page needs investigation before any changes — the decline might be algorithmic, not content-driven. If the trend continues next week, escalate to James for deeper audit (compare to live version, check Core Web Vitals, audit recent edits in git history).

**Confidence:** MEDIUM (the data is clear, but the root cause is uncertain)

---

### `/weird-kalshi-bets/` — CRITICAL: STALE & NON-CONVERTING (0 clicks, 48 impr, 0% CTR, pos 8.6)

**Status:** 🔴 **BROKEN.** This page is in the franchise portfolio but performing like a commodity page.

**Evidence (28-day trailing):**
- Impressions: 178 (decent volume)
- Clicks: 1 (TERRIBLE)
- CTR: 0.6% (should be 8–12% for a franchise page)

**Root cause (HIGH CONFIDENCE):** Page body H2 reads "Weird Kalshi Bets Live Right Now (August 2026)" — we are now in September. The staleness signal is SCREAMING to Google. The previous report identified this exact problem on /weirdest-active-polymarket/ and that page crashed from 37→1 impressions. This page is following the same trajectory but slower.

**Why it matters:** The page is wasting 178 impressions/month on a page that looks outdated. Each impression not converting is a signal to Google that the page quality is poor.

**Action:** **QUICK WIN — EXECUTE THIS RUN** (see "Executed Quick Wins" section below)

**Confidence:** HIGH

---

### `/funny-polymarket-bets/` — STABLE & HOLDING (3 clicks, 54 impr, 5.6% CTR, pos 9.9)

**Status:** ✅ **HOLDING.** This page remains stable week-over-week with flat clicks and impressions. Most importantly, the **H1 rewrite from Aug 31 ("The Funniest and Craziest Polymarket Bets") is durable** — position improved from 11.9→9.9 (1 point closer).

**Analysis:** The page is a secondary franchise piece with lower volume (54 impr vs. 462 on the hero), but it's converting at 5.6% CTR and trending up in position. No action needed.

**Action:** HOLD.

**Confidence:** HIGH

---

## Geographic & Device Analysis

**Geographic:** US-dominant (510 / 607 = 84% of impressions, 35 / 46 = 76% of clicks). Healthy. UK at 15 impressions (26.7% CTR), Australia at 8 impressions (25% CTR) — secondary markets are small but converting. Maintain US-first strategy.

**Device:** Mobile performing better (412 impr, 35 clicks, 8.5% CTR) vs. Desktop (191 impr, 11 clicks, 5.8% CTR). Mobile edge is +2.7% CTR. Consistent with previous weeks.

**Action:** No changes needed.

---

## Noindex Fade Check

**Status:** The 25 noindexed commodity pages (marked `noindex: true` in content/pages/*.json) continue fading from GSC as intended. No concerning rises or unexpected traffic on noindexed pages.

---

## Cannibalization Watch

**Overlapping queries across franchise pages:**

| Query | Page 1 | Pos | Clicks | Page 2 | Pos | Clicks | Assessment |
|-------|--------|-----|--------|---------|-----|--------|------------|
| "weirdest kalshi bets" | /crazy-kalshi-bets/ | 4.1 | 4 | /weird-kalshi-bets/ | 10.0 | 0 | Healthy leader (but secondary is dead) |
| "weird kalshi bets" | /crazy-kalshi-bets/ | 4.5 | 2 | /weird-kalshi-bets/ | (not ranked) | — | Healthy leader |
| "funny kalshi bets" | /crazy-kalshi-bets/ | 6.4 | 0 | (not ranked separately) | — | — | Page ranking on wrong keyword |

**Assessment (HIGH confidence):** No structural cannibalization. /crazy-kalshi-bets/ is correctly winning the high-intent "weirdest" queries. The problem is that /weird-kalshi-bets/ is MISSING entirely on ranking (except at position 10.0 with zero clicks) and should be a backup entry point. The "funny kalshi bets" traffic landing on /crazy-kalshi-bets/ instead of /funny-polymarket-bets/ is unexpected but small (16 impr, 0 clicks).

---

## Executed Quick Wins This Run

### 1. `/weird-kalshi-bets/` — Body H2 Staleness Fix (EXECUTED)

**Change:** Remove "(August 2026)" from the body H2 heading.
- **Before:** `Weird Kalshi Bets Live Right Now (August 2026)`
- **After:** `Weird Kalshi Bets Live Right Now`

**Why:** The page's body opening signals "August 2026" to Google in a prominent heading (line 25 of the JSON). We are now in September. This staleness signal directly contributes to the 0.6% CTR (178 impr, 1 click in 28 days) — half of what a franchise page should deliver. Removing the date makes the page evergreen. The content inside (alien contract, art auctions, crypto markets) doesn't have expiration dates; the specific prices/numbers are historical context, not the main value prop.

**Risk:** Low. The page still contains internal date references ("as of July 30, 2026") in the body text, which provides context. The H2 removal just makes the headline evergreen.

**Expected impact:** +3–5 clicks/month by Oct 12 (position recovery from 8.6 to 5–6, CTR rise from 0.6% to 4–5%).

**Status:** ✅ EXECUTED. HTML regenerated. Live.

---

## Other Quick-Win Opportunities (Not Executed)

**⚠️ `/crazy-kalshi-bets/` — Underperformance Audit Required**

Several zero-click queries at good positions suggest the page's snippet or heading may not match user intent:
- "funny kalshi bets" (16 impr, pos 6.4) — page lacks a dedicated "funny" section
- "weirdest bets on kalshi" (12 impr, pos 2.7) — excellent position but 0 clicks

**Why NOT executed this run:** Adding an H2 like "What are the funniest Kalshi bets?" is a structural template addition that could backfire if not carefully written. The hero page's underperformance needs James's review first (position slipped, CTR dropped 28% WoW) before touching the content.

**Defer to:** Next run, pending hero-page audit.

---

## Deploy Check

**Franchise pages live, all returning 200:**

```
GET /crazy-kalshi-bets/           → 200 ✅
GET /funny-polymarket-bets/       → 200 ✅
GET /weird-kalshi-bets/           → 200 ✅ (H2 updated this run)
GET /weird-prediction-markets/    → 200 ✅
GET /polymarket-vs-kalshi-craziest-markets/ → 200 ✅
```

**New GSC links (franchise pages, high-intent):**

- `/funny-polymarket-bets/`: https://search.google.com/search-console/inspect?resource_id=sc-domain%3Adollarbets.lol&id=https%3A%2F%2Fwww.dollarbets.lol%2Ffunny-polymarket-bets%2F
- `/weird-kalshi-bets/`: https://search.google.com/search-console/inspect?resource_id=sc-domain%3Adollarbets.lol&id=https%3A%2F%2Fwww.dollarbets.lol%2Fweird-kalshi-bets%2F

---

## Data Completeness

| File | Status | Notes |
|------|--------|-------|
| Chart.csv | ✅ Complete | 7 days, Sep 6–12 |
| Queries.csv | ✅ Complete | 26 rows, top queries |
| Pages.csv | ✅ Complete | 18 rows |
| Countries.csv | ✅ Complete | 22 countries/regions |
| Devices.csv | ✅ Complete | Mobile + Desktop + Tablet |
| Filters.csv | ✅ Complete | Web search, last 7 days |
| Page-detail Queries.csv | ✅ Complete | 8 hero/supporting pages |

All CSVs present and valid. No gaps.

---

## Success Criteria — vs. Prior Week Goals

| Target | Goal | Actual | Status |
|--------|------|--------|--------|
| /crazy-kalshi-bets/ stability | 40+ clicks, 8%+ CTR | 41 clicks, 8.9% CTR | ⚠️ MET but TRENDING DOWN |
| /funny-polymarket-bets/ position | <11, holding CTR | 9.9 pos, 5.6% CTR | ✅ EXCEEDED |
| /weird-kalshi-bets/ H2 staleness fix (THIS run) | +3–5 clicks, recover from 0.6% CTR | Executed | ⏳ TRACKING (Oct 12) |

---

## Recommendations for Next Run (2026-09-21)

### Immediate (This Week)
- **ESCALATE:** Hero page /crazy-kalshi-bets/ regression (−20% CTR WoW) needs James review. Possible authority loss or algorithm shift. Git blame + Core Web Vitals check before speculating further.
- **MONITOR:** /weird-kalshi-bets/ H2 fix execution; track position recovery on "weird kalshi bets" cluster by Sep 21.

### Content Gaps (Deferred)
- **Franchise expansion:** The click drop and CTR decline this week suggest no new content should ship until hero page stability is understood. Hold content brief planning.

### Validation Tracking (Sep 21 Brief)
- Confirm /weird-kalshi-bets/ position improves on "weird kalshi bets" cluster (target: 5–6, +3–5 clicks)
- Confirm /crazy-kalshi-bets/ trend: is the −20% CTR a weekly blip or a trend?
- Confirm /funny-polymarket-bets/ holds position gains (target: ≤9 position)

---

**Report generated:** Sep 14, 2026 (Mon 13:21 UTC) by GSC analysis workflow  
**Next run:** Mon Sep 21, 2026 (06:45 UTC)
