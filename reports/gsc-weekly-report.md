# GSC Report — 2026-08-03

**Window:** 2026-07-26 → 2026-08-01 (GSC "Last 7 days", ends 2 days ago per API lag). Full pull delivered — all 7 weekly CSVs + 28-day CSVs + 8 page-detail files present. **Confidence: High** on data completeness.

## Headline — franchise held its floor, but an external pipeline just planted a page in the franchise's own keyword territory

**Total clicks 53 → 57 (+7.5%), impressions 517 → 453 (-12.4%), CTR 10.25% → 12.58%, weighted avg position 6.0 → 6.49 (slightly worse).** Verified via three independent reconciliations: Chart.csv (57 clk / 453 imp), Devices.csv (57 / 453), Countries.csv (57 clk / 453 imp summed) — all agree exactly. **Confidence: High** on the numbers. Fewer impressions but more clicks at a higher CTR reads as the same demand-fluctuation pattern flagged the last two reports, not a ranking story — position moved less than half a point.

**The bigger story this run: last week's "URGENT — daily-article.yml silence" flag is resolved, and the resolution brought a new risk with it.** `daily-article.yml` wasn't broken — it was deliberately retired 2026-07-28 (commit `653a82b`, recorded in `docs/memory/decisions.md` and this week's `CLAUDE.md`), with net-new article writing handed to an external pipeline ("Postwerks"). That pipeline has been landing commits: 7 new `content/pages/*.json` files since 7/28 (`manifold-markets-craziest-bets`, `is-gambling-an-investment`, `weird-kalshi-bets`, `offensive-rookie-of-the-year-odds`, `nyc-mayor-odds`, `polymarket-senate-control-2026`, `who-will-win-the-senate-in-2026-polymarket`). Of those seven: **two are franchise-formatted** (`weird_market_roundup`) and **five are `format: explainer`** in clusters Market Structure / Sports / Politics — squarely the commodity category the 2026-06-05 audit says ranks page 8 and drags down site-wide quality. None match `BLOCKED_SLUG_PATTERNS` (no exact "odds-explained", "nba", "weather", "what-is-a-*-bet" hit), so none are auto-noindexed — they're live, 200, and in the sitemap by default. **Confidence: High** (verified by reading each JSON directly, not inferring from slugs).

**Sharper problem: `/weird-kalshi-bets/` (published 2026-08-01, Postwerks) directly restates `/crazy-kalshi-bets/`'s title and keyword territory.** `/crazy-kalshi-bets/` already owns the entire "weird kalshi bets" query family — this week's data: *weird kalshi bets* (2 clk/9 imp/pos 6.1), *kalshi weird bets* (0/4/5.0), *weird bets on kalshi* (0/2/6.0) — all currently resolving to `/crazy-kalshi-bets/` per its own page-detail Queries.csv. `/weird-kalshi-bets/`'s H1 is literally "Weird Kalshi Bets: The Actual Weirdest Markets Live." Two indexable pages on the same site now target the same query family. **Confidence: High** that the content overlap exists (read directly); **Medium** on whether it has yet caused actual SERP cannibalization — `/weird-kalshi-bets/` is 2 days old with zero GSC signal so far (not in 28-day Pages.csv), so there's no query-level GSC evidence yet, only the structural setup for it. Flagged now, before it accrues history, not after.

This is a strategy-scope question outside what a content-brief session can resolve unilaterally (noindexing a page from an external pipeline is a bigger call than a franchise metadata tweak), so it's flagged here and in the brief rather than executed.

---

## Franchise scorecard

| Page | This week (7/26–8/1) | Last week (7/19–7/25) | Read |
|---|---|---|---|
| `/crazy-kalshi-bets/` | **56 clk / 371 imp / 15.1% / pos 5.4** | 50 / 422 / 11.8% / 5.4 | Clicks +12%, impressions -12%, CTR +3.3pp, position exactly flat. Reads as the same page converting a smaller, more qualified impression pool better — consistent with demand fluctuation, not a ranking change. **Confidence: Medium** on the demand-side read (same caveat as prior reports). |
| `/funny-polymarket-bets/` | **1 clk / 45 imp / 2.2% / pos 11.2** | 1 / 52 / 1.9% / 9.0 | Position slid back 9.0 → 11.2 — **this fails last week's explicit success criterion** ("holds ≤10" was set precisely to test whether 9.0 was noise or a floor; it wasn't a floor). Click volume unchanged (1), sample still trivially small (45 imp). **Confidence: Medium** this is noise given the volume, but it's the second position swing in three reports with no on-page change to explain either direction — the "structural nav-link" hypothesis remains untested either way. |
| `/weird-kalshi-bets/` (NEW, Postwerks, not franchise-designated) | absent from weekly/28-day Pages.csv (2 days old) | n/a | See headline — cannibalization risk flagged before any GSC signal exists. |
| `/polymarket-vs-kalshi-craziest-markets/` | 0 clk/7 imp/pos 11.4 (weekly); 28d: 0/20/9.4 | absent weekly (28d: 1/16/8.2) | 28-day impressions up (16→20), position holding ~9-11. Still too early/small to call a trend. |
| `/weird-prediction-markets/` | absent weekly; 28d: 0/4/15.0 | 0/1/26.0 weekly | Trivial volume, position improved in the 28-day view but this is noise at n=4. |
| `/hall-of-filth/george-whitesides-ca-27-primary-bet/` | absent weekly; 28d: 0/3/7.0 | absent weekly (28d: 0/3/7.0) | Unchanged, holding trivial page-1 volume. |
| `/hall-of-filth/monet-auction-record-bet/` | absent weekly and 28-day | absent (28-day too) | **18 days old (published 7/16), still zero GSC signal in either window.** This has now crossed from "too new to judge" into "worth a second look before shipping a 4th Hall of Filth page into the same silent-signal pattern" — carried from last week's note, now with more days behind it. |
| `/politicians-with-prediction-markets-june-2026/` | absent from weekly Pages.csv entirely (below the 2-imp threshold); 28d: 0/4/pos 3.0 | 0/2/3.0 weekly (28d: 0/9/5.8) | Continuing its fade: 28-day impressions 270 → 20 → 9 → 4 over four reports. Still not retired — **now the 4th consecutive report carrying this**, see below. |

