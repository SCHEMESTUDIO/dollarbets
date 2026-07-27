# GSC Report — 2026-07-27

**Window:** 2026-07-19 → 2026-07-25 (GSC "Last 7 days", ends 2 days ago per API lag). Full pull delivered — all 7 weekly CSVs + 28-day CSVs + 8 page-detail files present. **Confidence: High** on data completeness.

## Headline — top line dipped, but positions improved; the bigger story is upstream: no content shipped this week

**Total clicks 62 → 53 (-15%), impressions 571 → 517 (-9%), CTR 10.9% → 10.25%, weighted avg position 7.05 → 6.0 (improved).** Verified via three independent reconciliations: Chart.csv (53 clk / 517 imp), Devices.csv (53 / 517), Countries.csv (53 clk summed) — all agree exactly. **Confidence: High** on the numbers.

The clicks/impressions dip is **not prune-driven** — no page was noindexed this week (checked `git log` on `content/` and `vercel.json`: zero commits touching either since the 2026-07-20 GSC run's quick-win edits). Read alongside position *improving* on both franchise pages (`/crazy-kalshi-bets/` 5.8→5.4, `/funny-polymarket-bets/` 13.5→9.0), the likely explanation is **demand-side query volume fluctuation, not a ranking regression** — rankings got better while the underlying search volume for these terms was simply lower this week. **Confidence: Medium** on that read; a second week of decline with static-or-worse positions would flip this to a real flag.

**The bigger finding: the `daily-article` pipeline appears to have gone silent.** `git log --grep="Article: auto"` shows the last automated article commit was `a5e5233 Article: auto 2026-07-17` — **10 days with zero output**, despite the workflow being correctly configured (`on: schedule: cron: '30 9 * * *'`, not disabled, `workflow_dispatch` present). This directly explains why none of last week's brief items shipped: no Hall of Filth #3, no structural nav-link fix, no politicians-june retirement. **This is flagged first in the Telegram report as the most urgent item — I cannot see GitHub Actions run logs from this session, so I can't tell whether it's failing every day or producing no diff; James needs to check the Actions tab.** **Confidence: High** that no commits landed; **Low** on root cause without run-log access.

---

## Franchise scorecard

| Page | This week (7/19–7/25) | Last week (7/12–7/18) | Read |
|---|---|---|---|
| `/crazy-kalshi-bets/` | **50 clk / 422 imp / 11.8% / pos 5.4** | 60 / 473 / 12.7% / 5.8 | Clicks -17%, impressions -11%, but **position improved** (5.8→5.4). Consistent with lower search demand that week rather than a ranking drop. Still carries ~94% of franchise clicks — concentration essentially unchanged. **Confidence: Medium** on the demand-side read. |
| `/funny-polymarket-bets/` | **1 clk / 52 imp / 1.9% / pos 9.0** | 1 / 75 / 1.3% / 13.5 | **First position improvement in 3 reports** (13.5 → 9.0), impressions down (-31%) but that's plausibly the same demand fluctuation as crazy-kalshi. Too early / too small a sample to call this "the stall broke" — no on-page or structural change happened this week to explain it (metadata unchanged since 7/20, structural nav-link fix still not shipped — see below). **Confidence: Low** that this is a real turn; **High** that nothing this pipeline did caused it. |
| `/polymarket-vs-kalshi-craziest-markets/` | absent from weekly Pages.csv (28d: 1 clk/16 imp/8.2) | 0 clk/4 imp/9.2 (28d: 1/13/8.8) | Trivial volume, slight 28-day uptick since the 7/17 refresh. Still too early/small to judge. |
| `/weird-prediction-markets/` | 0 clk/1 imp/pos 26.0 (weekly) | 0/3/11.3 | 1-impression noise, not meaningful at this volume. |
| `/weirdest-active-polymarket-markets-august-2026/` | absent (<2 imp) | absent (5 days old last week) | Still no GSC signal 12 days post-launch — worth another week before calling it stalled. |
| `/hall-of-filth/monet-auction-record-bet/` | absent (<2 imp, and now absent from 28-day Pages.csv too) | absent (4 days old) | 12 days old, zero signal in both weekly and 28-day pulls. Starting to look like more than "too new" — flag for next week if still silent. |
| `/hall-of-filth/george-whitesides-ca-27-primary-bet/` | absent weekly (28d: 0/3/7.0) | absent weekly (28d: 0/2/6.5) | Holding trivial page-1 volume, unchanged. |
| `/politicians-with-prediction-markets-june-2026/` | 0 clk/2 imp/pos 3.0 (weekly); 28d: 0/9/5.8 | 0/2/3.0 (28d: 0/20/8.2) | Continuing to fade (270 → 20 → 9 over three reports) but **still not retired** — third consecutive report carrying this. |

**Concentration: ~94% of franchise clicks on `/crazy-kalshi-bets/`** (50 of 53 total, or 50 of 51 counting only the two scorecard pages) — essentially flat vs last week's 97%, not a meaningful de-concentration move. **Confidence: High.**

---

## Last week's success criteria — scored (all from `reports/content-week-2026-07-20-to-2026-07-26.md`)

| Criterion | Result |
|---|---|
| Franchise clicks ≥ 60 (hold) | **FAIL** — 51 (50 + 1) |
| `/crazy-kalshi-bets/` holds ≥ 50 clicks | **PASS (exactly at threshold)** — 50 |
| Concentration stops increasing (non-crazy-kalshi franchise clicks ≥ 2, vs last week's 1) | **FAIL** — still 1 (funny-polymarket only; no Hall of Filth #3 shipped to help) |
| Politicians-june retirement fully executed (noindex + vercel.json redirect) | **FAIL** — neither half done; checked `content/pages/politicians-with-prediction-markets-june-2026.json` (no `noindex` field) and `vercel.json` (no redirect entry) directly |
| "Polymarket popular active markets" family shows signal on August page | **FAIL** — `weird-prediction-markets-Queries.csv` and `polymarket-vs-kalshi-craziest-markets-Queries.csv` page-detail files are both empty; politicians-june page still holds the family (9 imp/pos 5.8, 28-day) |
| New Hall of Filth page (#3) reaches 200/indexable by end of week | **FAIL (gate not met)** — page was never shipped; `content/hall-of-filth/` still ends at `monet-auction-record-bet.json` (7/16), no new file since |

**1 of 6 pass (marginal), 5 fail** — worse than last week's 3/6. All five failures trace back to the same root cause: **no content commits landed this week** (see headline). This is a pipeline-availability problem, not an editorial-judgment problem — the brief's calls were reasonable, they just didn't get executed. **Confidence: High.**

---

## Prune / noindexed-page fade check — no new pruning this week, nothing to check (High confidence)

Zero pages were noindexed since the 2026-07-20 run. `/can-you-bet-on-the-weather/`'s page-detail file remains empty (fade holding from prior weeks). No new fade signal to report — **this section is quiet because no pruning activity happened, not because pruning is un-monitored.**

---

## Quick wins — reviewed, 0 executed (same call as the last two reports)

Re-checked the same franchise quick-win candidates from 28-day page-detail (pos 4–15, ≥2 imp, 0 clicks): *funny kalshi bets* (10.0/11), *kalshi weird bets* (7.1/21), *kalshi weirdest bets* (5.6/7), *weirdest bets on kalshi today* (7.2/4), *craziest polymarket bets* (9.3/3), *craziest polymarket bets 2026* (10.3/3), *crazy polymarket bets* (11.0/3), *funny polymarket bets* (9.2/12), *polymarket crazy bets* (10.7/3), *polymarket funny* (10.8/4), *polymarket funny bets* (9.3/7), *stupid polymarket bets* (8.5/2).

Both pages are **unchanged since the 7/20 edit** (`last_updated: 2026-07-20` on both, confirmed via `content/pages/*.json`), so re-auditing word frequency directly: `/crazy-kalshi-bets/` already contains "funny"×2, "weird"×21, "weirdest"×14, "ridiculous"×3, "crazy"×11, "craziest"×19. `/funny-polymarket-bets/` already contains "funny"×18, "weird"×8, "crazy"×8, "craziest"×6, "ridiculous"×6, "absurd"×5. Every candidate query's core terms are already dense on the relevant page — the only two literally-absent single words across both audits are "stupid" and "strangest" (2-3 impression queries, not worth a bespoke pass). **Not executed, deliberately — same conclusion as 2026-07-13 and 2026-07-20: nothing left to add without stuffing.**

### Executed this run: none

No franchise metadata/copy quick win qualified. No other edit was made to `content/` by this run.

---

## Cannibalization watch (28-day page-detail intersections, High confidence)

Same clean separation as the last two reports: `/crazy-kalshi-bets/` owns the entire "kalshi" query family (25 queries), `/funny-polymarket-bets/` owns the entire "polymarket" family (17 queries). **Zero franchise-vs-franchise overlap.**

`/politicians-with-prediction-markets-june-2026/` still holds "polymarket popular active markets june 2026" (2 imp/pos 11.5, weekly) and "polymarket popular markets june 2026" (1 imp/pos 10.0) — continuing to fade (was 9/2.0 in 28-day last report) but still not reassigned to either weirdest-active edition. **Confidence: High** the politicians page still holds it; this is now a 3-week-carried item, see content gaps.

---

## Franchise content gaps (next brief covers in detail)

1. **`daily-article.yml` silence — new, most urgent item.** 10 days with no automated commit. Everything else on this list (Hall of Filth #3, the nav-link structural fix, the politicians-june retirement) depends on this pipeline running. Fixing the automation unblocks all three carried items at once.
2. **Politicians-june retirement — now 3 weeks carried, unexecuted.**
3. **Structural nav/footer inbound-link fix — now 2 weeks carried, unexecuted** (needs a `generate.py` change, out of this pipeline's scope; flagged again for a dev session).
4. **Hall of Filth page count stuck at one net-new page in 12 days** (Monet, 7/16) — the de-concentration cadence from the audit has stalled, likely for the same root-cause reason as #1.

No commodity gaps flagged, per strategy — out of scope for this list by design.

---

## Geographic + device notes

- **US skew holding strong:** US 43/53 clicks (81%), 381/517 imp (74%) — consistent with prior reports (74-77%). No franchise cluster >50% non-US. **Confidence: High.**
- **Mobile still dominant:** Mobile 40 clk/391 imp/10.2%/pos 5.8; Desktop 13 clk/122 imp/10.7%/pos 6.5 — desktop CTR now edges out mobile, a new pattern worth watching but not actionable on 13 clicks. **Confidence: Medium** (small sample).

---

## Day-by-day (7-day chart)

| Date | Clicks | Imp | CTR | Pos |
|---|---|---|---|---|
| 2026-07-19 | 12 | 169 | 7.1% | 6.0 |
| 2026-07-20 | 7 | 66 | 10.6% | 6.5 |
| 2026-07-21 | 3 | 54 | 5.6% | 6.1 |
| 2026-07-22 | 3 | 49 | 6.1% | 6.8 |
| 2026-07-23 | 9 | 58 | 15.5% | 5.7 |
| 2026-07-24 | 14 | 65 | 21.5% | 4.9 |
| 2026-07-25 | 5 | 56 | 8.9% | 6.2 |

7/19 was an impression spike (169, likely a one-off SERP feature or query surge) that didn't convert at the site's usual CTR (7.1% vs the week's 10.25% average). 7/24 was the strongest day on both CTR (21.5%) and position (4.9). No clear weekday pattern yet across only 7 days. **Confidence: High** on the raw numbers, **Low** on any causal read of the 7/19 spike (no corresponding query/page spike identified in the page-detail pulls).

---

## Data completeness / pipeline status

All 7 weekly CSVs, all 28-day CSVs, and all 8 page-detail files present and populated. No GSC pull failure. **Separately, the content pipeline (`daily-article.yml`) has produced zero commits in 10 days — see headline. This is the actionable item for this report, not the GSC pull itself, which is healthy.** Deploy check: all 8 checked franchise/carried URLs return 200 live (see brief for full list and the confirmed 308 on `/craziest-kalshi-markets/`). **Confidence: High.**
