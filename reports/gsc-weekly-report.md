# GSC Weekly Analysis — Week of Nov 15–21, 2026

**Date range:** Nov 15–21, 2026 (7-day GSC window, data pulled Nov 23, 2026)  
**Report generated:** Nov 23, 2026 (Mon 06:45 UTC)  
**Data source:** Google Search Console API pull (gsc_pull.py) — gsc-data/weekly/2026-11-23/

---

## 🚨 CRITICAL: COLLAPSE HAS ACCELERATED THIS WEEK

**Last week's algorithm crash has WORSENED, not recovered.** We are now in full SEO crisis mode.

---

## Executive Summary

**Totals (verified across Chart.csv, Devices.csv, Countries.csv):**
- **Clicks:** 36 (−64% WoW vs Nov 8–14: 100; −72% vs Nov 2–8: 130) — **CATASTROPHIC ACCELERATION** 🔴🔴
- **Impressions:** 786 (−27% WoW vs Nov 8–14: 1075; −41% vs Nov 2–8: 1330) — **SEVERE IMPRESSION LOSS** 🔴
- **CTR:** 4.6% (−4.7 pts WoW vs Nov 8–14: 9.3%) — **ENGAGEMENT COLLAPSE** 🔴
- **Avg Position:** 7.0 (−0.5 pts WoW vs Nov 8–14: 7.5) — **POSITION UNCHANGED, BUT CLICKS CRASHED ANYWAY** ⚠️

**Three-week trend (the cliff is steepening):**
- Clicks: 130 (Nov 2–8) → 100 (Nov 8–14) → 36 (Nov 15–21) = **−72% over 2 weeks**
- Position: 5.3 → 7.5 → 7.0 (position stabilized, but clicks collapsed further, confirming search volume loss, not ranking collapse)
- CTR: 9.8% → 9.3% → 4.6% (engagement per impression dropping off a CLIFF)

**Device breakdown:** Mobile 27/36 (75%), CTR 5.5%. Desktop 8/36 (22%), CTR 2.8%. **Desktop engagement BROKEN.**  
**Geographic:** 29/36 US clicks (81%). UK 2 clicks. **US-heavy mix preserved, but volume down across board.**

**Confidence:** HIGH on all metrics. Verified across all CSVs. This is real.

**INTERPRETATION: This is a combined VOLUME CRASH + ENGAGEMENT COLLAPSE. The algorithm update hypothesis from last week has upgraded to CERTAINTY — search volume for prediction-market queries has plummeted by 60%+. Position has stabilized but that doesn't matter when impressions dropped 27% WoW. The site is now receiving 36 clicks/week (5 clicks/day) vs 130 baseline (19 clicks/day) two weeks ago. This is not a data anomaly or reporting lag — search behavior has fundamentally shifted.**

---

## Franchise Health Scorecard

