# GSC Weekly Analysis — Dollar Bets

**Date range:** Aug 9–15, 2026 (7-day GSC window)  
**Report generated:** Aug 17, 2026  
**Data source:** Google Search Console API pull (gsc_pull.py)

---

## Executive Summary

**Totals (verified across Chart.csv, Devices.csv, Countries.csv):**
- **Impressions:** 699
- **Clicks:** 47
- **CTR:** 6.7%
- **Avg Position:** 8.5

**Franchise health — STRONG on primary, weak on secondaries:**

| Page | Clicks | Impressions | CTR | Position | Status |
|------|--------|-------------|-----|----------|--------|
| /crazy-kalshi-bets/ | 44 | 345 | 12.8% | 3.8 | ✅ HERO |
| /funny-polymarket-bets/ | 0 | 82 | 0% | 11.3 | ⚠️ HIGH VISIBILITY, NO CLICKS |
| /weirdest-active-polymarket-markets-august-2026/ | 1 | 101 | 1% | 7.7 | ⚠️ GOOD POSITION, NOT CONVERTING |
| /polymarket-vs-kalshi-craziest-markets/ | 1 | 6 | 16.7% | 31.7 | ⚠️ STRONG CTR, POOR VISIBILITY |
| /weird-kalshi-bets/ | 0 | 17 | 0% | 11.9 | ⚠️ WEAK |
| Other franchise pages | 1 | 48 | 2% | ~15 | ⚠️ MINIMAL IMPACT |

**Key finding:** `/crazy-kalshi-bets/` generates 93% of franchise clicks (44/47). Polymarket pages have good visibility but poor click-through, suggesting a title/meta copy mismatch.

---

## Franchise Scorecard

### `/crazy-kalshi-bets/` — PERFORMING (44 clicks, 345 impr, 12.8% CTR, pos 3.8)

**Status:** Dominant. Position 3.8 (rank 1), 12.8% CTR (2× site average). This is the money page.

**Top queries:** All Kalshi variations (craziest, crazy, weirdest, funny, dumb) at 20% CTR+.

**Action:** Maintain. Stability is the goal.

**Confidence:** HIGH

---

### `/funny-polymarket-bets/` — CRITICAL QUICK WIN (0 clicks, 82 impr, 0% CTR, pos 11.3)

**Status:** High visibility, zero conversion. Position 11.3 is decent, but title doesn't match query intent.

**Evidence:**
- "funny polymarket bets" query: 0 clicks, pos 9.0
- "funniest polymarket bets" query: 0 clicks, pos 11.0
- "funny prediction markets" query: 0 clicks, pos 20.1

**Root cause:** Title "Funny Prediction Markets Right Now — Funny Polymarket Bets" is indirect. Searchers want "Funniest Polymarket Bets," not a discovery roundup.

**Quick win:** Simplify title to "Funniest Polymarket Bets | Dollar Bets" — matches intent directly.

**Expected impact:** +3–5 clicks/week if title improves position/CTR.

**Confidence:** MEDIUM-HIGH

**Status:** EXECUTED (see section below)

---

### `/weirdest-active-polymarket-markets-august-2026/` — UNDERPERFORMING (1 click, 101 impr, 1% CTR, pos 7.7)

**Status:** Excellent position, nearly zero conversion. This page should be performing but isn't.

**Evidence:** 101 impressions (top-3 franchise visibility) but only 1 click. H1 "the weirdest popular active polymarket markets right now (august 2026)" is literal/informational, not compelling.

**Root cause:** H1 emphasizes "popular and active" (commodity language) over the hero content (Putin Nobel Prize at 286x payout — literally the weirdest thing).

**Quick win:** Rewrite h1 to "the craziest, weirdest polymarket bets (august 2026)" — emphasizes the weirdness over the roundup structure.

**Expected impact:** +5–8 clicks/week if CTR improves from 1% to 3–5%.

**Confidence:** MEDIUM

**Status:** EXECUTED (see section below)

