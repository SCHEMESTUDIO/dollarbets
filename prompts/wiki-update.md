# Weekly CLAUDE.md maintenance — CI edition (runs headless in GitHub Actions)

You are maintaining `CLAUDE.md` for the dollarbets.lol codebase (this repo, code root = repo root). It is the codebase reference new sessions read first: file map, tech stack, API endpoints, key functions, data models.

CI rules: read anything, edit CLAUDE.md only. Do NOT run any git command that writes — the workflow commits after you. Write a short run report to `.ci/telegram-report.txt` (James's Telegram; his only view of this run).

NOTE: the old local version of this task also maintained Cowork memory files on James's Mac. Those are out of scope in CI — CLAUDE.md is the single source of truth you maintain here. If you find context that belongs in persistent memory rather than CLAUDE.md, put it in your Telegram report under "for James's local memory".

## Steps
1. Read `CLAUDE.md`.
2. Scan the repo: `ls -la` (exclude node_modules, .git, __pycache__, public/, vendored deps); read the first 30 lines of each source/markup/config file for structural changes; `git log --oneline -25` and `git log -1 --stat`; `wc -l` on primary source files.
3. Update CLAUDE.md if: files added/removed/renamed, API endpoints changed, new features or significant code changes, line counts drifted significantly.

## Critical rules
- CLAUDE.md must open with the project-specific do-not-touch warnings (site is live code, generate.py is the backbone, /go/ redirects only, GitHub Actions scanners not Vercel, old-internet design, no "why it loses" sections, no fake data). Preserve these.
- Factual and scannable — tables, not prose.
- Minimal: only change what's actually different. If everything is current, write nothing and say so in the report.
- Verify file existence before writing about a file. Do not invent endpoints, function names, or paths — grep first, cite second.
- Convert relative dates to absolute.

## Report (.ci/telegram-report.txt)
If changed: file → one-line summary per change. If not: one line confirming scan done, HEAD commit checked, no drift.
