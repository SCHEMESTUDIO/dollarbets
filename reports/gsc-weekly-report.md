# GSC Report — 2026-07-13

**Window:** 2026-07-05 → 2026-07-11 (GSC "Last 7 days", ends 2 days ago per API lag). Data delivered by `scripts/gsc_pull.py` in-workflow — **all 7 weekly CSVs + 28-day CSVs + 6 populated page-detail files present.** This is the first API-grade pull with full page-detail intersection data since 2026-06-15.

**⚠️ Comparison caveat:** the last *delivered* weekly report covers **6/15–6/21** (the 6/22, 6/29, 7/06 pipeline pulls did not run — see CLAUDE.md "migration not committed"). So "vs last week" below is really **vs 3 weeks ago**. Raw current-week numbers are **High** confidence; anything framed as a *trend* is **Medium** (three unmeasured weeks in between).

## Headline — franchise clicks surged; concentration is now near-total on one page

The number that matters jumped hard: **total clicks 13 → 34** vs the last delivered report, and **33 of 34 (97%) landed on franchise pages.** The engine is `/crazy-kalshi-bets/`: **10 → 32 clicks, CTR 6.45% → 9.6%, position 7.9 → 7.4, impressions 155 → 334.** Up on every single axis, roughly tripling clicks on doubled impressions. **Confidence: High** on the raw numbers (Chart.csv, Devices.csv, Countries.csv all reconcile at exactly **34 clicks / 428 impressions**); **Medium** on attributing the *rate* of gain given the 3-week measurement gap.

**Ignore the total-impression dip — it's the prune, not a regression.** Total 7-day impressions 516 → 428 (−17%). That is entirely composition: the `/politicians-with-prediction-markets-june-2026/` intent-mismatch sink **dropped out of the 7-day window** (0 imp this week; 270 imp over the trailing 28 days, so it front-loaded earlier and has faded), and `/can-you-bet-on-the-weather/` (noindexed) fell to **7 imp** (was 94). Meanwhile **franchise impressions rose** (crazy-kalshi 155 → 334, +115%). Total down while the franchise doubled its exposure is the healthiest possible read. **Confidence: High.**

### Verified totals (cross-checked)

| Window | Clicks | Impressions | CTR | Avg Position |
|---|---|---|---|---|
| 7-day (7/05–7/11) | **34** | **428** | 7.9% | 7.4–9.9 daily |
| 7-day last delivered (6/15–6/21) | 13 | 516 | 2.5% | ~8 late-week |
| 28-day (6/14–7/11) | 76 | ~1,637 | 4.6% | ~11 |

Reconciliation: Chart.csv = 34 clk / 428 imp; Devices.csv = 34 / 428; Countries.csv clicks sum = 34 — all three agree. Pages.csv (34 clk) and Queries.csv (15 clk shown) differ due to GSC privacy thresholds, as expected. **Confidence: High.**

---

## Franchise scorecard (the real scorecard)

| Page | 7-day this wk | 7-day last delivered (6/15–21) | Read |
|---|---|---|---|
| `/crazy-kalshi-bets/` | **32 clk / 334 imp / 9.6% / pos 7.4** | 10 / 155 / 6.45% / 7.9 | **Up on every axis, dramatically.** Clicks ~3.2×, CTR +3.1pp, position +0.5, impressions +115%. **94% of all site clicks.** The workhorse is compounding. |
| `/funny-polymarket-bets/` | **1 clk / 53 imp / 1.9% / pos 12.6** | 2 / 49 / 4.08% / 9.39 | **The one franchise regression — FLAG.** Position slipped page-1 → page-2 (9.4 → 12.6), CTR more than halved. Impressions held (49→53) so it's a *ranking* slip, not exposure loss. Only 3% of clicks now. Needs fresh live examples (brief IMPROVE slot). |
| `/polymarket-vs-kalshi-craziest-markets/` | 0 clk / 4 imp / pos 8.8 (28d: 1/9/8.6) | 0 / 4 / 11.8 | **Still no authority.** Its page-detail file is **empty** — <2 imp on any single query. The inbound internal links from crazy-kalshi + funny-polymarket now exist (verified in both JSONs) and it's holding pos ~8.8, but not accumulating query-level exposure. Watch. |
| `/weird-prediction-markets/` | absent weekly (28d: 1/8/11.6) | 0 / 3 / 9.0 | Trivial volume; page-1-ish on 28d. Benign. |
| `/most-outrageous-polymarket-bets/` | absent weekly (28d: 0/4/9.2) | 0 / 3 / 9.0 | Page-1 position, 0 clicks, negligible impressions. Watch. |
| `/weirdest-active-polymarket-markets-july-2026/` | absent (<2 imp) | n/a (shipped since) | **Live + indexable + 200, but NOT ranking.** Same failure mode the June edition had — the politicians page still owns the "popular active markets" query family (below). Reposition + authority, not rebuild. |
| `/weirdest-active-polymarket-markets-june-2026/` | absent (<2 imp) | absent | Now 3 weeks stale; superseded by July edition but neither displaces politicians. Consolidation/retire candidate (brief). |
| `/hall-of-filth/george-whitesides-ca-27-primary-bet/` | 0 / 2 / pos 6.5 | n/a | Page-1 on trivial volume — dependable Hall of Filth pattern holds. |

