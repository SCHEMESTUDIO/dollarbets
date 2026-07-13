#!/bin/bash
# ci_guarded_commit.sh — the CI successor to publish.sh's guard logic.
# Stages ONLY scoped paths, excludes any NEW page whose generated HTML carries
# an unexpected noindex tag (off-policy page — the writing task should have
# caught it), commits, and pushes.
#
# Usage: ci_guarded_commit.sh "commit message" [scoped paths...]
# Default scoped paths: content public data gsc-data reports
set -u

MSG="${1:?commit message required}"
shift
SCOPED=("${@:-}")
if [ -z "${SCOPED[0]:-}" ]; then
  SCOPED=(content public data gsc-data reports)
fi

git config user.name "Dollar Bets Bot"
git config user.email "bot@dollarbets.lol"

# --- noindex guard: exclude brand-new public pages that carry noindex --------
# (Mirrors publish.sh. generate.py intentionally noindexes commodity slugs; a
# NEW page arriving with noindex means the slot was off-policy and must not ship.)
EXCLUDED=""
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if grep -q 'content="noindex' "$f" 2>/dev/null; then
    dir=$(dirname "$f")
    slug=$(basename "$dir")
    echo "GUARD: new page '$slug' carries noindex — excluding from commit"
    EXCLUDED="$EXCLUDED $dir"
    # Also exclude its content JSON (pages/ or hall-of-filth/)
    for j in "content/pages/${slug}.json" "content/hall-of-filth/${slug}.json"; do
      [ -f "$j" ] && EXCLUDED="$EXCLUDED $j"
    done
  fi
done < <(git ls-files --others --exclude-standard -- public/ | grep '/index\.html$' || true)

git add -- "${SCOPED[@]}" 2>/dev/null || true

for path in $EXCLUDED; do
  git reset -q HEAD -- "$path" 2>/dev/null || true
  git rm -r --cached -q -- "$path" 2>/dev/null || true
done

if git diff --staged --quiet; then
  echo "No changes to commit"
  echo "changed=false" >> "${GITHUB_OUTPUT:-/dev/null}"
  exit 0
fi

git commit -m "$MSG"
# Rebase onto latest origin/main in case a parallel workflow committed meanwhile.
git pull --rebase origin main || { echo "GUARD: rebase conflict — aborting push"; git rebase --abort 2>/dev/null; exit 1; }
git push
echo "changed=true" >> "${GITHUB_OUTPUT:-/dev/null}"
if [ -n "$EXCLUDED" ]; then
  echo "excluded=$EXCLUDED" >> "${GITHUB_OUTPUT:-/dev/null}"
fi
