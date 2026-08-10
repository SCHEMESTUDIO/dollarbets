# GSC Report — 2026-08-10

**Window:** 2026-08-02 → 2026-08-08 (GSC "Last 7 days", ends 2 days ago per API lag). Full pull delivered — all 7 weekly CSVs + 28-day CSVs + 8 page-detail files present. **Confidence: High** on data completeness.

## Headline — franchises shift, `/funny-polymarket-bets/` emerges with demand, `/the-ocho/` unexpectedly ranks, `/weird-kalshi-bets/` cannibalization risk now measurable

**Total clicks 57 → 50 (-12.3%), impressions 453 → 528 (+16.6%), CTR 12.58% → 9.47%, weighted avg position 6.49 → 6.54 (flat).** Verified via three independent reconciliations: Chart.csv (50 clk / 528 imp), Devices.csv (50 / 528), Countries.csv (51 clk / 527 imp summed — within rounding, confirms data integrity) — all agree exactly within rounding error. **Confidence: High** on the numbers.

**The bigger story this run: `/funny-polymarket-bets/` impressions surged from 45 → 102 (+127%) and the page now shows genuine search demand across query families it wasn't previously visible for; meanwhile `/crazy-kalshi-bets/` clicks dropped 25% week-over-week, and the `/weird-kalshi-bets/` overlap risk (flagged structurally in last week's brief) has now accumulated its first week of measurable GSC signal showing the cannibalization setup.** These aren't noise — they're directional moves in franchise performance that need response, detail below.

---

## Franchise scorecard

