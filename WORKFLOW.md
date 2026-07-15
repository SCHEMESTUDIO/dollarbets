# Repo workflow — who writes what (adopted 2026-07-15)

This repo has two writers: **GitHub Actions** (scheduled) and **James/local sessions**.
Every conflict we've ever had came from breaking the ownership rule below.

## Ownership

**Cloud-owned — NEVER edit locally (read-only on the Mac):**
- `gsc-data/**` — weekly GSC pulls (gsc-weekly workflow)
- `reports/**` — weekly reports + content briefs (gsc-weekly workflow)
- `data/boards/**` — board scans (daily-scan workflow)
- `content/**` page JSONs — daily-article + gsc-weekly quick-win edits
- `CLAUDE.md` — wiki-update workflow maintains it
- `public/**` — generated output

**Human-owned — edited locally, never by workflows:**
- Site code (`generate*.py`, templates, styles, `vercel.json`)
- `.github/workflows/**`, `prompts/**`, `scripts/**`

If you must correct a cloud-owned file: `git pull --rebase` first, edit, push
immediately, and expect the next scheduled run to have the final word.

## The two habits

1. **Bookend every local session:** `git pull --rebase` before starting;
   commit + push the same day. Never let local changes age.
2. **Rejected push ≠ conflict.** "Remote contains work you do not have" is
   normal (a bot committed since your pull): `git pull --rebase && git push`.
   An actual merge CONFLICT means the ownership rule was broken — stop and
   look at which file it is.

## Never again

- No local scheduled tasks (Cowork/launchd) may write to this repo. New
  recurring jobs become GitHub workflows.
- All `claude -p` workflow steps pin `--model` and `--max-turns` (cost guard).
- Bot commit steps rebase before push and workflows use `concurrency` groups.