**Concentration: 33 of 34 clicks (97%) franchise** (crazy-kalshi 32 + funny-polymarket 1; the 1 `/about/` click is brand/navigational). The roundup thesis is fully validated — **but 94% of clicks now sit on a single page.** That is the flip side of a healthy franchise: extreme single-page concentration is a resilience risk if `/crazy-kalshi-bets/` ever slips. Diversifying franchise click sources (get funny-polymarket back to page 1, get a second kalshi or Hall of Filth page earning) is the strategic priority, not new commodity surface. **Confidence: High.**

---

## Prune / noindexed-page fade check — working as intended (High confidence)

| Page | This wk (7d) imp | Prior reference | Status |
|---|---|---|---|
| `/can-you-bet-on-the-weather/` (noindexed) | 7 | 94 (6/15–21), 133 (6/08–14) | **Fading hard on schedule.** 28-day still shows 138 imp at pos 34.8 (residual tail); the 7-day window is nearly clear. India/weather-skew queries all pos 37–77. No action. |
| `/politicians-with-prediction-markets-june-2026/` | 0 (out of window) | 198 (6/15–21) | **Fell out of the 7-day window entirely.** 28-day 270 imp / 0 clk / pos 10.2 — the intent-mismatch sink has front-loaded and faded from recent days. See cannibalization note: it still *owns* the "popular active markets" family on a 28-day basis, which is the real problem. |
| `/craziest-kalshi-markets/` (thin sibling) | absent weekly (28d: 0/2/23.5) | 0 / 2 / 23.5 | Still page-3, still 0 clicks. 301-consolidation candidate carried from last brief — **not yet executed** (needs a `vercel.json` redirect, which is outside CI commit scope). |

No noindexed page is a content gap. The prune is complete and clean. **Confidence: High.**

---

## Franchise quick wins (pos 4–15, ≥2 imp, 0 clicks) — 7-day

| # | Query | Pos | Imp | Page | Action |
|---|---|---|---|---|---|
| 1 | weirdest kalshi bets | 8.5 | 13 | `/crazy-kalshi-bets/` | **Not executed — deliberately.** Phrase is already in the title ("The Weirdest Markets"), meta ("weirdest bets on Kalshi today"), and a dedicated body H2. This is a CTR-at-position problem, not a coverage gap; expected clicks at pos 8.5 on 13 imp is <1. Adding more "weird" = stuffing. |
| 2 | kalshi weirdest bets | 6.4 | 5 | `/crazy-kalshi-bets/` | Not executed — already covered; page-1 already. |
| 3 | kalshi weird bets / weird kalshi bets | 9.6 / 8.0 | 5 / 3 | `/crazy-kalshi-bets/` | Not executed — covered. |
| 4 | strangest kalshi bets | 5.7 | 3 | `/crazy-kalshi-bets/` | Not executed — "strangest" is the one un-covered synonym, but at 3 imp the upside is marginal and the meta is already keyword-dense. Stuffing risk > reward. |
| 5 | polymarket funny | 11.0 | 3 | `/funny-polymarket-bets/` | Not executed — already in meta; the page's problem is ranking (pos 12.6), not this phrase. |

**Executed this run: 1 edit (of the allowed 3), on purpose.** The kalshi quick-win queries are all already covered on-page — forcing edits to hit the cap would be exactly the low-value churn the editorial rules warn against.

### Executed this run

- **`/crazy-kalshi-bets/`** — removed the stale month label from the body heading **"the craziest kalshi bets live right now (june 2026)"** → **"the craziest kalshi bets live right now"**, and bumped `last_updated` 2026-06-25 → 2026-07-13. Rationale: the page is live in July with a June label; its market examples are evergreen forward-dated longshots (Taylor Swift/Pope before 2027, NASA moon before 2028, CA 8.0 before 2028), so a freshness bump is honest, and dropping the month is pure upside — this page ranks for no month-tail queries, so there's nothing to lose and a stale label to clear on the page driving 94% of clicks. Rebuilt with `generate_content.py` — no errors, page still indexable (no `noindex`, no robots meta), substance and slug unchanged. **Confidence: Medium** the freshness bump aids re-exposure; **High** it does no harm.

---

## Cannibalization watch — page-detail intersection data restored (High confidence)

Six page-detail Queries files present this week, so this is verified from true page×query intersections, not inferred.

