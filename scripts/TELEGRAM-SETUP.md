# Daily Telegram Posts — setup

Mirrors the X workflow. Reads the same daily queue file, posts the same 3 cards as photo+caption to your Telegram channel and group.

## What's already in place

- `scripts/daily_telegram.py` — reads `data/social-queue/YYYY-MM-DD.json`, posts via Bot API
- `.github/workflows/daily-telegram.yml` — cron at 13:05 / 17:05 / 21:05 UTC (5 min after X workflow so the queue file exists)
- Queue file structure — already includes a pre-rendered `telegram_caption_html` per slot, locked at selection time, so what you see in dry-run is exactly what posts

The Telegram script does NOT trigger a Claude selection — that's the X workflow's job. This keeps both platforms on the same 3 picks each day and halves Claude spend.

## Cost

**$0.** Telegram Bot API is free. Rate limits are generous (30 messages/sec total, 20/min per group). Three posts/day to two chats = 6 calls/day. Well below any limit.

## One-time setup

### 1. Create the bot

In Telegram, open <https://t.me/BotFather>:
1. `/newbot`
2. Pick a display name (e.g. "Dollar Bets")
3. Pick a username — must end in `bot`, e.g. `@dollarbets_bot`
4. BotFather returns a token like `123456789:ABCdef...` — copy it, this is `TELEGRAM_BOT_TOKEN`
5. (Optional) `/setdescription`, `/setuserpic`, `/setcommands` — basic profile

### 2. Create the channel and group, add the bot

**Channel** (broadcast, looks like a feed):
1. New Channel → set name, public or private, etc.
2. Channel → Administrators → Add Administrator → search the bot username → grant **Post Messages** permission (the only one needed)

**Group** (conversational):
1. New Group → invite the bot as a regular member
2. The bot does NOT need admin in the group, just membership

### 3. Find the numeric chat IDs

The most reliable way:

1. Send any message in the channel and another in the group (the bot needs at least one event to surface them)
2. In a browser, visit:
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look at the JSON. For each chat you'll see something like:
   ```
   "chat": { "id": -1001234567890, "title": "Dollar Bets", "type": "channel" }
   "chat": { "id": -987654321,     "title": "Dollar Bets Chat", "type": "supergroup" }
   ```
4. The negative numbers are your chat IDs. Channels and supergroups always start with `-100`; older groups start with `-`.

Alternative: for **public channels** you can use `@channelusername` as the chat ID instead of the numeric. The script accepts either.

If `getUpdates` returns an empty `result: []`, post a fresh message in the chat and refresh. Bot needs to be "active" in the chat for it to appear.

### 4. Add secrets to GitHub repo

In <https://github.com/SCHEMESTUDIO/dollarbets/settings/secrets/actions>:

| Secret name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | From BotFather |
| `TELEGRAM_CHANNEL_ID` | Numeric ID (e.g. `-1001234567890`) or `@channelname` |
| `TELEGRAM_GROUP_ID` | Numeric ID (e.g. `-987654321`) |

You can omit either CHANNEL_ID or GROUP_ID — the script posts to whichever is set. Empty = skipped.

### 5. Add repo variable

In <https://github.com/SCHEMESTUDIO/dollarbets/settings/variables/actions>:

| Variable | Value | Notes |
|----------|-------|-------|
| `TELEGRAM_LIVE` | `0` (for now) | Set to `1` to actually post |

## Going live — recommended sequence

### Day 0: dry-run

- Actions → **Daily Telegram Posts** → Run workflow → `slot = all`, `live = inherit` (still 0)
- Confirm 3 captions render correctly in the log, both target chat IDs are recognized
- No actual posts hit Telegram

### Day 1: live-fire one slot

- Set repo variable `TELEGRAM_LIVE = 1`
- Manually trigger with `slot = 1`
- Verify the photo + caption show correctly in both channel and group
- Check formatting: bold title, italic quip, working link

### Day 2+: scheduled

- Cron takes over at 13:05 / 17:05 / 21:05 UTC daily
- The X workflow at :00 selects → commits queue
- The Telegram workflow at :05 reads queue → posts

## How the two workflows coordinate

```
13:00 UTC  daily-tweets.yml runs:
           - Claude picks 3 cards
           - Writes data/social-queue/YYYY-MM-DD.json
           - Posts slot 1 to X
           - Commits queue file with X post state filled in

13:05 UTC  daily-telegram.yml runs:
           - git pull --rebase (picks up the commit)
           - Reads data/social-queue/YYYY-MM-DD.json
           - Posts slot 1 to channel + group
           - Commits queue file with Telegram post state filled in

17:00 UTC  daily-tweets.yml posts slot 2 to X
17:05 UTC  daily-telegram.yml posts slot 2 to TG

21:00 UTC  daily-tweets.yml posts slot 3 to X
21:05 UTC  daily-telegram.yml posts slot 3 to TG
```

The queue file is the single source of truth. Both workflows append to it without overwriting each other (X writes only to `posts.x.*`, Telegram writes only to `posts.telegram_*.*`).

## Things to watch for

**Photo-by-URL caching.** We send `photo=https://www.dollarbets.lol/share/.../og.png` and Telegram fetches it server-side. Telegram caches by URL — if the same URL serves different bytes later (e.g., we regenerate the OG image with a fixed typo), Telegram may keep serving the old cached version. To force a refresh, append a cache-buster: `?v=2`. Not an issue in normal operation.

**HTML escaping.** Titles and quips from Claude/Kalshi are HTML-escaped in `build_telegram_caption_html`. If you change the caption template, keep the `_html.escape(...)` calls or a malicious-looking title (`<script>`-style) would break rendering. Telegram HTML mode only accepts a tiny tag set (`<b> <i> <u> <s> <a> <code> <pre>`) — anything else fails the parse_mode check and the whole sendPhoto errors out.

**Bot needs to stay admin in the channel.** If someone accidentally demotes the bot, sendPhoto returns a 403. The workflow log will show `"description":"Bad Request: not enough rights"`. Re-promote the bot, retry the slot manually.

**Channel vs group voice.** Channels are broadcast — no replies, fewer dynamics. Groups invite reactions and conversation. The same caption goes to both. If you later want different copy per target (e.g., conversational prompt in the group), add a second caption builder and switch on `state_key` in `post_slot`. Easy edit.

## Manual ops cheat sheet

| Need to... | Do this |
|------------|---------|
| Pause Telegram only (leave X running) | Set repo var `TELEGRAM_LIVE = 0` |
| Re-post a missed slot | Actions → Run workflow → `slot = 2` (or 3) |
| Skip the group, channel-only | Delete `TELEGRAM_GROUP_ID` secret |
| Skip the channel, group-only | Delete `TELEGRAM_CHANNEL_ID` secret |
| Change drip times | Edit `cron` in `.github/workflows/daily-telegram.yml` (keep +5 min offset from X) |
| Inspect what posted today | `cat data/social-queue/$(date -u +%Y-%m-%d).json` in repo |
