# Weekly GSC analysis — CI edition (runs headless in GitHub Actions)

You are analyzing Google Search Console data for dollarbets.lol, a daily prediction market discovery board. You are running inside GitHub Actions at the repo root. The GSC CSVs were pulled by a previous step in this same workflow (scripts/gsc_pull.py).

RULES OF THE ROAD (CI):
- You may read anything, write files, and run `python3 generate_content.py`. Do NOT run any git command that writes (add/commit/push/rebase) — the workflow's guarded-commit step handles that after you finish.
- When you finish, write a concise report (the "Step 6" format below) to `.ci/telegram-report.txt`. That file is sent to James's Telegram. Notification diet (2026-07-25): the Telegram message is a SCORECARD, not an essay — hard cap 1200 chars. Everything deep lives in `reports/gsc-weekly-report.md`. Anything that needs James to ACT goes in the shared actions queue via `bash scripts/queue_action.sh "dollarbets:gsc:<stable-slug>" "<title>" "<what+why>"` (fail-open to a ping if queue secrets are absent) — it surfaces in his Saturday digest. Use the SAME slug when re-detecting a known issue so it dedupes instead of re-nagging week after week.
- Do NOT fabricate data. Label non-trivial claims High/Medium/Low confidence.

## Strategy context (2026-06-05 audit — anchor every judgment to it)

1. Only franchise content ranks: brand-native editorial about specific weird/funny/outrageous prediction markets (/crazy-kalshi-bets/ pos ~7 / 11%+ CTR, /funny-polymarket-bets/, market roundups, Hall of Filth single-market deep dives). Commodity informational content (odds explainers, "what is a X bet", NBA props, weather, generic "X vs sports betting") ranks page 8, earns zero clicks, harms the site.
2. 24 commodity pages were noindexed 2026-06-05; generate.py auto-noindexes new commodity slugs (BLOCKED_SLUG_PATTERNS). Expect those pages to fade from Pages.csv — that's the prune working, not a problem.
3. Post-prune, total impressions DROP and average position IMPROVE for compositional reasons. Neither is news. Do not alarm on the drop or celebrate the position move.
4. "Indexing is the bottleneck" was a misdiagnosis. Absent from Pages.csv = earned no impressions, not "not indexed". Light deploy check only.

THE METRIC: clicks + CTR on franchise pages, and whether new franchise pages earn qualified impressions.

{monday-date} = most recent Monday on or before today (compute: today minus today.weekday() days).

## Step 1 — Load this week's data

Locations (repo-relative, written by gsc_pull.py earlier in this workflow run):
- `gsc-data/weekly/{monday-date}/` — Queries.csv, Pages.csv, Countries.csv, Devices.csv, Search appearance.csv, Chart.csv, Filters.csv
- `gsc-data/28day/{monday-date}/` — same set
- `gsc-data/page-detail/{monday-date}/` — up to 8 {slug}-Queries.csv files

If the weekly/{monday-date} directory is MISSING or empty, the pull step failed silently. Write to `.ci/telegram-report.txt`: "GSC ANALYSIS SKIPPED — gsc_pull produced no data for {monday-date}. Check the workflow logs for the pull step (likely a creds/API problem with the GSC_CREDENTIALS_JSON secret)." Then STOP. Do not overwrite the report, do not generate a brief.

## Step 2 — Analyze (prune-aware)

Cross-verify totals across Chart.csv, Devices.csv, Countries.csv (should match; Pages/Queries differ slightly due to privacy thresholds). Then:
- FRANCHISE HEALTH (primary): clicks, CTR, position trend for crazy-kalshi-bets, funny-polymarket-bets, most-outrageous-polymarket-bets, weird-prediction-markets, the roundups, Hall of Filth.
- Expected fade: noindexed pages (any content/ JSON containing "noindex") losing impressions = EXPECTED, not a problem.
- Attribute impression/position movement correctly: prune-driven (healthy) vs genuine franchise regression (flag).
- Quick wins (franchise-only): queries at position 4–15, ≥2 impressions, 0 clicks, on a franchise page/topic. Commodity quick wins are not quick wins.
- Cannibalization: use page-detail Queries.csv files — flag queries appearing in ≥2 files with overlapping positions.
- Trend deltas vs previous `reports/gsc-weekly-report.md` if it exists.
- Geographic skew: franchise clusters >50 impressions with >50% non-US get deprioritized.

## Step 3 — Write the report

Save to `reports/gsc-weekly-report.md` (overwrite). Include: date range (from Filters.csv/Chart.csv), verified totals with prune-aware interpretation, FRANCHISE SCORECARD (lead section), trend table vs last week, quick wins (with executed-or-not status), noindexed-fade check, cannibalization watch (with evidence), franchise content gaps (never commodity), geo/device notes, day-by-day chart breakdown. Confidence labels on every non-trivial claim.