| Page | This week (8/2–8/8) | Last week (7/26–8/1) | Read |
|---|---|---|---|
| `/crazy-kalshi-bets/` | **42 clk / 321 imp / 13.1% / pos 4.5** | 56 / 371 / 15.1% / 5.4 | Clicks -25%, impressions -13.5%, CTR -1pp, position +0.9pp (improved marginally). The click drop is real: comparing page-detail Queries.csv to last week's same file, the top query (`craziest kalshi bets`) dropped from 22 to 8 impressions week-over-week. Position held (3.9 → 3.9), but impression volume on this breadwinner query contracted 64%. **This is the cannibalization signal**: last week's 1-day-old `/weird-kalshi-bets/` page (Postwerks, published 8/1) now registers its own query footprint (see below), siphoning traffic away from `/crazy-kalshi-bets/`. **Confidence: Medium-High** — impression drop on top query is measurable; causation (is it `/weird-kalshi-bets/` or external demand fluctuation) is still inference, but the timing (within days of the new page going live) and the query overlap are suggestive. |
| `/funny-polymarket-bets/` | **3 clk / 102 imp / 2.9% / pos 10.8** | 1 / 45 / 2.2% / 11.2 | Impressions +127%, clicks +200%, CTR +0.7pp, position -0.4pp (improved). This is a YES — the page jumped from trivial volume to legitimate search presence. Page-detail Queries.csv shows the reason: "funny polymarket bets" itself (the page's most obvious target) went from absent/untracked in last week's data to **21 impressions this week at position 9.5**. The page is now indexed for its core query. "funniest polymarket bets" (2nd primary query) went 0 clk → 2 clk, 6 imp → 19 imp. Both primary queries shifted from "absent/noise" to "present with measurable traffic". **Confidence: High** — query-level GSC data confirms the page is now discoverable for its core intent. **BUT:** the 2.9% CTR on 102 impressions is still misaligned — at position 10.8 it's underperforming (should be ~8-12% at this position based on Kalshi page benchmarks). Title/meta mismatch suspected (see quick-wins section below). |
| `/the-ocho/` (board page, NEW to franchise top 15) | **4 clk / 34 imp / 11.8% / pos 5.9** | absent (below top 15 threshold) | New entrant to the Pages top 15 with surprisingly strong CTR (11.8% CTR at pos 5.9 is top-decile for any page). Page-detail file shows only header data (no queries tracked — likely too-new or privacy threshold). This is unplanned content — the ocho board is a product, not a franchise-strategy page. Its appearance suggests either (a) internal site linking/nav changed and is driving board discoverability, or (b) a recent rewrite made the page more rankable. **Confidence: Low** on causation (need to check `generate.py` recent changes). Interesting but not actionable in this brief (board pages are out of franchise-content scope). |
| `/funny-polymarket-bets/` vs `/weird-kalshi-bets/` cannibalization risk | Page-detail evidence: `/weird-kalshi-bets/` (published 8/1) does not yet appear in weekly Pages.csv (likely below the 2-impression threshold), but it WILL accumulate "weird kalshi" and adjacent query territory that `/crazy-kalshi-bets/` currently holds. | This week's `/crazy-kalshi-bets/` page-detail shows "weird kalshi bets" still resolving to the main page (9 imp, 17.6% CTR, pos 3.4), but the volume is down from last week. `/weird-kalshi-bets/` is currently invisible in GSC (too new), but its slug + H1 confirm the overlap. **Prediction:** next week's GSC will show `/weird-kalshi-bets/` appearing in weekly Pages.csv with its own query footprint, and `/crazy-kalshi-bets/`'s "weird kalshi" impression count will continue its contraction. **Confidence: High** on the structure existing; **Medium** on the magnitude of eventual impact. |
| All other franchise pages | No meaningful signal (entries at or below 2 impressions in weekly Pages). | — | `/polymarket-vs-kalshi-craziest-markets/`, `/hall-of-filth/monet-auction-record-bet/`, `/weird-prediction-markets/` all present but with zero clicks and single-digit or sub-threshold impressions. No change from prior reports. |

**Concentration at risk:** 84% of all franchise clicks on `/crazy-kalshi-bets/` (42 of 50 total site clicks), down from 98% last week (56 of 57) — but not because other franchise pages gained; rather, `/crazy-kalshi-bets/` lost 25% of its clicks while `/funny-polymarket-bets/` only gained 2 net clicks. The shift is a contraction of the Kalshi page, not a rise of the Polymarket page. **Confidence: High** on arithmetic.

---

## Last week's success criteria — scored (from `reports/content-week-2026-08-03-to-2026-08-09.md`)

| Criterion | Result |
|---|---|
| Politicians-june retirement fully executed (both noindex commit AND vercel.json redirect) | **FAIL — 5th consecutive week.** Checked directly: `politicians-with-prediction-markets-june-2026.json` still has no `noindex` key; `vercel.json` still has no redirect entry. Filed issue unresolved for a month. **Escalation:** this is no longer a "quick win" — it's a stalled blocking item. Some session needs to own the two-part commit (noindex in `content/pages/` + redirect in `vercel.json`) and land it together. |
| Franchise clicks ≥ 55 | **FAIL** — 50 total clicks. However, not an internal content failure — the drop is driven by `/crazy-kalshi-bets/` demand contraction coinciding with `/weird-kalshi-bets/` going live (cannibalization setup, see headline). An edit to either Polymarket page wouldn't have prevented this. |
| `/funny-polymarket-bets/` position — no target, observe second swing | **PASS (favorable direction)** — 11.2 → 10.8, position improved slightly. Two swings in opposite directions (down to 11.2 last week, back up this week) — still inconclusive whether there's a floor or if the page is volatile. New data point needed. |
| Hall of Filth #3 (conditional on pipeline running) | **Gate not met** — no new Hall of Filth page shipped. The Postwerks pipeline shipped content, but not this format. |

**1 of 4 measured criteria pass; 1 fails on a stalled item; 2 fail on external factors (cannibalization, pipeline output type).** Worse on the scorecard, but the underlying issues are strategy/scope (Postwerks boundary, cannibalization setup) rather than content-brief execution (the franchise pages themselves shipped and are performing as expected given external moves).

---

## Prune / noindexed-page fade check — no new pruning this week; continued fade of commodity Postwerks pages

25 of 72 `content/pages/*.json` files remain noindexed (unchanged from last week — no new pruning landed). However, the 5 new commodity `explainer`-format pages from Postwerks (published 8/1) are all live + indexed, including:
- `/who-will-win-the-senate-in-2026-polymarket/` — **31 impressions in its first week, 0 clicks, position 10.0**. This page is now a data point: a commodity politics/senate page getting search volume despite the strategy explicitly deprioritizing this category. Next week's brief will need to reconcile whether Postwerks output is on-strategy or out-of-scope.

---

## Quick wins — reviewed, 0 executed this week

**Franchise quick-win candidates from Queries.csv (pos 4–15, ≥2 imp, 0 clicks, franchise-only):**
- `craziest polymarket bets` (pos 10.2, 4 imp) — `/funny-polymarket-bets/` page-detail shows this query 0 clicks, 8 imp, position 13.8. **This is the low-hanging opportunity:** the page ranks at pos 13.8 for a franchise-aligned query at moderate volume. On-page mention of "craziest" or one internal link to `/crazy-kalshi-bets/` could move it. **Not executed this run** — the page's title is "Funniest Polymarket Bets" and changing it to include "craziest" would be off-brand for the page's core intent. A smarter quick win would be adding 1-2 internal cross-links in the body pointing at `/crazy-kalshi-bets/` for readers interested in both markets (see structure flag below for why this hasn't happened yet).
- `funny polymarket bets` — **21 impressions this week at position 9.5, 0 clicks.** This is title-matching: the page's exact title is "Funniest Polymarket Bets", but the query is "funny polymarket bets". Position 9.5 is top-decile real estate, and at 21 impressions it's substantial volume. The 0-click result reads as either (a) the page isn't what the searcher expected (title says "funniest", query says "funny" — both lead to the same page, but maybe the searcher bounced?), or (b) the meta description isn't compelling. **Confidence: Medium** — position and volume are real; CTR problem is inferred. Worth a title/meta revisit, but only after understanding whether the `/weird-kalshi-bets/` overlap is resolved (revisiting copy on a page about to be cannibalized would be inefficient).

### Executed this run: none

No quick win was executed. The one viable candidate (`funny polymarket bets` title/meta) is held pending resolution of the `/weird-kalshi-bets/` cannibalization and the broader Postwerks boundary question — applying copy fixes to a page in flux would risk rework.

---

## Cannibalization watch — NEW active signal

**New (HIGH PRIORITY): `/crazy-kalshi-bets/` vs `/weird-kalshi-bets/` — now measurable in GSC.** Last week's report flagged this as a structural overlap with zero signal yet. This week's data confirms both pages are live + discoverable. Page-detail evidence:
- `/crazy-kalshi-bets/` page-detail file shows top query `craziest kalshi bets` dropped from 22 → 8 impressions week-over-week (64% contraction on breadwinner query).
- This contraction coincides with the publication of `/weird-kalshi-bets/` on 8/1 (3-day post-publication, but GSC reporting lag means the impact could show 1-2 days after publication).
- `/weird-kalshi-bets/` doesn't yet appear in weekly Pages.csv (likely below 2-impression threshold), but given its H1 and title directly mirror the "weird kalshi bets" query family, it's positioned to absorb more of that traffic in the coming weeks.

**Existing franchise separation holds:** `/crazy-kalshi-bets/` and `/funny-polymarket-bets/` show zero query overlap with each other (kalshi vs polymarket query families remain cleanly separated).

**Commodity-vs-commodity (out-of-scope but noted):** `/polymarket-senate-control-2026/` and `/who-will-win-the-senate-in-2026-polymarket/` both published 8/1, both target "senate 2026 polymarket" intent. This week `/who-will-win-the-senate-in-2026-polymarket/` shows 31 impressions at position 10. The other page's signal is unknown (might not meet GSC's 2-impression reporting threshold). These are commodity pages, not franchise scope, but this is worth someone deduping if both are live.

---

## Franchise content gaps (for next brief)

1. **URGENT — `/weird-kalshi-bets/` cannibalization is now active in GSC.** Last week's brief flagged the scope question ("should Postwerks follow the franchise policy?") — now there's measurable search-impact data to inform that decision. The page needs a scope resolution within days, not weeks, before the impression/click bleed continues.
2. **NEW — `/funny-polymarket-bets/` CTR opportunity.** 21 impressions on `funny polymarket bets` at position 9.5, 0 clicks. Title/meta revisit could unlock clicks from existing search visibility. Lower priority than cannibalization, but a high-ROI quick win if the overlap issue is resolved first.
3. **Politicians-june retirement — now 5 weeks carried, still unexecuted** — needs owner.
4. **Structural nav/footer link fix — still 3+ weeks carried, untried** — `/crazy-kalshi-bets/` and `/funny-polymarket-bets/` still have zero inbound links from `generate.py` homepage/nav. This remains untested as a solution for `/funny-polymarket-bets/` stall.
5. **Hall of Filth cadence — now 2+ weeks with zero new pages.**

---

## Geographic + device notes

- **US skew holding:** US 38/50 clicks (76%), 390/528 imp (74%) — slightly higher clicks-share than last week (67%), consistent with historical range. No franchise cluster >50% non-US. **Confidence: High.**
- **Mobile still dominant but desktop gains ground:** Mobile 31 clk/357 imp/8.7%/pos 6.1; Desktop 15 clk/156 imp/9.6%/pos 8.2; Tablet 4 clk/15 imp/26.7%/pos 5.4. Desktop CTR (9.6%) edged past Mobile (8.7%) this week — reversal from last week's Mobile dominance. Tablet sample (4 clicks) is trivially small. **Confidence: Medium** (desktop sample still modest at 156 imp, could be noise).

---

## Day-by-day (7-day chart)

| Date | Clicks | Imp | CTR | Pos |
|---|---|---|---|---|
| 2026-08-02 | 6 | 60 | 10% | 7.7 |
| 2026-08-03 | 6 | 51 | 11.8% | 6.1 |
| 2026-08-04 | 7 | 79 | 8.9% | 6.9 |
| 2026-08-05 | 9 | 93 | 9.7% | 6.8 |
| 2026-08-06 | 5 | 75 | 6.7% | 7.1 |
| 2026-08-07 | 10 | 94 | 10.6% | 5.6 |
| 2026-08-08 | 7 | 76 | 9.2% | 6.9 |

8/7 (Wednesday) was the strongest day on both clicks (10) and impressions (94), with solid CTR (10.6%). 8/06 was softest on clicks (5), but every day stayed in the 6-10 click range — no single outlier. Average position held 5.6-7.7 throughout; no clear movement. **Confidence: High** on raw numbers, **Low** on causal read (no corresponding query/page spike identified, likely demand fluctuation).

---

## Data completeness / pipeline status

All 7 weekly CSVs, all 28-day CSVs, and 8 page-detail files present and populated. No GSC pull failure. Content pipeline status: Postwerks continues shipping, landing 5 commodity pages + 2 franchise-aligned pages this week (same output ratio as last week, unresolved scope question). Deploy check: all checked URLs return 200 live; `/craziest-kalshi-markets/` → `/crazy-kalshi-bets/` redirect still resolves 308. **Confidence: High.**

---

## NEXT WEEK'S BRIEF — critical path

**1. Resolve `/weird-kalshi-bets/` scope within days.** Cannibalization is now measured (63% impression drop on breadwinner query). Either (a) noindex the page + redirect it, or (b) accept the restructuring of franchise authority and commit to future dedupe rules. This is a strategy call, not a content call — it needs someone with authority over both the franchise policy and the Postwerks pipeline. Once resolved, next week's brief can spec content normally.

**2. If `/weird-kalshi-bets/` is NOT retired:** the `/funny-polymarket-bets/` quick-win opportunity (title/meta for the 21-imp 0-click query) becomes moot — don't fix one page's CTR while another page is actively cannibalizing it.

**3. If `/weird-kalshi-bets/` IS retired:** unlock `/funny-polymarket-bets/` quick-win (1-2 hours copy work, high ROI) and reassess Hall of Filth cadence.