**Concentration: 98% of franchise clicks on `/crazy-kalshi-bets/`** (56 of 57 total site clicks) — up slightly from last week's ~94-97%, driven by `/funny-polymarket-bets/`'s flat click count against a larger `/crazy-kalshi-bets/` number, not by `/funny-polymarket-bets/` losing clicks outright. **Confidence: High** on the arithmetic; the "is concentration a problem" framing is unchanged from prior reports.

---

## Last week's success criteria — scored (from `reports/content-week-2026-07-27-to-2026-08-02.md`)

| Criterion | Result |
|---|---|
| At least one `Article: auto` commit lands this week | **N/A — superseded, not a fail.** Zero `Article: auto` commits, but the pipeline was deliberately retired 2026-07-28 (see headline) and replaced by Postwerks, which *did* land 5 commits this week. The criterion's underlying goal (content pipeline producing output) was met via a different mechanism than the one the criterion named. |
| Politicians-june retirement fully executed (noindex + vercel.json redirect) | **FAIL — 4th consecutive week.** Checked directly: `content/pages/politicians-with-prediction-markets-june-2026.json` has no `noindex` key; `vercel.json` has no redirect entry for this slug (only the pre-existing `/craziest-kalshi-markets` → `/crazy-kalshi-bets/` pair, confirmed still live at 308). |
| Franchise clicks ≥ 51 (hold); `/crazy-kalshi-bets/` ≥ 45 | **PASS both** — 57 total franchise clicks, 56 on `/crazy-kalshi-bets/`. |
| `/funny-polymarket-bets/` position holds ≤ 10 | **FAIL** — 11.2, see scorecard. |
| Hall of Filth #3 (conditional on pipeline running) | **Gate not met** — no new Hall of Filth page shipped. Note the pipeline *did* run this week (Postwerks), just not on this format — see franchise content gaps. |