## Step 3.5 — EXECUTE trivial quick wins (cap: 3)

For each franchise quick win that is a pure metadata/copy edit to an EXISTING franchise page (title/h1/meta_description phrase, lede sharpening, one internal link):
1. Edit the page JSON in content/ directly (respect editorial guardrails; don't change substance or slug).
2. Bump "last_updated" to today.
3. Rebuild: `python3 generate_content.py`. Confirm no errors, page still indexable.
4. List each edit in the report under "Executed this run."
Franchise pages only, metadata/copy only. Structural TEMPLATE changes (generate.py nav/footer/layout) remain BANNED for this pipeline — generate.py is the backbone and stays human-reviewed. When the data says a template change is needed (e.g. zero sitewide internal links to franchise pages), queue it once: `bash scripts/queue_action.sh "dollarbets:gsc:<slug>" ...` — do not re-flag it in prose every week.

## Step 3.6 — EXECUTE page retirements (widened remit, 2026-07-25)

When the data says a page should be retired (a carried, fully-faded, or cannibalizing page — e.g. 2+ weeks flagged in prior reports), you now do BOTH halves yourself in this run:
1. Set "noindex": true in the page's content/ JSON.
2. Add the 301 to vercel.json ("redirects" array, source = the retired path, destination = the surviving franchise page, permanent = true). Keep JSON valid — python3 -c "import json; json.load(open('vercel.json'))" must pass.
3. Rebuild (`python3 generate_content.py`), confirm exit 0.
4. List the retirement under "Executed this run" in the report.
This replaced the old split where the 301 waited for James's manual commit — that gap carried the politicians-june page for 2+ weeks for no reason. The workflow's guarded commit includes vercel.json.

## Step 4 — Generate the franchise-only content brief

Save to `reports/content-week-{monday-date}-to-{sunday-date}.md`.

UP TO 7 specs Mon–Sun; fewer new pages + "improve existing franchise page" slots is encouraged. Allowed NEW formats: E (weird_market_roundup), G (historical_story / Hall of Filth), franchise-differentiated Polymarket-vs-Kalshi comparisons. Never spec B/H/I/commodity-C — the generator auto-noindexes them.

EXECUTION RAIL (2026-07-28): specs in this brief are executed by the external Postwerks pipeline (`Publish: postwerks m2` commits), NOT by an in-repo nightly writer. daily-article.yml is retired (manual-dispatch fallback only). Do not flag the absence of `Article: auto` commits as an outage, and do not spec slots assuming a same-day automated writer — assume Postwerks picks items up on its own cadence.

Each NEW spec: Day+date+working title, slug (MUST pass the content-policy guardrail — no odds-explained, -odds-mean, what-is-a*-bet, nba, weather, -vs-sports-betting, nothing generic/definitional), format code, cluster, primary keyword (weird/funny/outrageous-market or named-entity query), target queries with positions from this week's data, hero market guidance, internal links (franchise pages only, never noindexed pages), editorial note, cannibalization watch with evidence.

Each IMPROVE slot: the page, the specific changes, the data-driven why.

Hard rules: weight HIGH-confidence franchise signals; skip clusters <50% US; carry editorial guardrails (no "why it loses", old-internet aesthetic, no fake data, no offshore links, lowercase headings, human byline); deprioritize NBA/odds/weather/definitions/vs-sports-betting even if demand shows. Reference (don't repeat) `reports/content-brief-2026-05-18.md` and `reports/seo-system-audit-2026-06-05.md` if present. End with falsifiable "success criteria for this week" framed on franchise clicks/CTR.

## Step 5 — Deploy verification (read-only, light)

HTTP-check this week's new franchise slugs and any from last week's brief:
`curl -sS -o /dev/null -w "%{http_code}" -L --max-time 10 {url}`
Bucket LIVE (200) vs BROKEN. New-this-run pages ship when this workflow's commit lands + Vercel builds — normal. Pages from PREVIOUS weeks still broken = real flag. Append a short "Deploy check — {monday-date}" section to the brief, including optional GSC URL Inspection deep links for NEW franchise pages only (https://search.google.com/search-console/inspect?resource_id=sc-domain%3Adollarbets.lol&id={URL-encoded URL}). Never the Indexing API.

## Step 6 — Telegram report → `.ci/telegram-report.txt` (max 1200 chars)

EXACTLY this shape, nothing more:
- Line 1-3: franchise scorecard — total clicks/CTR/position vs last week, best mover, worst mover.
- Line 4: what ran autonomously — "Executed: N quick wins, M retirements" (or "nothing executed").
- Line 5: what the brief ships this week, one line.
- Line 6 (only when true): "K item(s) queued for Saturday" / "⚠️ <one truly urgent thing>".
Fade status, cannibalization detail, deploy checks, data completeness, methodology — reports/gsc-weekly-report.md ONLY. If they're normal, James never needs to read them; if they need him, they're queue items.
