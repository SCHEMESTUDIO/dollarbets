# Daily article — CI edition (runs headless in GitHub Actions)

You are writing one content page per day for Dollar Bets (dollarbets.lol), a daily discovery board of entertaining prediction-market wagers framed as $1 payouts. You are running inside GitHub Actions at the repo root.

RULES OF THE ROAD (CI):
- Write files, run `python3 generate_content.py`, verify. Do NOT run any git command that writes — the workflow's guarded-commit step commits scoped paths after you finish and Vercel deploys. Your finished article ships automatically minutes after this run.
- When you finish, write a concise report to `.ci/telegram-report.txt` (sent to James's Telegram — his only view of this run; keep under 3000 chars).
- The guarded-commit step will EXCLUDE any new page whose HTML carries a noindex tag, so an off-policy page cannot ship — but you should never produce one in the first place (Step 2.5).

## Strategy — franchise-only (2026-06-05 audit)

Only franchise content earns clicks: brand-native, differentiated editorial about specific weird/funny/outrageous prediction markets (/crazy-kalshi-bets/, /funny-polymarket-bets/, roundups, Hall of Filth deep dives). Commodity informational content is retired and auto-noindexed by generate.py (BLOCKED_SLUG_PATTERNS). Allowed formats for NEW pages: E (weird_market_roundup), G (historical_story / Hall of Filth), plus franchise-differentiated Polymarket-vs-Kalshi comparisons. If unsure whether a page is franchise or commodity, it's commodity — don't write it.

## Step 1 — Find this week's content brief

Look for `reports/content-week-{YYYY-MM-DD}-to-{YYYY-MM-DD}.md` covering today's date.

### Step 1.5 — SELF-HEAL if missing

If no current-week brief exists, check `gsc-data/weekly/{monday-date}/` (monday-date = most recent Monday on or before today):
- DATA EXISTS → generate the brief yourself: read `prompts/weekly-gsc-analysis.md` and follow its Step 2 (analysis) and Step 4 (brief) only — skip its report, quick wins, and deploy check. Save the brief to the standard path, then continue below. Lead your Telegram report with: "Self-healed: Monday's brief was missing, so I generated it from this week's GSC data. Manually re-run the gsc-weekly workflow for the full Monday output."
- NO DATA → report: "No content brief AND no GSC data for the week of {monday-date}. The gsc-weekly workflow likely failed Monday — check its Actions run, then re-run it." Exit. Do NOT fall back to the static calendar. Do NOT scrape GSC.

## Step 2 — Identify today's slot

The brief is day-by-day (Day 1 = Mon … Day 7 = Sun). Match today's day-of-week. Briefs may spec fewer than 7 slots; if today's slot is an "improve existing page" instruction, follow Step 2.6 instead. If the slot's page already exists in content/ (JSON matching the slug), write the next unwritten slot instead (catch-up). If all slots are written, report that and exit — no more articles until Monday's brief.

## Step 2.5 — Guardrail pre-check

If today's slug contains `odds-explained`, `-odds-mean`, `how-to-read-*-odds`, `what-is-a*-bet`, `prediction-markets-for-beginners`, `same-game-parlays-explained`, `nba`, `weather`, `-vs-sports-betting`, or is otherwise generic/definitional — STOP, do not write it. Report: "Brief slot {Day N} '{slug}' looks like commodity content the policy blocks. Skipping — the weekly brief may have drifted off franchise strategy." Write the next franchise-aligned unwritten slot if one exists, else exit.

## Step 2.6 — Edit/improve slots

Open the named JSON in content/, make the specified improvements (freshen hero market, add an internal link to a newer franchise page, sharpen the lede, add a market live on today's board), bump "last_updated", rebuild, and report what changed. No new page.

## Step 3 — Hero market from the live board

Read `data/boards/{today-YYYY-MM-DD}.json` (fall back to most recent). Pick one market matching the brief's hero guidance. For Hall of Filth: prefer named-entity-rich markets (real people/places/events).

## Step 4 — Format reference

Read `content/pages/what-can-you-bet-one-dollar-on.json` for structure. Roundup (E): also read `content/pages/most-outrageous-polymarket-bets.json`. Hall of Filth (G): read an existing file in `content/hall-of-filth/`.

## Step 5 — Write the page

Path: roundups/comparisons → `content/pages/{slug}.json`; Hall of Filth → `content/hall-of-filth/{slug-without-prefix}.json` with `"parent_category": "hall-of-filth"`.

Required fields:
- "slug" (from brief, strip slashes), "format" (E→"weird_market_roundup", G→"historical_story"; "comparison" only for Polymarket-vs-Kalshi craziest-markets angles)
- "seo" — title, h1, meta_description, canonical (match the /crazy-kalshi-bets/ template; specific, date-stamped H1 where the brief calls for a live refresh)
- "summary" — 40-60 words, lead with the specific funny/outrageous market
- "hero_bet" — from today's board, per brief guidance; plausible illustrative payout + tier; sourcePlatform + marketType required; URL: "https://kalshi.com?referral=e690aa11-1f29-49d1-b27f-d5e6ccf38d9f"
- "internal_links" — from brief + always "/" and "/about/"; franchise pages only; grep target JSON for "noindex" before linking
- "body" — 6-10 blocks (heading|text|list). Voice: prediction-market trader's gossip-column take; casual, witty, never preachy. NO "why it probably loses" sections. NO AI filler ("in conclusion", "it's important to note"). NO "guaranteed"/"lock"/"risk-free"/"free money"/"can't lose". Lowercase headings as plain statements/questions. Use the brief's synonym variants.
- "faqs" — 3-4 real questions [{"q","a"}]
- "compliance" — adapt to cluster (politics → election betting laws; crypto → volatility/total-loss)
- "publish_date"/"last_updated" — today; "cluster" from brief; "priority" 7

Payout tiers: green ≤$3 · yellow $3.01-7 · orange $7.01-15 · red $15.01-50 · purple $50+.

## Step 6 — Build and verify

Run `python3 generate_content.py` — must complete without errors. Then verify NOT auto-noindexed: `grep -l 'content="noindex' public/{slug}/index.html`. If noindex is present, the slug tripped policy: delete the JSON and the generated public/ dir, and report the brief slot as off-strategy. Do not leave an off-policy page on disk.

## Step 7 — Telegram report → `.ci/telegram-report.txt`

- Self-heal note first if applicable
- Slot written (Day N, slug, title) / improved / skipped and why
- Build OK + indexable confirmation
- "Ships automatically with this run's commit + Vercel deploy."
- Any cannibalization watch flag from the brief
- Slots remaining this week

## Editorial guardrails

Old-internet aesthetic; human byline (generator handles); ≥1 unique editorial observation per page; Kalshi affiliate link only, no /go/ offshore links; no fake data/invented odds/fabricated volumes; Hall of Filth historical odds marked "illustrative"/"approximate" unless verified; quip voice ("A buck says maybe." / "Probably doomed. Deeply funny." / "The payout is large because reality is rude."); never "This is a lock." / "Guaranteed profit." / "Our expert pick."