**2 of 5 clean pass, 1 N/A/superseded, 2 fail.** Better underlying trajectory than last week's 1/6 — the pipeline-availability crisis is resolved — but two of the three carried items (politicians-june, Hall of Filth cadence) are still unexecuted, and a new item (cannibalization risk) replaces the resolved one as the top flag.

---

## Prune / noindexed-page fade check — no new pruning this week; nothing to check (High confidence)

Zero pages were noindexed since 2026-07-20 (still 25 of the now-72 `content/pages/*.json` files noindexed, unchanged count from the 7-file Postwerks additions since none of the new 7 carry `noindex`). No new fade signal — quiet because no pruning activity happened, not because pruning is unmonitored.

---

## Quick wins — reviewed, 0 executed (4th consecutive report reaching this conclusion)

Re-checked franchise quick-win candidates from this week's Queries.csv (pos 4–15, ≥2 imp, 0 clicks, franchise-only): *craziest bets on kalshi* (4.1/10), *crazy bets on kalshi* (7.5/2), *crazy polymarket bets* (8.0/2), *funniest kalshi bets* (7.7/3), *funniest polymarket bets* (9.8/6), *funny polymarket bets* (9.8/4), *kalshi crazy bets* (7.8/4), *kalshi weird bets* (5.0/4), *kalshi weirdest bets* (3.0/2), *most ridiculous kalshi bets* (2.5/2), *ridiculous kalshi bets* (6.5/2), *strangest kalshi bets* (4.0/4), *weird bets on kalshi* (6.0/2), *wildest kalshi bets* (2.5/2).

Both franchise pages remain **unchanged since 7/20** (confirmed `last_updated` field on both). Re-verified body text directly: `/crazy-kalshi-bets/` still does not contain the literal strings "stupid" or "strangest" despite ranking well for "strangest kalshi bets" (pos 4.0) and near-adjacent terms off "weird/craziest/ridiculous" density alone. Every other candidate query's core terms are already dense on the page. **Not executed, same conclusion as the last three reports** — nothing left to add without keyword-stuffing for 2-4 impression queries.

### Executed this run: none

