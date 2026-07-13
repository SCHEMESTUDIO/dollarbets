# GSC Report — 2026-06-22

**Data source caveat (read first):** the launchd `gsc-pull` job did **not** deliver `weekly/2026-06-22/` this morning (the directory is absent; latest pipeline pull is `2026-06-15`). James manually exported two zips instead. This report is built from the **manual "Last 7 days" export** (window **2026-06-15 → 2026-06-21**, Mon–Sun, API-grade) plus a manual **"Last 3 months" export** used as the longer-trend proxy. **Limitation:** the manual export contains **no `page-detail/*-Queries.csv` intersection files**, so cannibalization analysis this week is inferred from the page-level and query-level tables only — not from true page×query intersections. Flag each affected claim accordingly. **Confidence: High** on totals; **Medium** on anything needing intersection data.

## Headline — franchise clicks up again, concentration now total

The number that matters went the right way for the second week running: **total clicks 10 → 13 WoW (+30%), and 100% of them (13/13) landed on franchise pages.** `/crazy-kalshi-bets/` is the engine — **7 → 10 clicks (+43%), CTR 4.4% → 6.45%, position 8.7 → 7.9** (better on all three). `/funny-polymarket-bets/` softened (3 → 2 clicks) but on *halved* impressions (87 → 49) with CTR actually rising (3.4% → 4.08%), so the dip is reduced query exposure on small numbers, not a conversion problem. **Confidence: High** — Chart.csv, Devices.csv, and Countries.csv all reconcile at exactly **13 clicks / 516 impressions**.

**Ignore the impression drop — it's the prune, not a regression.** Total 7-day impressions *fell* 694 → 516 (−26%). That is the noindexed/mismatch pages bleeding out as designed: `/can-you-bet-on-the-weather/` 133 → 94 imp (still recrawling, India-skewed weather queries), and the `/politicians-with-prediction-markets-june-2026/` intent-mismatch page 285 → 198 imp. Strip those two zero-click sinks (292 imp) and the remaining ~224 impressions are franchise-relevant and click-converting at ~6%. **Franchise-only CTR ≈ 6.2%** (13 clicks / 211 franchise impressions), up from ~4.1% last week. **Confidence: High.**

### Verified totals (cross-checked)

| Window | Clicks | Impressions | CTR | Avg Position |
|---|---|---|---|---|
| 7-day (6/15–6/21) | 13 | 516 | 2.5% | ~14 (site) / ~8 late-week |
| 7-day prior (6/08–6/14) | 10 | 694 | 1.4% | 14.6 |
| 3-month (≈5/05–6/21, proxy) | 50 | ~2,531 | 2.0% | ~30 |

7-day reconciliation: Chart.csv = 13 clk / 516 imp; Devices.csv = 13 / 516; Countries.csv clicks sum = 13 — all three agree. Pages.csv (13 clk) and Queries.csv (5 clk shown) differ due to GSC privacy thresholds, as expected. **Confidence: High.**

