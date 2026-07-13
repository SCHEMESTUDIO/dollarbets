# GSC API + Auto-Publish Setup (2026-06-11 rebuild)

One-time setup for the rebuilt automation pipeline. After this, Mondays are
zero-touch: launchd pulls GSC data → Claude analyzes + writes the brief →
Claude drafts articles daily → launchd publishes daily.

**The one design rule:** Claude agents write files but never touch `.git`.
`publish.sh` is the single git writer. If you ever see an `index.lock` problem
again, something violated this rule.

## Part 1 — Google service account (~15 min, the only fiddly part)

1. Go to https://console.cloud.google.com/ — create a project (or reuse one),
   e.g. `dollarbets-gsc`.
2. **APIs & Services → Library** → search "Google Search Console API" → Enable.
3. **IAM & Admin → Service Accounts → Create service account.**
   Name: `gsc-reader`. No roles needed (GSC permissions are granted in Search
   Console, not IAM). Create.
4. Open the service account → **Keys → Add key → Create new key → JSON.**
   A `.json` file downloads.
5. Save it:
   ```
   mkdir -p ~/.config/dollarbets
   mv ~/Downloads/dollarbets-gsc-*.json ~/.config/dollarbets/gsc-service-account.json
   chmod 600 ~/.config/dollarbets/gsc-service-account.json
   ```
6. Grant it Search Console access: https://search.google.com/search-console
   → property `sc-domain:dollarbets.lol` → **Settings → Users and permissions
   → Add user** → paste the service account email (looks like
   `gsc-reader@dollarbets-gsc.iam.gserviceaccount.com`) → permission
   **Restricted** (read-only is all it needs).

## Part 2 — Verify

```
cd ~/Documents/Claude/Projects/Dollar\ Bets/site
python3 scripts/gsc_pull.py --selftest    # tests JWT signing, no network
python3 scripts/gsc_pull.py               # real pull — writes gsc-data/ CSVs
```

A successful run logs `auth OK` then `wrote gsc-data/...` lines. Common
failures:
- `Token exchange failed ... invalid_grant` → key JSON is wrong or clock skew
- `API query failed (HTTP 403)` → service account email not added in Search
  Console yet (step 6), or wrong property name
- Empty CSVs → property has data lag; the script ends its window 2 days back
  by design

## Part 3 — Install the launchd jobs

```
cp scripts/launchd/com.dollarbets.*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dollarbets.gsc-pull.plist
launchctl load ~/Library/LaunchAgents/com.dollarbets.publish.plist
```

Schedule (local time):
- **gsc-pull** — Mondays 7:45 (before the 8:49 weekly-gsc-analysis task)
- **publish** — daily 11:30 (after the 10:30 daily-article-batch task)

If the Mac is asleep at fire time, launchd runs the job once on wake — jobs
are not silently skipped. Logs: `~/Library/Logs/dollarbets-gsc-pull.log` and
`dollarbets-publish.log`.

Test publish manually any time: `bash scripts/publish.sh` (it's a no-op when
there's nothing staged-worthy).

To pause auto-publishing: `launchctl unload ~/Library/LaunchAgents/com.dollarbets.publish.plist`

## Part 4 — What changed in the Claude scheduled tasks (already done)

- **weekly-gsc-analysis** (Mon 8:49): no longer scrapes Chrome or runs git.
  Reads the CSVs gsc-pull wrote, produces report + brief, and now EXECUTES
  trivial quick wins (title/meta edits ≤15 min) itself instead of
  recommending them week after week.
- **daily-article-batch** (moved 8:07 → 10:30 so Monday's run sees the fresh
  brief): writes + builds the article, runs no git. publish.sh ships it at
  11:30.

## Pipeline at a glance

```
Mon 7:45   launchd gsc-pull      → gsc-data/ CSVs           (script, no LLM)
Mon 8:49   weekly-gsc-analysis   → report + content brief    (Claude, no git)
                                  + executes trivial quick wins
Daily 10:30 daily-article-batch  → article JSON + built HTML (Claude, no git)
Daily 11:30 launchd publish      → commit scoped paths, rebase, push → Vercel
```
