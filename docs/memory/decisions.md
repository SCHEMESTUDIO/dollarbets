# Dollar Bets — durable decisions log

Repo-resident project memory. Read by local sessions AND cloud workflows —
this file (not any machine-local memory) is the shared source of truth for
*why* things are the way they are. Maintained by the weekly wiki-update
workflow: append new durable decisions, mark superseded ones, never silently
delete. Keep entries short; link evidence.

## Strategy

- **2026-06-05 — Franchise-only content (THE strategic decision).** Full SEO
  audit: only brand-native editorial about specific weird/funny/outrageous
  prediction markets earns clicks (/crazy-kalshi-bets/ pos ~7, 11%+ CTR).
  Commodity informational content (odds explainers, "what is a X bet", NBA,
  weather, generic vs-sports-betting) ranks page 8 with zero clicks and harms
  the site. 24 commodity pages noindexed; `BLOCKED_SLUG_PATTERNS` /
  `policy_noindex()` in generate.py auto-noindexes new commodity slugs.
  Expect total impressions to FALL as the prune is honored — that is healthy,
  not a regression. Scorecard = franchise clicks/CTR, never total impressions.
- **Geographic skew rule:** clusters >50% non-US impressions are deprioritized.
- **Editorial guardrails:** old-internet aesthetic; human byline; no "why it
  loses" framing; no fake data/odds; Kalshi affiliate link only (no offshore
  books); lowercase headings; quip voice ("A buck says maybe.").

## Architecture

- **2026-07-03 → 2026-07-15 — Cloud migration (complete).** All recurring
  automation runs in GitHub Actions; nothing recurring runs on the Mac.
  Reporting rail = Telegram bot → James's DM (chat id 1425135907). GSC auth =
  service account key in `GSC_CREDENTIALS_JSON` (user-ADC failed in CI with
  `invalid_rapt`; org policy for key creation overridden at project level
  2026-07-15). launchd pair + local Cowork twins retired.
- **2026-07-15 — Model pinning.** Every `claude -p` workflow step pins
  `--model claude-sonnet-5` + `--max-turns` (unpinned steps defaulted to Opus
  and 10×'d the bill). Never ship an unpinned model call.
- **2026-07-15 — File ownership (see WORKFLOW.md).** Cloud owns gsc-data/,
  reports/, data/boards/, content/, public/, CLAUDE.md. Enforced by
  `.githooks/pre-commit` (`ALLOW_CLOUD_EDIT=1` to override). Sandboxed
  sessions: no git writes over the mount (orphaned index.lock root cause);
  reads use `GIT_OPTIONAL_LOCKS=0`; verify remote via `git ls-remote`.
  The pre-2026-07-15 "never fetch" rule is revoked — it caused sessions to
  report phantom outages from a 3-week-stale clone.
- **2026-07-20 — Cost audit: fewer scans, cheaper quips (commit 70933d0).**
  `daily-scan.yml` cron cut from 6 runs/day (`0 8,16,19,22,1,4`) to 3
  (`0 8,16,22`) — the dropped slots were redundant sports/combo refreshes.
  Quip generation in `scanner.py` + `sports_scanner.py` moved from
  `claude-sonnet-4-6` to `claude-haiku-4-5-20251001`. Don't revert either
  change without checking the cost impact first.

- **2026-07-28 — daily-article.yml retired (replaced by Postwerks).**
  Net-new article writing/publishing moved to the external Postwerks pipeline
  (`Publish: postwerks m2 — {slug}` commits, seo-plan/seo-publish workflows in
  the private postwerks repo, GH_PUBLISH_TOKEN secret there). `Article: auto`
  commits ceasing after 2026-07-17 was intentional, NOT an outage — do not
  re-diagnose it. daily-article.yml keeps `workflow_dispatch` as a manual
  fallback; its schedule is removed. Weekly briefs are now consumed by
  Postwerks, not by a nightly in-repo writer.

- **2026-08-08 — Quip model upgraded to Opus-5 (commit 435b5bc).**
  Three-model tier restructure: (1) `QUIP_MODEL = "claude-opus-5"` — writes
  original quips with extended thinking (fixes Sonnet-5 reliability where it
  returned blank despite tiny budget), (2) `PAIRING_MODEL = "claude-sonnet-5"`
  — ranks/pairs best pool quip per bet (mechanical, not creative), (3) taste
  engine + GSC/wiki workflows dropped to `claude-haiku-4-5-20251001` (ops tier,
  not product tier). Quips are THE product and volume is tiny (hundreds of
  tokens/day), so the joke writer gets top tier. Fallback: if thinking/timeout
  fails, board ships with pool quips, never blank. Optional upgrade path:
  swap Opus for `"claude-fable-5"` (2x cost, unmeasured humor gain—A/B first).

## Superseded (kept for archaeology)

- ~~2026-06-11 rebuild: publish.sh sole git writer via launchd 11:30~~ →
  replaced by ci_guarded_commit.sh in Actions (2026-07-13).
- ~~"Indexing is the bottleneck" thesis~~ → misdiagnosis; absent from
  Pages.csv means "earned no impressions", not "not indexed" (2026-06-05).
- ~~daily-article.yml nightly writer (09:30 UTC, part of the 07-13 cloud
  migration)~~ → retired 2026-07-28; replaced by Postwerks publishing.