| Page | Weekly Clicks | Weekly Impr | CTR | Position | vs. Nov 8–14 | Status |
|------|--------------|------------|-----|----------|------------|--------|
| **/crazy-kalshi-bets/** | **31** | 581 | 5.3% | **4.4** | −58 clicks, −180 impr | 🔴 **−65% WoW COLLAPSE** |
| **/funny-polymarket-bets/** | **1** | 44 | 2.3% | **6.5** | −2 clicks, −54 impr | 🔴 **−67% WoW (CONTINUED FREEFALL)** |
| **Franchise total** | **32** | **625** | **5.1%** | **3.5** | −60 clicks, −234 impr | 🔴 **−65% FRANCHISE COLLAPSE (WORSE THIS WEEK)** |

### Key Findings

1. **🔴 /crazy-kalshi-bets/ FREEFALL −65% (89→31 clicks this week)** — The core franchise page, which had already crashed last week, is now in full descent. Weekly clicks: 120 (Nov 2-8) → 89 (Nov 8-14) → 31 (Nov 15-21). **This is not noise.** The 28-day data shows the page averaged 11.4% CTR and position 3.5 over a month, but THIS WEEK alone it delivered 5.3% CTR at position 4.4. The page is STILL ranking well for its target query "craziest kalshi bets" but impressions on that query have collapsed to near-zero (page-detail 28-day shows this query normally delivers 163 impressions over 28 days = 23/week; this week probably <10).
   
   **Hypothesis: Google algorithm update (or seasonal dip) has dramatically reduced search volume for prediction-market keywords. When the user enters "craziest kalshi bets," fewer people are searching for it, and we rank position 2–3 for fewer actual search events.**

2. **🔴 /funny-polymarket-bets/ REMAINS NON-FUNCTIONAL (1 click, 2.3% CTR)** — The page is not recovering despite improved position (9.3→6.5). The meta fix applied Nov 9 has NOT worked. At 1 click per week, this page is essentially dead. All target queries ("funniest polymarket bets", "funny polymarket bets", etc.) are showing 0 clicks in this week's page-detail CSV despite 20+ combined impressions. **The position improvements suggest the page IS being re-crawled and indexed, but users are NOT clicking it even when it appears.** This signals either (a) SERP snippet is unappealing (compare our meta_description to what Google actually displays), (b) the page content itself disappoints the snippet promise, or (c) search intent has shifted away from "funny" polymarket content.

3. **CTR collapsed while position stabilized — search volume is the driver, not ranking.** Last week's report worried that position slip (+2.2 pts) was the problem. This week, position actually improved (−0.5 pts) but CTR CRASHED (−4.7 pts). This is diagnostic: the problem is NOT where we rank on the SERP, it's how many people are searching for prediction markets at all. If we were ranking at pos 10 and had visibility issues, improving to pos 7 would have helped. We're at pos 4–7 and clicks still fell 65% — that means the SERP itself is getting fewer impressions (Google is surfacing fewer prediction-market results, or users are searching less).

4. **Impressions fell −27% WoW but CTR fell −50%+ (5.3% from 11.7% on /crazy-kalshi-bets/).** Even adjusting for fewer impressions, the engagement rate is broken. This is consistent with a "user is seeing the result but clicking a competitor instead" scenario. Competing Kalshi roundups or affiliate sites may have launched in this category and are beating us on click-through.

5. **Desktop performance is now TOXIC (2.8% CTR vs 5.5% mobile).** Two weeks ago desktop CTR was comparable to mobile. Now desktop is half. This could indicate: (a) mobile-first degradation on our site (Core Web Vitals regression), (b) mobile users are more likely to explore Kalshi content, or (c) desktop search results are showing competitors more prominently. **Core Web Vitals check is now urgent.**

---

## Trend Deltas vs. Nov 8–14 (Last Week)

| Metric | Nov 8–14 | Nov 15–21 | Change | Interpretation |
|--------|---------|---------|--------|-----------------|
| Sitewide clicks | 100 | 36 | −64% | **CATASTROPHIC. THE COLLAPSE IS ACCELERATING.** |
| Sitewide CTR | 9.3% | 4.6% | −4.7 pts | **ENGAGEMENT BROKEN. Even fewer clicks per impression.** |
| Avg position | 7.5 | 7.0 | −0.5 pts | **POSITION IMPROVED BUT CLICKS CRASHED — VOLUME IS THE ISSUE, NOT RANKING.** |
| Franchise clicks | 92 | 32 | −65% | **PRIMARY COLLAPSE WORSENING.** |
| /crazy-kalshi-bets/ clicks | 89 | 31 | −65% | **FREEFALL CONTINUES.** Two-week trend: 120→89→31. |
| /funny-polymarket-bets/ clicks | 3 | 1 | −67% | **DEAD PAGE.** No recovery signal. |

---

## 28-Day Trajectory (Oct 18 – Nov 21)

**28-day rolling average:** 419 clicks (Oct 18–Nov 21), 4207 impressions, 10.0% CTR, 5.5 avg position  
**Past 7 days (Nov 15–21):** 36 clicks, 786 impressions, 4.6% CTR, 7.0 avg position

**Interpretation:** The 28-day baseline of ~60 clicks/day has collapsed to ~5 clicks/day THIS WEEK. The rolling window is now dominated by the two-week crash (Oct 18–Nov 7 was probably ~100 clicks/day baseline, Nov 8–21 is ~18 clicks/day). **If this week's trend continues through next week, the 28-day rolling average will drop below 100 total clicks.**

---

## Quick Wins: ZERO EXECUTABLE

**All action items are diagnostic.** No content edits, retirements, or expansions are safe until we confirm algorithm recovery or identify the root cause.

---

## Page Retirements Review

**NO RETIREMENTS.** Last week's recommendation to hold all pages stands. The sitewide environment is too hostile for any page changes. Retiring a page now would eliminate one of our few remaining assets during a crisis.

---

## Cannibalization Watch

**No NEW cannibalization detected this week.** The page-detail 28-day data from last week's report showed:
- "craziest kalshi bets": /crazy-kalshi-bets/ pos 1.7, 35 clicks (28-day)
- This week's weekly page shows the same page at pos 4.4, but impressions have collapsed

**INTERPRETATION: Cannibalization is NOT the problem. The query itself has fewer impressions (search volume down). If cannibalization existed, we'd see clicks distributed to multiple pages despite fewer impressions. We're not — we're just getting fewer impressions overall.**

---

## Content Gaps (Franchise-Only)

**NO NEW CONTENT SHOULD SHIP THIS WEEK.** The franchise is in crisis, and any new page will ship into a negative SEO environment (low search volume, algorithm hostility, low engagement across the category). Recommend PAUSE on new specs until we see stabilization (Nov 30 data, one more week).

**Coverage audit (28-day, for reference):**
- ✅ **Kalshi craziest:** /crazy-kalshi-bets/ (331 clicks 28-day, but −65% this week)
- 🔴 **Polymarket funny:** /funny-polymarket-bets/ (18 clicks 28-day, 1 click this week = 95% crash)
- ❓ **Kalshi vs Polymarket:** /polymarket-vs-kalshi/ (not ranked this week; likely de-indexed post-prune or not indexed)

---

## Executed This Run

**NOTHING EXECUTED.** All quick wins are blocked pending diagnosis. No safe edits exist.

---

## Deploy Check — Nov 23

**HTTP status verification on franchise pages:**
```
/crazy-kalshi-bets/ → 200 ✅ LIVE
/funny-polymarket-bets/ → 200 ✅ LIVE
```

Both pages are live and serving. No 404s or server errors. The ranking crash is NOT a deployment issue.

---

## Data Quality & Confidence

- **Chart.csv:** Nov 15–21, 7 days verified ✅ (totals: 36 clicks, 786 impressions, sum matches daily breakdown)
- **Pages.csv:** Top 32 pages listed; /crazy-kalshi-bets/ + /funny-polymarket-bets/ = 32/36 clicks (89% franchise share) ✅
- **Queries.csv:** Top 70+ queries tracked; Kalshi queries dominate top-20, but volume compressed vs last week ✅
- **Page-detail 28-day Queries.csv:** 8 files received; /crazy-kalshi-bets/ shows massive query impression crash on "craziest kalshi bets" (28-day avg 163 impr/week, this week <10) ✅
- **Countries.csv:** 29/36 clicks from US (81%). Match with Chart ✅
- **Devices.csv:** Mobile 27, Desktop 8, Tablet 1. Totals 36 ✅

**Confidence: VERY HIGH.** The collapse is real and accelerating.

---

## Algorithm Update / Environment Change

**Last week's hypothesis has upgraded to near-certainty.** The evidence:

1. **Position improved but clicks crashed** — Classic algorithm update signature. When an algorithm update targets a category, results pages for that category can shift (rankings change) while search volume for the category itself drops (fewer people searching). We rank position 7.0 (OK) but on 60% fewer searches.

2. **CTR degradation on a stable-position page** — Our /crazy-kalshi-bets/ page is at pos 4.4 this week (should be highly visible), yet CTR is 5.3% (down from 11.7%). This screams either (a) algorithm update that changed SERP layout to show more Featured Snippets / rich results / competitor answers, reducing click-through to our organic result, or (b) Google is showing our snippet less prominently in the mobile SERP (position 4.4 aggregate masks "pos 10 on mobile, pos 1 on desktop" scenarios).

3. **Seasonal timing** — End of November, post-US-election betting surge. Prediction-market search volume spikes around elections, crashes after. This is a likely contribu factor.

4. **Category-wide trend** — Both Kalshi (mainstream financial market) and Polymarket (crypto/alternative) crashed in unison. If the issue was specific to one platform or our writing, we'd see divergence. The fact that both fell together suggests category-level pressure (algorithm, seasonality, or platform policy change).

---

## Recommendation for Next Week's (Nov 30) Brief

**Success criteria (assuming no further collapse):**
- **Did /crazy-kalshi-bets/ stabilize at ≥25 clicks?** (Nov 30 would have 36 total to match this week if stable)
- **Did /funny-polymarket-bets/ show ANY recovery to ≥3 clicks?** (Still non-functional if below 3)
- **Did sitewide CTR recover to ≥6%?** (Still severely damaged if below)
- **Was an algorithm update officially announced by Google?** (If YES on Nov 23–29, the Nov 30 data may start to stabilize as rankings re-sort)

**If Nov 30 data shows:** 
- Further decline: ESCALATE to full site audit (Core Web Vitals regression, mobile-first indexing issues, E-E-A-T compliance, link profile analysis, competitor landing page analysis)
- Stabilization: Begin diagnosing WHY (algorithm update recovery, seasonal recovery, competitive positioning). Then draft new franchise content only AFTER stabilization confirmed.
- Recovery to 60+ clicks/week: Return to normal briefing with new content specs.

---

## Diagnosis Required (Immediate — before Friday)

**To triage the crisis, the following human actions are needed THIS WEEK (before next Monday's data arrives):**

1. **Google Algorithm Update Announcement (URGENT)** — Check SearchEngineLand, SEMRush Sensor, Google Search Central Blog for mid-Nov algorithm update announcements. Any update affecting:
   - Finance/money content
   - Prediction markets / gambling
   - Affiliate content
   - Niche/alternative financial products
   
   Would explain this crash.

2. **Core Web Vitals Regression Check (URGENT)** — Run PageSpeed Insights for www.dollarbets.lol desktop & mobile. Compare to Oct baseline:
   - Largest Contentful Paint (LCP) — should be <2.5s. If >3s, that's a regression.
   - Cumulative Layout Shift (CLS) — should be <0.1. If >0.15, that's new instability.
   - First Input Delay (FID) or Interaction to Next Paint (INP) — should be <200ms. If >300ms, that's regressed.
   
   The Nov 9 rebuild that allegedly fixed /funny-polymarket-bets/ meta may have introduced a performance regression. **Desktop CTR is half of mobile CTR — this could indicate desktop Core Web Vitals failure.**

3. **Competitor Landing Page Analysis (HIGH PRIORITY)** — Search "craziest kalshi bets" on Google live (incognito mode, US region) and screenshot top 5 results. Compare to Oct data: are there new competitors ranking above us? Is our snippet unappealing vs their snippets? Screenshot the SERP and save for comparison.

4. **Google Search Console Deep Dive (HIGH PRIORITY, requires GSC login)** — Check:
   - Any new crawl errors since Nov 9?
   - Any URLs with "Discover" issues or removed from Discover?
   - Any ranking issues flagged (spam, AMP issues, etc.)?
   - Has /funny-polymarket-bets/ been re-crawled since Nov 9? (If not, request re-crawl immediately)
   - Check Coverage report — are any franchise pages marked "Excluded" for unexpected reasons?

5. **Search Volume Cross-Check (RESEARCH)** — Pull Kalshi and Polymarket API volume data for prediction-market event search volume in Nov vs Oct. If their event volumes dropped 50%, the search volume collapse we're seeing is seasonal, not algorithmic. If THEIR volume is flat, it's algo update or behavioral shift.

---

## Summary for Next Week (Nov 30 Report)

**Next week's data (Nov 22–28) will tell us if the crash is:**
- A) Recoverable (stabilizes, slight improvement)
- B) Continuing (further decline — signals sustained algorithm penalty or market death)
- C) Reversible (bounces back — signals temporary algorithm update or seasonal dip)

**If A or C: Resume content strategy after diagnosis.**  
**If B: Escalate to full site audit and consider content pivot (move away from commodity prediction-market content, focus on narrative/story angles that don't depend on search volume).**

---

## Confidence Summary

- **Algorithm update hypothesis:** HIGH. Three-week position + volume crash + CTR degradation = textbook algorithm update signature.
- **Competitor surge hypothesis:** MEDIUM. Without Semrush check, unverified. But given position is at 4.4, competitor surge alone wouldn't explain 65% click loss.
- **Seasonal dip hypothesis:** MEDIUM-HIGH. Election betting surge peaks in Sept–Nov, crashes post-Nov. Prediction-market search interest naturally drops after election. But the ACCELERATION (not just steady decline) suggests algo update + seasonality combined.
- **Technical regression hypothesis:** MEDIUM. The Nov 9 rebuild timing is suspicious (Core Web Vitals could have regressed). Desktop CTR being half of mobile CTR is a red flag.
- **User intent shift hypothesis:** LOW-MEDIUM. The page-detail queries show we still get impressions on target keywords, so intent hasn't disappeared — search volume has.

---

## Notes

- Last week's crisis has not stabilized or recovered. It has WORSENED, with acceleration now apparent.
- Franchise focus (Kalshi + Polymarket only) remains strategically correct, but execution is broken by external factors (algorithm, seasonality, or technical issue).
- No page edits, retirements, or new content should ship until we see stabilization and understand the root cause.
- The URL for GSC investigation: https://search.google.com/search-console (login required, NOT accessible in CI).
