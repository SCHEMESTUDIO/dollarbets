# Daily X posts — setup and ops

The agent that posts 3 cards/day from the board to **@dollarbetslol**.

## What's in place

- `scripts/daily_tweets.py` — the agent. `--mode run` is the scheduled entry
  point: make sure a queue exists for the latest board (Claude picks two, the
  board's own filthy little longshot is always slot 3), then post the next slot
  that hasn't gone out. Idempotent — never double-posts, never re-selects.
- `share_card.py` — renders the 1080×1080 post image for every market at build
  time: `/share/{ticker}/card.png`. Two variants: the light **tile** (board
  picks) and the dark **ticket** (the longshot). The 1200×630 `og.png` stays
  for link previews.
- `.github/workflows/daily-tweets.yml` — three cron fires a day, 12:30 / 16:30
  / 00:30 UTC (8:30am / 12:30pm / 8:30pm ET). The slot is decided by queue
  state, not by the clock, so GitHub's cron drift cannot skip a post.
- `data/social-queue/YYYY-MM-DD.json` — the day's picks + post state, keyed by
  **board** date, committed to git as a public record. Shared with the
  Telegram rail.

## When it runs, and why the slots are queue-driven

GitHub fires cron late and unevenly. Measured over the week to 2026-09-18 the
08:00 UTC board scan started between 12:41 and 14:45, and the 22:00 one
sometimes after midnight UTC, which makes the file-gated scan build *tomorrow's*
board at 00:08. So:

- **Selection is triggered by the scan finishing** (`workflow_run`), not by
  the clock. The queue for a new board exists the minute the board does.
- **Posting drains the oldest queue that still has an unposted slot**, as long
  as its board is at most a day older than the latest. A board landing at
  00:08 no longer orphans yesterday's longshot.
- Cron fires at 13:45 / 17:30 / 00:30 UTC, behind the usual board landing.

## The photo behind the card

At post time `scripts/social_photo.py` tries to put a subject-matched photo
behind the card:

1. Opus 5 writes two search phrases in plain nouns (scene, not subject).
2. Pexels is searched (needs `PEXELS_API_KEY`). Every candidate is scored for
   darkness and low detail; the best 16 go to Haiku 4.5, which picks one or
   none, rejecting people, logos, text and anything about the wrong subject.
3. If Pexels has nothing acceptable, Openverse (commercial-use CC only) gets
   the same treatment.
4. Nothing acceptable = the plain card. A photo is never forced.

Cost is about 4,300 input tokens per card, roughly $0.02 with Opus on the
phrases and Haiku on the ranking; under a dollar a month at three a day. The
queue file records source, id, page, photographer and licence for every
photo used. `SOCIAL_PHOTOS=0` (repo variable) switches the whole thing off.

## What a post is

Parent post = the quip as the text, the card as the image, **no link**. A
self-reply carries the share link (`TWEET_LINK_MODE=reply`). X throttles posts
with an external URL in the body; the reply keeps the parent eligible for For
You and still carries the click.

## One-time setup — DONE 2026-09-19

- X account: @dollarbetslol, Premium (blue check, For You ranking boost).
- Developer account: pay-per-use, app `2101241197779976193dollarbetsl`, OAuth
  1.0a permissions **Read and write**, app type "Web App, Automated App or Bot".
- Repo secrets: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`,
  `X_ACCESS_TOKEN_SECRET` (+ the existing `ANTHROPIC_API_KEY`).
- Repo variables: `TWEET_LIVE=0`, `TWEET_LINK_MODE=reply`.
- Credits: the pay-per-use balance must be above zero or every post 402s.
  Console → Buy Credits. ~$20 covers a month.

Pricing as verified 2026-09-19 (docs.x.com/x-api/getting-started/pricing):
$0.015 per post without a URL, $0.20 per post containing a URL. Reply mode is
$0.215 per card → ~$19/month at 3/day.

## Going live

1. Merge the card PR. Wait for the Vercel deploy — cards only exist after a
   build with `share_card.py` in it. Check one:
   `https://www.dollarbets.lol/share/<ticker>/card.png`.
2. Enable the workflow (it was disabled by hand in June):
   `gh workflow enable "Daily X Tweets" -R SCHEMESTUDIO/dollarbets`
3. Smoke test: Actions → Daily X Tweets → Run workflow → `mode = dry-run-all`.
   The log shows all three posts composed and the card bytes downloaded; a
   queue file is committed.
4. Flip live: `gh variable set TWEET_LIVE -b 1 -R SCHEMESTUDIO/dollarbets`.
   The next cron fire posts the next unposted slot. Or trigger `mode = run` by
   hand and watch it land.
5. Leave it. Three fires a day, three posts a day.

## Ops cheat sheet

| Need to... | Do this |
|---|---|
| Pause posting | `gh variable set TWEET_LIVE -b 0` |
| Skip today | Same — the unposted slots just never go out; tomorrow's board makes a new queue |
| Re-run a missed slot | Actions → Run workflow → `mode = run` (posts the next unposted) |
| Force a re-selection | Delete today's queue file from `data/social-queue/`, run `mode = run` |
| Preview without posting | Run workflow with `live = 0` |
| Change times | Edit `cron` in the workflow |
| Put the link in the body instead | `gh variable set TWEET_LINK_MODE -b inline` |

## Things to watch

**Card 404s.** The image is rebuilt on every deploy. If the morning scan or
the Vercel build fails, the fetch fails and the run aborts rather than posting
a broken card. The PNG magic-byte check in `download_image()` is what catches
a 200-disguised error page — don't remove it.

**Zero credit balance.** Pay-per-use draws from a prepaid balance. When it hits
zero every post fails. Auto-recharge is optional; a hard balance is also a
spend cap.

**Stale board.** The queue is keyed by board date. If the board stops updating,
the three slots for the last board post and then nothing more goes out — by
design. Fix the board, not the poster.

**Selection quality.** Claude picks two from the board. The anti-dupe corpus is
the last 14 days of queue files, keyed by ticker, so it won't repeat a market
but can repeat a topic. Tighten `SELECTION_PROMPT` if that becomes a pattern.

**Telegram.** `daily_telegram.py` still maps slots from the clock hour and
reads `utc_today()`. It is disabled and untouched by the card PR; if it is
ever switched on, port it to the queue-state model first.

## Measurement

The reply link carries `utm_source=x&utm_medium=daily_card`. Judge the rail on
GA4 sessions from that source against API spend. Written gate: thirty days
live; if clicks per dollar don't beat the paid campaign on dogshow, pause it.