No franchise metadata/copy quick win qualified. No edit was made to `content/` by this run. (The one substantive finding this week — the `/weird-kalshi-bets/` overlap — is a policy/scope question, not a copy edit to an *existing* franchise page, so it's flagged rather than executed per the trivial-quick-win boundary.)

---

## Cannibalization watch

**New: `/crazy-kalshi-bets/` vs `/weird-kalshi-bets/` (Postwerks, published 8/1) — see headline.** Title, H1, and target-query overlap confirmed by direct read of both JSON files. No GSC query-level evidence yet (page is 2 days old, zero impressions so far) — this is a structural-risk flag, not yet a measured cannibalization. **Confidence: High** on overlap existing; **Medium** on eventual impact.

**Also noted in passing (commodity-vs-commodity, out of franchise scope but a real technical issue):** `/polymarket-senate-control-2026/` and `/who-will-win-the-senate-in-2026-polymarket/` were both published 2026-08-01, same cluster (Politics), and both target "who wins the senate 2026 polymarket"-shaped queries with near-identical H1s. Not a franchise concern per this pipeline's strategy scope, but worth someone deduping — two commodity pages competing with each other helps no one, including the site's aggregate quality signal.

**Existing franchise separation holds:** `/crazy-kalshi-bets/` and `/funny-polymarket-bets/` still show zero query overlap with each other (kalshi vs polymarket query families remain cleanly split) — the only new overlap is the one flagged above, and it's a franchise-page-vs-non-franchise-page collision, not franchise-vs-franchise.

`/politicians-with-prediction-markets-june-2026/` still holds trace "polymarket popular markets" family queries (28-day: down to 4 impressions total, continuing its 4-report fade) — unchanged assessment, still not reassigned to a weirdest-active edition page.

---

## Franchise content gaps (next brief covers in detail)

1. **NEW — `/weird-kalshi-bets/` overlaps `/crazy-kalshi-bets/`'s query territory.** Needs a scope decision: is Postwerks output subject to the same franchise-only editorial policy as the retired daily-article pipeline, or does it run on its own rules? Someone with authority over both pipelines needs to decide; a content-brief session can't unilaterally noindex or merge pages from an external source.
2. **NEW (lower priority) — 5 of 7 recent Postwerks pages are commodity `format: explainer` content** (Market Structure / Sports / Politics clusters) that the 2026-06-05 audit's strategy explicitly deprioritizes, and none trip `BLOCKED_SLUG_PATTERNS`. If this pipeline continues at this ratio, the site accrues exactly the kind of page-8 commodity-page dilution the June prune was designed to remove. Worth someone deciding whether `BLOCKED_SLUG_PATTERNS` should be extended to catch this pipeline's output too.
3. **Politicians-june retirement — now 4 weeks carried, unexecuted.**
4. **Structural nav/footer inbound-link fix — now 3 weeks carried, unexecuted** (`grep -n "crazy-kalshi-bets\|funny-polymarket-bets" generate.py` still returns zero matches; still a `generate.py` change out of this pipeline's scope).
5. **Hall of Filth page count stuck at one net-new page in 18 days** (Monet, 7/16, still zero signal). The de-concentration cadence from the audit remains stalled even though the broader content pipeline is unblocked (Postwerks is shipping — just not Hall of Filth format).

No commodity gaps flagged as *things to build* — items 1-2 above are risk/scope flags about commodity content that already shipped via a different channel, not a recommendation to build more of it.

---

## Geographic + device notes

- **US skew holding strong:** US 38/57 clicks (67%), 323/453 imp (71%) — slightly lower US clicks-share than the 74-81% range of recent reports, but UK (5 clk/20 imp) and Canada (4/27) both ticked up; no franchise cluster is >50% non-US. **Confidence: High.**
- **Mobile still dominant:** Mobile 47 clk/335 imp/14%/pos 5.8; Desktop 10 clk/115 imp/8.7%/pos 8.6 — mobile leads on both volume and CTR this week (last week desktop briefly edged CTR; that didn't hold, consistent with it being noise as flagged last time). **Confidence: Medium** (desktop sample still small).

---

## Day-by-day (7-day chart)

| Date | Clicks | Imp | CTR | Pos |
|---|---|---|---|---|
| 2026-07-26 | 3 | 52 | 5.8% | 6.9 |
| 2026-07-27 | 7 | 73 | 9.6% | 5.7 |
| 2026-07-28 | 11 | 61 | 18% | 6.5 |
| 2026-07-29 | 15 | 70 | 21.4% | 6.2 |
| 2026-07-30 | 4 | 66 | 6.1% | 5.9 |
| 2026-07-31 | 11 | 55 | 20% | 7.4 |
| 2026-08-01 | 6 | 76 | 7.9% | 7.1 |

7/29 was the strongest day on both clicks (15) and CTR (21.4%), on the same 66-76 impression range as the rest of the week — a conversion-quality day, not an impression spike. 7/26 was the softest day on every metric. No clear weekday pattern across 7 days. **Confidence: High** on the raw numbers, **Low** on any causal read of the 7/29 peak (no corresponding query/page spike identified in page-detail data).

---

## Data completeness / pipeline status

All 7 weekly CSVs, all 28-day CSVs, and all 8 page-detail files present and populated. No GSC pull failure. Content pipeline status: `daily-article.yml` retirement confirmed intentional (not a new finding — resolves last week's open flag); Postwerks pipeline confirmed active with 5 commits since last Monday. Deploy check: all checked franchise/carried/new URLs return 200 live, and the `/craziest-kalshi-markets/` → `/crazy-kalshi-bets/` redirect still resolves 308 as expected. **Confidence: High.**