Note the late-week position move in the good direction: 6/20 pos 8.8 / CTR 4.17%, 6/21 pos 8.0 / CTR 8.33%. That is the dead page-80 commodity entries finally clearing the average, plus franchise pages holding page 1 — composition, not a ranking surge. **Confidence: Medium-High** (attribution inferred; the daily chart can't decompose by page).

---

## Franchise scorecard (the real scorecard)

| Page | 7-day this wk | 7-day last wk | Read |
|---|---|---|---|
| `/crazy-kalshi-bets/` | **10 clk / 155 imp / 6.45% / pos 7.9** | 7 / 158 / 4.4% / 8.7 | **Up on every axis.** Clicks +43%, CTR +2pp, position +0.8. **77% of all clicks.** Last week's metadata edit is working. |
| `/funny-polymarket-bets/` | **2 clk / 49 imp / 4.08% / pos 9.39** | 3 / 87 / 3.4% / 8.9 | **Softer, but benign.** Clicks −1 on impressions −44%; CTR *rose*. Exposure dropped, not conversion. 15% of clicks. Edited this run (below). |
| `/weird-prediction-markets/` | 1 clk / 2 imp / 50% / pos 14.5 | 0 / 3 / — / 9.0 | First click; trivial volume. |
| `/most-outrageous-polymarket-bets/` | 0 / 3 imp / pos 9.0 | 0 / 2 / 32.5 | Position jumped page-3 → page-1; still 0 clicks. Watch. |
| `/craziest-kalshi-markets/` | 0 / 2 imp / pos 23.5 | 0 / 5 / 10.4 | Thin sibling of crazy-kalshi-bets; position volatile. Consolidation candidate (brief). |
| `/polymarket-vs-kalshi-craziest-markets/` | absent (0 imp) | 0 / 4 / 11.8 | Dropped out of the 7-day window. Needs internal-link authority — an edit adding that link from funny-polymarket exists but **has not shipped** (see deploy check). |
| `/weirdest-active-polymarket-markets-june-2026/` | absent (<2 imp) | n/a (new) | Live + indexable, but **not yet ranking** for its target demand — the politicians page still owns those queries. Reposition, not rebuild (brief). |

**Concentration: 13 of 13 clicks (100%) are franchise this week** (crazy-kalshi 10 + funny-polymarket 2 + weird-prediction 1). The franchise-roundup thesis holds and is tightening. **Confidence: High.**

---

## Prune / noindexed-page fade check

Working as intended. **Confidence: High.**

| Page | This wk (7d) imp | Last wk (7d) imp | Status |
|---|---|---|---|
| `/can-you-bet-on-the-weather/` (noindexed) | 94 | 133 | **Fading** — recrawl honoring noindex; India-skewed weather queries. No action. |
| `/betting-odds-explained/`, `/best-prop-bets-today-nba/`, `/prediction-markets-vs-sports-betting/`, `/what-is-a-prop-bet/` | not in 7-day top-12 (≈0) | ≈0–1 | Gone from the active window. Prune complete on these. |
| `/weather-betting-markets/` | 4 | 3 | Negligible residual. |

The weather page is the only sizeable noindexed survivor and it is on a clean downward path (133 → 94). Do **not** treat any of these as clusters needing content. **Confidence: High.**

---

## Non-franchise impression sinks (context, not scorecard)

- **`/politicians-with-prediction-markets-june-2026/` — 0 clk / 198 imp / pos 10.43.** Still the #1 zero-click sink. It surfaces for **"polymarket popular markets june 2026"** (85 imp, pos 8.8) and **"polymarket popular active markets june 2026"** (62 imp, pos 13.6) — a *politicians* page answering a *"what's live right now"* query. The intent mismatch caps CTR at 0% despite a near-page-1 position. Recurring monthly demand (~147 imp/wk). **Confidence: High** the demand is real and recurring.
- The fix page (`/weirdest-active-polymarket-markets-june-2026/`) was built last week and is live + indexable, but **Google still ranks the politicians page** for the query family — the new page isn't displacing it yet. That makes this an **internal-link + title-alignment** job, not a new-build job (brief). **Confidence: Medium** (can't see per-query page assignment without intersection data; inferred from which page holds the impressions).

---

## Franchise quick wins (pos 4–15, ≥2 imp, 0 clicks) — 7-day

| # | Query | Pos | Imp | Page | Action |
|---|---|---|---|---|---|
| 1 | crazy kalshi bets | 8.6 | 15 | `/crazy-kalshi-bets/` | **Not executed — deliberately.** Phrase already in title + meta; page is winning on "craziest" variants. 0 clicks on 15 imp at pos 8.6 is statistically unremarkable (expected <1 click). A 3rd consecutive weekly edit here = over-optimization. |
| 2 | strangest kalshi bets | 9.0 | 4 | `/crazy-kalshi-bets/` | Not executed — "strangest" is the only un-covered synonym; adding it to an already keyword-dense meta risks stuffing for marginal upside. |
| 3 | weirdest bets on kalshi today | 9.67 | 3 | `/crazy-kalshi-bets/` | Already in meta. No action needed. |
| 4 | craziest polymarket bets / polymarket funniest bets | 9 / 9 (3-mo) | — | `/funny-polymarket-bets/` | **EXECUTED this run** — folded both superlatives into the meta naturally (below). |

**I executed 1 of the allowed 3 edits, on purpose.** Both kalshi winners already carry on-target metadata for their quick-win queries, and last week's edits are visibly converting. Forcing edits to hit the cap would be the low-value churn the editorial rules warn against. The one genuinely additive edit went to the page that softened.

