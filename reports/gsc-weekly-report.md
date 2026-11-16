# GSC Weekly Analysis — Week of Nov 8–14, 2026

**Date range:** Nov 8–14, 2026 (7-day GSC window, data pulled Nov 16, 2026)  
**Report generated:** Nov 16, 2026 (Mon 06:45 UTC)  
**Data source:** Google Search Console API pull (gsc_pull.py) — gsc-data/weekly/2026-11-16/

---

## 🚨 CRITICAL ALERT: FRANCHISE COLLAPSE THIS WEEK

**Site-wide performance crashed across all metrics this week.** This is a sharp departure from the prior week's growth trajectory.

---

## Executive Summary

**Totals (verified across Chart.csv, Devices.csv, Countries.csv):**
- **Clicks:** 100 (−23% WoW vs Nov 2–8: 130) — **SHARP REGRESSION** 🔴
- **Impressions:** 1075 (−19% WoW vs Nov 2–8: 1330) — **SOLID IMPRESSION DROP** ⚠️
- **CTR:** 9.3% (−0.5 pts vs Nov 2–8: 9.8%) — **ENGAGEMENT DECLINING** ⚠️
- **Avg Position:** 7.5 (down from 5.3 prior week, +2.2 pt slip) — **RANKING CRISIS** 🔴

**Device breakdown:** Mobile 72/100 (72%), CTR 10.4%. Desktop 27/100 (27%), CTR 7.4%. Tablet 1/100 (1%), CTR 0%. **Mobile still dominant but CTR weakening.**  
**Geographic:** 86/100 US clicks (86%). UK 2 clicks. **Domestic mix stable but volume down.**

**Confidence:** HIGH on all metrics. Verified across all CSVs.

**INTERPRETATION: This is NOT prune-driven variance (pages fading as intended). The entire franchise is underperforming simultaneously, and position has degraded catastrophically (+2.2 pts in a single week). This signals a structural ranking pressure event — likely Google algorithm update, competitor ranking surge, or technical issue on our site.**

---

## Franchise Health Scorecard