- **No franchise-vs-franchise cannibalization.** `/crazy-kalshi-bets/` owns the *entire* "kalshi" query family (craziest/weirdest/wildest/strangest — all 17 kalshi queries route to it). `/funny-polymarket-bets/` owns the *entire* polymarket family (craziest/funniest/absurd/stupid polymarket — all 12 route to it). **Zero queries appear in both franchise files.** Clean separation. **Confidence: High.**
- **The real intersection issue is intent-mismatch, not cannibalization:** `/politicians-with-prediction-markets-june-2026/` owns **"polymarket popular markets june 2026"** (105 imp, pos 8.7) and **"polymarket popular active markets june 2026"** (94 imp, pos 13.1) — a *politicians* page answering a *"what's live right now"* query at 0% CTR. The intended-takeover pages (`weirdest-active-polymarket-markets-june-2026` and the new July edition) each earn **<2 imp** — neither displaces it. Google has not reassigned the query family. **Confidence: High** (intersection data confirms which page holds the impressions).

---

## Franchise content gaps

1. **Monthly "active markets" cadence is broken — AUGUST edition + decisive reposition (HIGH).** The recurring ~100–200 imp/mo on "polymarket popular/active markets [month] 2026" has now been landing 0% on the *politicians-june* page for months. We shipped June and July "weirdest-active" pages; **neither ranks** (<2 imp each). Two unmeasured weeks of a new page not displacing = the title-alignment lever alone is not working. Moves: (a) ship the **August** edition on the monthly cadence; (b) add real inbound authority (already-linked from crazy-kalshi/funny-polymarket, but consider a homepage/board link); (c) **retire the intent-mismatch politicians-june page** (301 or noindex) so it stops absorbing the query family. **US share: Medium-High.**
2. **Recover `/funny-polymarket-bets/` to page 1 (MEDIUM).** The only franchise regression. Metadata is already optimized (the craziest/funniest superlatives shipped) — the lever now is a genuine content refresh with current live markets, which CI can't do without board data. IMPROVE slot.
3. **De-concentrate franchise clicks (MEDIUM-HIGH, strategic).** 94% on one page is a resilience risk. Named-market Hall of Filth pages reliably hit page-1 on low volume (Whitesides pos 6.5, and the Obama/Lear/deBessonet precedents) — the cheapest way to add a second earning franchise page. Keep mining the query log for named-entity queries at pos <15.

No commodity clusters listed as gaps, per strategy.

---

## Geographic + device notes

- **US skew strengthened:** US **317/428 imp (74%)**, **25/34 clicks (74%)** — up from 54% imp last report. Every franchise cluster is US-majority. No cluster >50% non-US to deprioritize. Canada 21 imp/2 clk, UK 13 imp/2 clk at pos 12.4. **Confidence: High.**
- **Mobile dominant, desktop now converting a little:** Mobile 30 clk / 343 imp / 8.7% / pos 7.8; Desktop 4 clk / 84 imp / 4.8% / pos 11.1 (was 0% last report). Mobile carries 88% of clicks. **Confidence: High.**

---

## Day-by-day (7-day chart)

| Date | Clicks | Imp | CTR | Pos |
|---|---|---|---|---|
| 2026-07-05 | 6 | 62 | 9.7% | 9.9 |
| 2026-07-06 | 7 | 74 | 9.5% | 8.1 |
| 2026-07-07 | 4 | 46 | 8.7% | 7.4 |
| 2026-07-08 | 1 | 42 | 2.4% | 9.3 |
| 2026-07-09 | 2 | 34 | 5.9% | 8.4 |
| 2026-07-10 | 4 | 58 | 6.9% | 9.8 |
| 2026-07-11 | 10 | 112 | 8.9% | 7.4 |

Broadly healthy across the whole week — no single day carries it. The 7/11 spike (10 clk / 112 imp) is the last un-lagged day catching full volume; CTR held 8–10% on the strong days. Position sat page-1 (7.4–9.9) every day, a clear improvement over the mid-June page-2 readings (14–18). **Confidence: High.**

---

## Data completeness / pipeline status (for James)

- **Full API pull delivered this week** — all weekly + 28-day + 6 page-detail CSVs present. First complete pull (with intersection data) since 2026-06-15. If this ran from the committed GitHub Actions workflow, **the cloud migration is now live** (it was flagged uncommitted as recently as 2026-07-06). Worth confirming in the Actions tab.
- **Deploy check:** all 8 franchise slugs + both active-markets editions + a Hall of Filth page return **200 LIVE**. No broken pages. See brief for detail.
- **Two carried structural items still outside CI commit scope** (need manual commit — `vercel.json`/`scripts/` are not staged by `ci_guarded_commit.sh`): the `/craziest-kalshi-markets/` → `/crazy-kalshi-bets/` 301, and the politicians-june-2026 retirement redirect. Neither ships automatically from this run.