### Executed this run (queued for the 11:30 publish)

- **`/funny-polymarket-bets/`** — `meta_description` changed from "…the most ridiculous Polymarket bets and crazy Polymarket bets…" to **"…the most ridiculous, craziest, and funniest Polymarket bets…"**. This naturally captures the page's own zero-click brand queries *"craziest polymarket bets"* (pos 9) and *"polymarket funniest bets"* (pos 9) without stuffing, and drops a redundant duplicate. `last_updated` bumped to 2026-06-22 (freshness, to aid re-exposure after the impression dip). Rebuilt with `generate_content.py` — no errors, page still indexable (no noindex), `dateModified` 2026-06-22. Substance and slug unchanged.

---

## Cannibalization watch (LIMITED — no intersection data this week)

The manual export has no `page-detail/*-Queries.csv`, so these are **inferred from page+query tables, not verified intersections. Confidence: Medium.**

- **"craziest kalshi" family:** `/crazy-kalshi-bets/` (pos 7.9, converting) vs `/craziest-kalshi-markets/` (pos 23.5, 0 clicks, thin). The thin sibling earns impressions on the same query family while ranking page-3 — likely splitting signal. **Consolidation candidate** (301 the thin one into the winner). Spec'd in the brief.
- **"funny prediction markets"** (1 imp, pos 23): `/funny-polymarket-bets/` vs `/weird-prediction-markets/`. Cooled to near-zero; low priority.

To analyze this properly next week, restore the pipeline pull so page-detail files exist.

---

## Franchise content gaps

1. **Weirdest currently-active Polymarket markets, monthly cadence (HIGH).** Recurring ~147 imp/wk on "polymarket popular/active markets [month] 2026" is landing 0% on the politicians page. The June page exists but isn't displacing it. Two moves: (a) internal-link + title-align the June page now; (b) ship the **July** edition before the June page goes stale (it's 06-23). Brief covers both. **US share: Medium-High** (site US share 54%; per-query geo unavailable).
2. **Named single-market demand (MEDIUM).** "obama federally charged before 2027? prediction market" (pos 8.7) already has a Hall of Filth page shipped — good. Keep mining the query log for named-market queries at pos <15 as Hall of Filth fodder.

No commodity clusters listed as gaps, per strategy.

---

## Geographic + device notes

- **US-majority, healthy:** US 279/516 imp (54%), 9/13 clicks (69%). India 70 imp / 1 click (the weather page). UK 14 imp / 1 click at pos 8.1. The franchise kalshi cluster is inherently US (Kalshi is US-only). **Confidence: High.**
- **Mobile converts, desktop doesn't:** Mobile 13 clk / 223 imp / 5.83%; Desktop **0 clk** / 284 imp / 0%. Desktop impressions are almost entirely the zero-click politicians (198) + weather (94) pages. **Confidence: High.**

---

## Day-by-day (7-day chart)

| Date | Clicks | Imp | CTR | Pos |
|---|---|---|---|---|
| 2026-06-15 | 4 | 130 | 3.08% | 15.2 |
| 2026-06-16 | 3 | 100 | 3.00% | 14.7 |
| 2026-06-17 | 1 | 72 | 1.39% | 17.2 |
| 2026-06-18 | 0 | 62 | 0.00% | 18.4 |
| 2026-06-19 | 1 | 80 | 1.25% | 15.9 |
| 2026-06-20 | 2 | 48 | 4.17% | 8.8 |
| 2026-06-21 | 2 | 24 | 8.33% | 8.0 |

Clicks front-load on 6/15–6/16 (the franchise pages catching the week's volume); the 6/20–6/21 position/CTR jump is the prune clearing the average. No single-day spike carries the week. **Confidence: High.**

---

## Pipeline status (for James)

- **gsc-pull did NOT run / deliver this morning** — `weekly/2026-06-22/` is absent; this report used your manual export. Check `~/Library/Logs/dollarbets-gsc-pull.log`. If the Mac was asleep at 7:45 or auth failed, run `python3 scripts/gsc_pull.py` from `site/` to restore the pipeline (and the page-detail files this report was missing).
- See the **Deploy check** at the bottom of the content brief — there is a real flag there (uncommitted `content/pages/` edits since 06-17 that aren't live).