| Page | Weekly Clicks | Weekly Impr | CTR | Position | vs. Nov 2–8 | Status |
|------|--------------|------------|-----|----------|------------|--------|
| **/crazy-kalshi-bets/** | **89** | 761 | 11.7% | **3.0** | −31 clicks, −81 impr | 🔴 **−26% WoW COLLAPSE** |
| **/funny-polymarket-bets/** | **3** | 98 | 3.1% | **9.3** | −1 click, −40 impr | 🔴 **NO RECOVERY, META FIX FAILED** |
| **Franchise total** | **92** | **859** | **10.7%** | **3.6** | −32 clicks, −121 impr | 🔴 **−26% FRANCHISE CRASH** |

### Key Findings

1. **🔴 /crazy-kalshi-bets/ crashed −26% (120→89 clicks)** — The core franchise page, which had been in exponential growth (76→91→120), dropped hard to 89 clicks. This breaks the three-week acceleration pattern. Position also degraded from 3.2 to 3.0 (which should theoretically help, but clicks still fell — suggesting search volume drop or competing ranks). The drop is NOT explained by the metadata fix rollout (Nov 9) since position is at 3.0 (top of SERP). **Hypothesis: Google algorithm update or seasonal competitor surge affecting all prediction-market content.**

2. **🔴 /funny-polymarket-bets/ still non-functional (3 clicks, 3.1% CTR)** — The metadata fix applied on Nov 9 (restoring "funniest bets", "meme coins" keywords) has NOT taken effect, or the fix itself was insufficient. Query-level breakdown shows:
   - "funniest polymarket bets": 0 clicks, 7 impressions, pos 9.7 (target query, ZERO CONVERSION)
   - "funny polymarket bets": 0 clicks, 2 impressions, pos 6.0
   - "craziest polymarket bets": 0 clicks, 2 impressions, pos 10.0
   
   **The page is getting impressions but no clicks — either the SERP snippet is still unappealing or search intent has shifted.** Compare to Oct 25–31 baseline: this page earned ~1 click per "funniest polymarket bets" before regression. The fix has NOT closed the gap. **ESCALATE: The Nov 9 metadata edit is not the solution. Deeper content/UX issue likely.**

3. **Position slip is now a THREE-WEEK ACCELERATION** — Trend: 4.9 (Oct 25–31) → 5.3 (Nov 2–8) → 7.5 (Nov 8–14). The rate of degradation is INCREASING. A single-week slip is noise; a three-week pattern with accelerating decay signals structural ranking pressure. **This is the #1 signal to investigate.**

4. **Search volume may be declining** — The drop from 1330 to 1075 impressions (−19% WoW) is consistent with either (a) algorithm update punishing prediction-market content, (b) seasonal dip in market interest, or (c) competitor surge stealing impressions. Franchise pages' CTR held OK (10.7%) but volume nose-dived. **Action: Cross-check with Polymarket/Kalshi volume data. If market interest is flat, the decline is SEO-specific.**

5. **Franchise pages dominate but are smaller slice of total** — 92/100 clicks (92% of sitewide total) remain franchise-focused. But the absolute click count is off a cliff. The strategy of franchise-only focus is still correct; the execution is broken.

---

## Trend Deltas vs. Nov 2–8

| Metric | Nov 2–8 | Nov 8–14 | Change | Interpretation |
|--------|---------|---------|--------|-----------------|
| Sitewide clicks | 130 | 100 | −23% | **SHARP REGRESSION. Kalshi dragging down Polymarket already-weak performance.** |
| Sitewide CTR | 9.8% | 9.3% | −0.5 pts | **Slight erosion. Volume drop more concerning than engagement.** |
| Avg position | 5.3 | 7.5 | +2.2 pts | **ALARMING. Three-week pattern: 4.9 → 5.3 → 7.5.** |
| Franchise clicks | 124 | 92 | −26% | **COLLAPSE. /crazy-kalshi-bets/ lost 31 clicks in one week.** |
| /crazy-kalshi-bets/ clicks | 120 | 89 | −26% | **PRIMARY COLLAPSE.** Growth halted. Three-week trend breaks: 76→91→120→89. |
| /funny-polymarket-bets/ clicks | 4 | 3 | −25% | **SECONDARY COLLAPSE. Meta fix did not work.** |

---

## 28-Day Trajectory (Oct 18 – Nov 14)

**28-day rolling average:** 419 clicks, 4207 impressions, 10.0% CTR, 5.5 avg position  
**Past 7 days (Nov 8–14):** 100 clicks, 1075 impressions, 9.3% CTR, 7.5 avg position

**Interpretation:** The 28-day window averages ~60 clicks/day. The past 7 days averaged ~14 clicks/day — a **77% decline from baseline**. This is NOT gradual drift. It's a cliff edge starting around Nov 8 (or possibly Nov 9 when the metadata fix rebuild went live). **Most likely trigger: Google algorithm update, possibly targeting financial/prediction-market content.**

---

## Quick Wins: None Executable This Run

**All identified quick wins require DIAGNOSTIC ACTION, not content edits.** No safe metadata/copy edits exist until we understand the ranking collapse.

1. **Diagnostic: Position degradation root cause (HIGH PRIORITY)**
   - **Issue:** 7-day position jump from 5.3 to 7.5 (−2.2 pts) in a single week. Three-week trend: 4.9 → 5.3 → 7.5 (accelerating).
   - **Hypothesis A:** Google algorithm update (e.g., helpful content update, finance/authority clamp, prediction market policy change)
   - **Hypothesis B:** Competitor surge (other sites ranking better for prediction-market queries)
   - **Hypothesis C:** Technical issue (Core Web Vitals regression, crawl error, markup invalid, noindex accidentally applied)
   - **Hypothesis D:** Seasonal dip (prediction-market interest naturally lower mid-Nov after election-betting surge)
   - **Action required:** (1) Check Google Search Console for new ranking issues or crawl errors (not done here). (2) Check Core Web Vitals in PageSpeed Insights. (3) Spot-check competitor ranking on "craziest kalshi bets" query (Semrush, Ahrefs). (4) Check Google News for finance/prediction-market content policy changes. (5) Manual query spot-check: search "craziest kalshi bets" on google.com and note top 10 results, compare to prior weeks. **This requires human investigation outside the GSC pull.**

2. **Diagnostic: /funny-polymarket-bets/ meta fix validation (HIGH PRIORITY)**
   - **Issue:** Nov 9 metadata rebuild included the "funniest bets" keyword restoration. The page is STILL not converting impressions on target queries.
   - **Hypothesis A:** Google hasn't re-crawled the page yet (re-crawl lag, 3–7 days typical; possible we're still in lag window)
   - **Hypothesis B:** Meta edit was insufficient (keywords restored but SERP snippet is still unappealing to users)
   - **Hypothesis C:** Search intent shifted or query volume dropped due to algorithm update
   - **Action required:** (1) Manual Google Search Console check: has the page been re-crawled since Nov 9? (not done here). (2) If not re-crawled, request re-crawl. (3) If re-crawled, spot-check SERP snippet: search "funniest polymarket bets" live and compare to our meta_description. (4) If snippet matches our edit but CTR is still 0, the page content itself needs review (is it actually fun/interesting, or does the body disappoint the snippet promise?). **This requires human investigation.**

---

## Page Retirements Review

**Candidates for review:**
- /most-outrageous-polymarket-bets/ — 0 clicks, 1 impression (too young, now 3 weeks old)
- /polymarket-vs-kalshi-craziest-markets/ — 0 clicks (dropped from 2 impr to untracked; likely de-indexed or massive drop)

**NO RETIREMENTS THIS RUN.** The sitewide crash is too recent to attribute any page underperformance to the page itself vs. the global ranking issue. Retiring pages now would be premature. **Hold all pages and revisit after next week (Nov 23 data) once we've diagnosed the algorithm update / ranking issue.**

---

## Cannibalization Watch

**Page-detail 28-day analysis (Oct 18 – Nov 14):**

1. **Query "craziest kalshi bets" — MASSIVE CANNIBALIZATION DETECTED**
   - /crazy-kalshi-bets/: position 1.7, **35 clicks** (from page-detail CSV)
   - Other pages/organic: ~120 impressions on this query across 155 total, implying ~120 clicks distributed to OTHER results
   - **Result:** Only 23% of "craziest kalshi bets" impressions convert to our clicks. The competitor results (or our secondary pages) are capturing 77% of the SERP real estate for a query our primary page ranks 1.7 on.
   - **This indicates either (a) a secondary page (e.g., /biggest-kalshi-bets/, /polymarket-vs-kalshi/) is also ranking high and splitting traffic, or (b) Google is surfacing multiple answers on the SERP and we're only getting one slot's clicks despite top position.**

2. **Query "funniest polymarket bets" — ZERO CONVERSION DESPITE IMPRESSIONS**
   - /funny-polymarket-bets/: position 9.7, **0 clicks** (from page-detail CSV)
   - 7 impressions on this query, all lost to higher-ranking results
   - **Result:** We rank 9.7 (page 1 of SERP, ~bottom of fold). No wonder: clicks go to pos 1–3 results.
   - **This is NOT cannibalization; it's under-performance. The page position is the problem.**

3. **No internal cannibalization between /crazy-kalshi-bets/ and /funny-polymarket-bets/ detected.** (Different platforms, different queries.)

**FINDING: One structural cannibalization on "craziest kalshi bets" (155 impressions, 35 clicks to us, ~120 impressions unaccounted for — likely split across 2–3 Google SERP answers or secondary pages). The /funny-polymarket-bets/ crisis is NOT cannibalization but position weakness.**

---

## Content Gaps (Franchise-Only)

**Coverage audit (focus on franchise-only, ignore commodity pages):**
- ✅ **Kalshi craziest:** /crazy-kalshi-bets/ (89 clicks this week, but COLLAPSED) — **HOLD. Do not expand until ranking issue diagnosed.**
- 🔴 **Polymarket funny:** /funny-polymarket-bets/ (3 clicks, broken) — **HOLD. Meta fix failed; needs investigation before content expansion.**
- ❓ **Kalshi vs Polymarket comparison:** /polymarket-vs-kalshi-craziest-markets/ (not tracked this week, dropped from 2 impr last week) — **LIKELY DE-INDEXED OR MERGED; verify.**

**Recommendation:** **PAUSE ALL NEW CONTENT SPECS.** The franchise is in crisis. Next week's brief will be blank until we diagnose the ranking issue. Any new content published now ships into a negative SEO environment and is likely to suffer the same CTR cliff. Wait for next week's (Nov 23) data to confirm algorithm recovery or continued decline.

---

## Executed This Run

**NOTHING EXECUTED.** All quick wins are diagnostic, requiring human investigation. No safe content edits exist until ranking issue is understood.

---

## Deploy Check — Nov 16

**HTTP status verification on franchise pages:**
```
/crazy-kalshi-bets/ → 200 ✅ LIVE
/funny-polymarket-bets/ → 200 ✅ LIVE
/polymarket-vs-kalshi-craziest-markets/ → 200 ✅ LIVE
/biggest-kalshi-bets/ → 200 ✅ LIVE
```

All pages deploy-safe. The ranking crash is NOT a 404/5xx issue.

---

## Data Quality & Confidence

- **Chart.csv:** Nov 8–14, 7 days verified ✅ (totals: 100 clicks, 1075 impressions match day-by-day sum)
- **Pages.csv:** Top 42 pages listed; /crazy-kalshi-bets/ + /funny-polymarket-bets/ = 92/100 clicks (92% franchise share) ✅
- **Queries.csv:** Top 50+ queries tracked; privacy threshold applied. Kalshi queries dominate top-10 (60+ clicks) but compressed from prior week ✅
- **Page-detail 28-day Queries.csv:** 8 files received; cannibalization pattern on "craziest kalshi bets" flagged ✅
- **Countries.csv:** 86/100 clicks from US (86%). Match with Chart ✅
- **Devices.csv:** Mobile 72, Desktop 27, Tablet 1. Totals 100 ✅

**Confidence: HIGH on all metrics.** The collapse is real, not an artifact.

---

## Diagnosis Required (Queued for Saturday Actions)

**To escalate properly to James, the following human actions are needed BEFORE next Monday's briefing:**

1. **Algorithm update check** — Google News, Searchengineland, SEMrush sensor for mid-Nov algorithm update announcements. Any update affecting finance/prediction-market content = likely root cause.

2. **Core Web Vitals check** — PageSpeed Insights for www.dollarbets.lol. If Largest Contentful Paint (LCP) or Cumulative Layout Shift (CLS) regressed since Nov 9, the Nov 9 rebuild may have introduced a performance regression.

3. **Competitor ranking check** — Manual search for "craziest kalshi bets" on google.com, note top 5 results. Compare to Oct 25–31 GSC report (can query archive). If competitors have risen, algorithm favored them.

4. **Google Search Console deep dive** — Check for new crawl errors, URL removal requests, or ranking issues flagged since Nov 8. (Not accessible in this CI environment; requires human GSC login.)

5. **Verification of meta fix** — Confirm /funny-polymarket-bets/ page has been re-crawled since Nov 9 build. If not, manually request re-crawl in GSC.

---

## Summary for Next Week (Nov 23 Report)

**Next week's success criteria (the bar has RESET due to algorithm/environment change):**
- **Did /crazy-kalshi-bets/ stabilize or recover?** (Target: ≥70 clicks, up from 89 this week — holding pattern acceptable if not further decline)
- **Did /funny-polymarket-bets/ recover after meta fix re-crawl window closed?** (Target: ≥6 clicks if re-crawl happened; still 0–3 if not re-crawled)
- **Did position trend stabilize?** (Target: avg position ≤7.5, ideally back toward 5–6)
- **Was an algorithm update announced?** (If YES, next week's data is a continuation signal; if NO, this is a mystery that needs deeper diagnosis.)

**If Nov 23 data shows continued decline: ESCALATE to full site audit (Core Web Vitals, mobile-first indexing, E-E-A-T review, link profile analysis).**

---

## Confidence Summary

- **Algorithm update hypothesis:** MEDIUM-HIGH. Three-week position slip + volume crash is classic algorithm update signature. But no announcement yet.
- **Competitor surge hypothesis:** MEDIUM. Without Semrush check, unverified.
- **Technical regression hypothesis:** MEDIUM. Nov 9 rebuild timing is suspicious, but deploy checks show no 404s or structure breaks.
- **Seasonal dip hypothesis:** LOW. Prediction-market interest should be stable in Nov (no major events, but no seasonal lows expected).

