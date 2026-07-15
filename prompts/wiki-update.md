# Weekly CLAUDE.md maintenance — CI edition (runs headless in GitHub Actions)

You are maintaining `CLAUDE.md` for the dollarbets.lol codebase (this repo, code root = repo root). It is the codebase reference new sessions read first: file map, tech stack, API endpoints, key functions, data models.

CI rules: read anything, edit ONLY `CLAUDE.md` and `docs/memory/decisions.md`. Do NOT run any git command that writes — the workflow commits after you. Write a short run report to `.ci/telegram-report.txt` (James's Telegram; his only view of this run).

You also maintain `docs/memory/decisions.md` — the repo-resident durable memory (this REPLACED the old Cowork memory files on James's Mac, decision 2026-07-15). Rules for it: append newly discovered durable decisions (strategy calls, architecture changes, hard-won gotchas) with dates; move invalidated entries to its "Superseded" section rather than deleting; keep it decisions-only (no file-map detail — that's CLAUDE.md's job). If a change is neither a codebase fact (CLAUDE.md) nor a durable decision (decisions.md), it goes in the Telegram report only.

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