---

### `/polymarket-vs-kalshi-craziest-markets/` — PROMISING BUT BURIED (1 click, 6 impr, 16.7% CTR, pos 31.7)

**Status:** Strong CTR (16.7%), terrible visibility (page 4). Not a quick win, but a long-term opportunity.

**Action:** Monitor for ranking improvements. If position improves to 10–15, this becomes a top-5 page.

**Confidence:** HIGH

---

## Geographic & Device Analysis

**Geographic:** US-centric (70% of impressions, 79% of clicks, 7.5% CTR). Healthy for a US compliance/affiliate site.

**Device:** Mobile outperforms (8.2% CTR) vs. desktop (5.2% CTR). Expected — discovery/casual queries favor mobile.

**Action:** Maintain mobile-first design; monitor if desktop CTR falls further.

---

## Noindex Fade Check

**Status:** Noindexed commodity pages (25 pages as of 2026-08-03) are not appearing in top-20 results. The prune is working as intended.

---

## Cannibalization Watch

**Potential issue:** `/weirdest-active-polymarket-markets-august-2026/` (1 click, pos 7.7) and `/weirdest-polymarket-markets-june-2026/` (1 click, pos 8.1) both rank for "weirdest polymarket" query family. August page has 3× visibility but same conversion. Monitor if June page takes over; consider consolidating if visibility shifts.

**Status:** Not yet a problem; both pages have distinct content (June vs. August markets).

---

## Deploy Check

All franchise pages live and 200 status:
- /crazy-kalshi-bets/ ✅
- /funny-polymarket-bets/ ✅
- /weirdest-active-polymarket-markets-august-2026/ ✅
- /polymarket-vs-kalshi-craziest-markets/ ✅
- /weird-kalshi-bets/ ✅

---

## Data Completeness

| File | Status |
|------|--------|
| Queries.csv | ✅ Complete (58 rows) |
| Pages.csv | ✅ Complete (23 rows) |
| Countries.csv | ✅ Complete (67 rows) |
| Devices.csv | ✅ Complete (3 rows) |
| Chart.csv | ✅ Complete (7 days) |
| Filters.csv | ✅ Complete |

Page-detail CSVs not present (possible scope configuration).

---

## Quick Wins Executed This Run

### 1. `/funny-polymarket-bets/` — Title simplification

**Old:** "Funny Prediction Markets Right Now — Funny Polymarket Bets | Dollar Bets"
**New:** "Funniest Polymarket Bets | Dollar Bets"
**Rationale:** Direct match on "funniest polymarket bets" query (0 clicks currently); wordier title reads as discovery/news, not direct answer.
**File edited:** `content/pages/funny-polymarket-bets.json`
**Last_updated:** 2026-08-17
**Status:** ✅ Executed, generate.py rebuild successful

---

### 2. `/weirdest-active-polymarket-markets-august-2026/` — H1 rewrite

**Old h1:** "the weirdest popular active polymarket markets right now (august 2026)"
**New h1:** "the craziest, weirdest polymarket bets (august 2026)"
**Rationale:** Position 7.7 with 1 click suggests expectation mismatch. "Craziest, weirdest" emphasizes the hero content (286× payout) over "popular active" (commodity language). Better match on "weirdest polymarket" queries.
**File edited:** `content/pages/weirdest-active-polymarket-markets-august-2026.json`
**Last_updated:** 2026-08-17
**Status:** ✅ Executed, generate.py rebuild successful

---

## Success Criteria for Next Week

1. **Polymarket quick-win clicks:** Expect +3–8 combined new clicks on the two rewritten pages (vs. 1 total this week).
2. **CTR stability:** `/crazy-kalshi-bets/` should maintain 40+ clicks, 12%+ CTR.
3. **Position gains:** If the title/h1 rewrites land, positions on "funniest polymarket" and "weirdest polymarket" queries should improve by 1–3 spots.

---

**Next run:** Mon 2026-08-24, 06:45 UTC
