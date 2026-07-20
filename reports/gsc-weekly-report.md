# GSC Report — 2026-07-20

**Window:** 2026-07-12 → 2026-07-18 (GSC "Last 7 days", ends 2 days ago per API lag). Full pull delivered — all 7 weekly CSVs + 28-day CSVs + 8 page-detail files present (page-detail is intentionally a top-pages-by-**28-day**-impressions pull per `gsc_pull.py`'s design, not a weekly pull — read those intersections as 28-day signal, not this-week signal). **Confidence: High** on data completeness.

## Headline — franchise keeps compounding; concentration deepened further

**Total clicks 34 → 62 (+82%), impressions 428 → 571 (+33%), CTR 7.9% → 10.9%, weighted avg position 8.47 → 7.05.** Every top-line number improved. Verified via three independent reconciliations: Chart.csv (62 clk / 571 imp), Devices.csv (62 / 571), Countries.csv (62 clk summed) — all agree exactly. **Confidence: High.**

Almost all of the gain is one page: `/crazy-kalshi-bets/` went **32 → 60 clicks, 334 → 473 impressions, CTR 9.6% → 12.7%, position 7.4 → 5.8** — up on every axis again, for the second week running. It now carries **97% of total site clicks** (60 of 62), up from 94% last report. The franchise thesis keeps validating itself; the resilience risk from concentration keeps growing with it. **Confidence: High.**

---

## Franchise scorecard

| Page | This week (7d) | Last report (7/05–7/11) | Read |
|---|---|---|---|
| `/crazy-kalshi-bets/` | **60 clk / 473 imp / 12.7% / pos 5.8** | 32 / 334 / 9.6% / 7.4 | **Up again, on every axis.** Clicks +88%, CTR +3.1pp, position +1.6. Second consecutive week of clean compounding. |
| `/funny-polymarket-bets/` | **1 clk / 75 imp / 1.3% / pos 13.5** | 1 / 53 / 1.9% / 12.6 | **Refresh (7/14: new hero market + live `/go/` link) has not moved the needle yet.** Position actually drifted slightly worse (12.6→13.5), impressions up (+42%) but CTR down. Still page-2. One week may be too early to judge a ranking response — but this is the second flat/negative week for this page. **Flag for continued attention, not alarm yet.** |
| `/polymarket-vs-kalshi-craziest-markets/` | 0 clk / 4 imp / pos 9.2 (28d: 1/13/8.8) | 0 / 4 / 11.8 | Refreshed 7/17 (differentiation angle). Page-detail file now exists but is **still empty** — no single query clears the reporting threshold. Too early post-refresh to judge; watch next week. |
| `/weird-prediction-markets/` | 0 clk / 3 imp / pos 11.3 (28d: 0/10/10.7) | absent weekly / 0/3/9.0 | Trivial volume, benign. |
| `/weirdest-active-polymarket-markets-july-2026/` | absent (<2 imp) | absent | Still not earning impressions 5 days post-launch-adjacent. Superseded by August edition (shipped 7/15) — see content gaps. |
| `/weirdest-active-polymarket-markets-august-2026/` | absent (<2 imp) | n/a (new, shipped 7/15) | Live, 200, no GSC signal yet — 5 days old, expected at this stage. |
| `/hall-of-filth/monet-auction-record-bet/` | absent (<2 imp) | n/a (new, shipped 7/16) | Live, 200, no GSC signal yet — 4 days old, expected. |
| `/hall-of-filth/george-whitesides-ca-27-primary-bet/` | absent weekly (28d: 0/2/6.5) | 0/2/6.5 | Holding page-1 on trivial volume, unchanged. |
| `/politicians-with-prediction-markets-june-2026/` | 0 clk / 2 imp / pos 3.0 | 0/0 (out of window) | Continuing to fade (28d: 20 imp/pos 8.2, was 270 imp two reports ago). **Still not retired** — see below. |

**Concentration: 97% of clicks on one page**, up from 94%. The de-concentration plays from last week's brief (Hall of Filth #2, funny-polymarket refresh) are either too new to show (Monet page) or not yet working (funny-polymarket). **Confidence: High** on the numbers; **Medium** on whether de-concentration is actually progressing.

---

## Last week's success criteria — scored

| Criterion | Result |
|---|---|
| Franchise clicks ≥ 34 (hold) | **PASS** — 61 franchise clicks (60 + 1) |
| `/crazy-kalshi-bets/` holds ≥ 25 clicks | **PASS** — 60 |
| `/funny-polymarket-bets/` position recovers to < 10 | **FAIL** — pos 13.5, essentially unchanged/slightly worse |
| "Polymarket popular active markets" family shows ≥1 impression on July/August page | **NOT CONFIRMED** — neither page has enough volume to appear in page-detail; the politicians-june page still owns the family (9 imp/pos 12.6 on "…active markets june 2026" in the 28-day intersection, down from 94 two reports ago but not reassigned) |
| A second franchise page earns ≥1 click | **PASS (marginal)** — funny-polymarket's usual 1 click |
| August page indexed within the week | **UNCONFIRMED** — 200 live, no GSC impressions yet (5 days old, not necessarily a problem) |

3 of 6 clear pass, 1 fail, 2 too-early-to-call. **Confidence: High** on the pass/fail calls; the "not confirmed" items need another week.

---

## Prune / noindexed-page fade check — still working as intended (High confidence)

`/can-you-bet-on-the-weather/` (noindexed): page-detail file is now **completely empty** (zero queries clear the threshold) — full fade confirmed. `/politicians-with-prediction-markets-june-2026/` continues its multi-week decline (270 → 20 → fading further this week) but **has still not been formally retired** — no `noindex` set, and no `vercel.json` redirect exists for it (checked directly). This is the same outstanding item flagged last report, now two weeks unexecuted. Note: the `/craziest-kalshi-markets/` → `/crazy-kalshi-bets/` 301 flagged as unshipped *last* report **has since landed** — verified live, returns a real 308 to `/crazy-kalshi-bets/`. Good — that carried item is closed.

---

## Quick wins — reviewed, 0 copy-edit wins qualified; 2 stale-link wins executed instead

Reviewed this week's franchise quick-win candidates (pos 4–15, ≥2 imp, 0 clicks): *funny kalshi bets* (pos 10.4/imp 8), *kalshi craziest bets* (5.9/10), *kalshi weird bets* (6.6/8), *most ridiculous kalshi bets* (5.0/2), *polymarket crazy bets* (10.5/2), *polymarket funny bets* (9.0/3), *craziest polymarket bets 2026* (10.0/2). Checked both pages' H2s/meta/body against these phrases directly — **all synonyms (crazy/craziest/weird/weirdest/ridiculous/funny) are already present**, and "2026" already appears 5× on the Polymarket page. At 2–10 impressions and page-1/2 position, expected incremental clicks from more keyword density are near zero; stuffing risk exceeds any plausible reward. **Not executed, deliberately — same call as last week.**

Instead found a genuine, lower-risk win while checking internal links: both `/crazy-kalshi-bets/` and `/funny-polymarket-bets/` still linked to the **June** "weirdest active Polymarket markets" edition, even though the **August** edition shipped 7/15 and July already links forward to August. Stale-month internal links on the two highest-traffic franchise pages were quietly pointing PageRank at a month-old page instead of the current one.

### Executed this run (2 of the allowed 3)

- **`/crazy-kalshi-bets/`** — updated internal link text/URL from "weirdest popular active polymarket markets june 2026" → "…august 2026" (`/weirdest-active-polymarket-markets-august-2026/`), bumped `last_updated` to 2026-07-20.
- **`/funny-polymarket-bets/`** — same fix: internal link updated from the July edition to the August edition, `last_updated` bumped to 2026-07-20.
- Rebuilt with `python3 generate_content.py` — exit 0, no errors. Confirmed both pages still render without a `noindex` meta tag, and both now link to the August page. **Confidence: High** this is a correct, low-risk fix (both are pure link-freshness edits, no substance/slug change); **Low-Medium** on measurable SEO impact (internal link authority signals are slow-moving).

---

## Cannibalization watch (28-day page-detail intersections, High confidence)

Same clean separation as last report: `/crazy-kalshi-bets/` owns the entire "kalshi" query family (22 queries, zero overlap with the polymarket file); `/funny-polymarket-bets/` owns the entire "polymarket" family (15 queries). **Zero franchise-vs-franchise overlap.**

The standing intent-mismatch issue persists: `/politicians-with-prediction-markets-june-2026/` still holds "polymarket popular active markets june 2026" (9 imp/pos 12.6, down from 94) and "polymarket popular markets june 2026" (2 imp/pos 11.0, down from 105) in the 28-day window — a fading grip, but a grip nonetheless. Neither the July nor August "weirdest-active" page has enough volume to appear in page-detail, so there's no evidence yet that the family is reassigning to the intended page. **Confidence: High** the politicians page still holds it; **Medium** on whether natural fade alone (without the retirement) will ever finish the handoff.

---

## Franchise content gaps (next brief will cover in detail)

1. **Politicians-june retirement — now 2 weeks carried, unexecuted.** Needs `noindex` + `noindex_reason` on the JSON (CI can do this) paired with a `permanent: true` redirect in `vercel.json` (outside CI scope — needs a manual commit from James). Splitting these across two different git-write paths is why it keeps slipping; flagging explicitly again.
2. **`/funny-polymarket-bets/` still not recovering** after its 7/14 refresh — two flat/negative weeks now. The lever may need to be internal authority (a homepage/board link) rather than another content pass, since metadata and hero market are both already current.
3. **De-concentration is directionally the right call but unproven** — Monet Hall of Filth page too new to read; funny-polymarket refresh hasn't worked yet. Keep the cadence rather than declaring success.

No commodity gaps flagged, per strategy — that's out of scope for this list by design.

**Note for James (not a franchise item, flagging for awareness only):** `/is-gambling-an-investment/` published 2026-07-17 via a separate process ("postwerks m2" commit, not part of the daily-article/GSC-brief pipeline). It's a generic "is X an investment" definitional/philosophical page — doesn't match any `BLOCKED_SLUG_PATTERNS` regex today so it isn't auto-noindexed, but it reads like exactly the commodity-content shape the 2026-06-05 audit found unproductive. Not touching it (outside this run's scope, and it's too new for any GSC signal either way) — just surfacing it in case it wasn't an intentional strategy exception.

---

## Geographic + device notes

- **US skew holding strong:** US 436/571 imp (76%), 48/62 clicks (77%) — consistent with last report's 74%. No franchise cluster >50% non-US. **Confidence: High.**
- **Mobile still dominant:** Mobile 50 clk/422 imp/11.8%/pos 6.3; Desktop 12 clk/148 imp/8.1%/pos 9.3. Desktop CTR improved from prior near-zero readings. **Confidence: High.**

---

## Day-by-day (7-day chart)

| Date | Clicks | Imp | CTR | Pos |
|---|---|---|---|---|
| 2026-07-12 | 3 | 40 | 7.5% | 11.2 |
| 2026-07-13 | 7 | 54 | 13.0% | 7.9 |
| 2026-07-14 | 7 | 77 | 9.1% | 6.4 |
| 2026-07-15 | 14 | 92 | 15.2% | 6.8 |
| 2026-07-16 | 9 | 124 | 7.3% | 7.1 |
| 2026-07-17 | 11 | 102 | 10.8% | 6.4 |
| 2026-07-18 | 11 | 82 | 13.4% | 6.1 |

Position trended from page-2 (11.2 on 7/12) down to consistently page-1 (6.1–7.1) by week's end — the clearest week-over-week improvement in the dataset so far. 7/15 was the peak day (14 clicks/15.2% CTR). **Confidence: High.**

---

## Data completeness / pipeline status

All 7 weekly CSVs, all 28-day CSVs, and all 8 page-detail files present and populated. No pull failures. Deploy check: all 10 checked franchise/carried URLs return 200 live (see brief for full list), and the `/craziest-kalshi-markets/` 301 is confirmed live (308 → `/crazy-kalshi-bets/`). **Confidence: High.**
