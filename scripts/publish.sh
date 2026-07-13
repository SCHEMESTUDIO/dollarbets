#!/bin/bash
# publish.sh — the ONLY thing that commits/pushes content for dollarbets.lol.
#
# Design rule (2026-06-11 rebuild): Claude agents write files, never touch
# .git. This script is the single git writer. Runs daily via launchd
# (com.dollarbets.publish) or manually: bash scripts/publish.sh
#
# Guards:
#   - scoped paths only (content/ public/ data/ gsc-data/)
#   - stale index.lock cleanup (>10 min old); fresh lock = abort, don't fight
#   - NEW pages that carry an unexpected noindex tag are excluded from the
#     commit (off-policy page; the daily task should have caught it)
#   - rebase onto origin/main; abort cleanly on conflict, never force-push

set -u
SITE="$HOME/Documents/Claude/Projects/Dollar Bets/site"
SCOPED_PATHS=(content public data gsc-data)

log() { echo "[publish $(date '+%F %T')] $*"; }

cd "$SITE" || { log "FATAL: site dir not found: $SITE"; exit 1; }

# --- stale lock handling -----------------------------------------------------
if [ -f .git/index.lock ]; then
  lock_mtime=$(stat -c %Y .git/index.lock 2>/dev/null || stat -f %m .git/index.lock)
  age=$(( $(date +%s) - lock_mtime ))
  if [ "$age" -gt 600 ]; then
    log "removing stale index.lock (age ${age}s)"
    rm -f .git/index.lock
  else
    log "fresh index.lock (age ${age}s) — another git process is running, aborting"
    exit 1
  fi
fi

# --- stage scoped paths ------------------------------------------------------
git add -A -- "${SCOPED_PATHS[@]}" 2>/dev/null

# --- noindex guard on NEWLY ADDED pages --------------------------------------
# Intentionally-noindexed commodity pages already exist in git; this only
# checks pages new in this commit. A new franchise page must be indexable.
while IFS= read -r f; do
  [ -f "$f" ] || continue
  if grep -q 'content="noindex' "$f"; then
    slug=$(dirname "$f"); slug=${slug#public/}
    log "GUARD: new page '$slug' carries noindex — excluding from publish (off-policy?)"
    git reset -q -- "$f"
    # exclude its content JSON twin too, so the inconsistency is visible, not shipped
    base=$(basename "$slug")
    json=$(git diff --cached --name-only --diff-filter=A -- 'content/' | grep "/${base}\.json$" || true)
    [ -n "$json" ] && git reset -q -- $json && log "GUARD: also excluded $json"
  fi
done < <(git diff --cached --name-only --diff-filter=A -- 'public/' | grep '/index\.html$')

# --- anything to do? ----------------------------------------------------------
if git diff --cached --quiet; then
  log "nothing to publish"
  exit 0
fi

summary=$(git diff --cached --name-only | sed 's|/index.html||' | head -5 | xargs -I{} basename {} | sort -u | tr '\n' ' ')
git commit -m "Publish: auto $(date +%F) — ${summary}" || { log "commit failed"; exit 1; }

# --- sync + push --------------------------------------------------------------
git fetch origin || { log "fetch failed (offline?) — commit kept locally, will push next run"; exit 1; }
if ! git -c rebase.autostash=true rebase origin/main; then
  git rebase --abort 2>/dev/null
  log "REBASE CONFLICT — manual fix needed. Commit is local; nothing was pushed or lost."
  exit 1
fi
git push origin HEAD:main || { log "push failed — commit kept locally, will retry next run"; exit 1; }
log "published OK: ${summary}"
