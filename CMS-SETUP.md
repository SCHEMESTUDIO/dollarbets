# Dollar Bets CMS — Setup Guide

## What it does

The CMS is a password-protected admin page at `/admin/` that lets editors:
- Edit quip copy on any bet
- Change titles, Kalshi URLs, payouts, tiers, and categories
- Reorder or remove bets from a board
- Add new bets manually (with a title + Kalshi URL)

Every save commits the updated board JSON to GitHub, which triggers an automatic Vercel rebuild. Changes go live in ~30 seconds.

## Architecture

```
/admin/              → static HTML page (old-internet CMS UI)
/api/login           → Vercel Python function (validates password)
/api/board           → Vercel Python function (reads/writes board JSON via GitHub API)
data/boards/*.json   → board data (committed to git, read by generate.py at build time)
```

No database. Git is the database. GitHub commit history is your audit trail.

## Required Environment Variables

Set these in Vercel Dashboard → Settings → Environment Variables:

| Variable | Example | Description |
|---|---|---|
| `CMS_PASSWORD` | `your-editor-password` | Shared password for all editors. Pick something strong. |
| `CMS_SECRET` | `a-random-secret-key` | HMAC signing key for session tokens. If not set, falls back to CMS_PASSWORD. |
| `GITHUB_TOKEN` | `ghp_xxxxxxxxxxxx` | GitHub Personal Access Token with `repo` scope (needs write access to push commits). |
| `GITHUB_REPO` | `yourusername/dollarbets` | The `owner/repo` slug for your GitHub repository. |
| `GITHUB_BRANCH` | `main` | Optional. Defaults to `main`. The branch the CMS writes to. |

## Setting up the GitHub Token

1. Go to https://github.com/settings/tokens
2. Generate a **Fine-grained personal access token**
3. Select only the Dollar Bets repository
4. Grant **Contents: Read and write** permission
5. Copy the token and add it as `GITHUB_TOKEN` in Vercel

## How it works

1. Editor goes to `dollarbets.lol/admin/`
2. Enters the shared password
3. Backend validates password, returns a time-limited HMAC token (24h)
4. Editor picks a date, sees all bets on that board
5. Edits quips, URLs, payouts, etc.
6. Clicks "save & publish"
7. CMS commits the updated JSON to GitHub via the API
8. Vercel detects the commit and rebuilds the site
9. ~30 seconds later, changes are live

## Security notes

- The `/admin/` page is `noindex, nofollow` — search engines won't find it
- Auth tokens expire every 24 hours
- All writes go through the GitHub API, so you get full commit history
- The CMS password should be shared only with trusted editors
- GitHub token permissions are scoped to just the repo
