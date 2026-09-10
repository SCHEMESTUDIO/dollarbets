#!/bin/bash
# queue_action.sh — enqueue a James-action into the shared Postwerks actions
# queue (Supabase `actions` table, schema-actions.sql in the postwerks repo)
# instead of pinging Telegram. Notification redesign 2026-07-25: ACTION items
# surface once a week in the Saturday 04:00 UTC digest; instant pings are for
# FAILs only.
#
# Usage: queue_action.sh <key> <title> <body>
#        queue_action.sh <key> <title> --file <path>
#   key    stable dedupe key, e.g. "dogshow:wiki:orphan-pages" — a re-run with
#          the same key bumps last_seen/times_seen, never re-pings, and never
#          resurrects an item James already closed.
#
# Env: SUPABASE_URL, SUPABASE_SERVICE_KEY (org-level secrets recommended so
#      every repo shares them). PROJECT optional (defaults to key prefix).
#      Fail-open: if Supabase is unreachable/missing, falls back to a Telegram
#      ACTION ping via scripts/notify_telegram.sh so nothing is silently lost.
set -u

KEY="${1:?usage: queue_action.sh <key> <title> <body|--file path>}"
TITLE="${2:?missing title}"
if [ "${3:-}" = "--file" ]; then
  BODY=$(cat "${4:?--file needs a path}")
else
  BODY="${3:-}"
fi
PROJECT="${PROJECT:-${KEY%%:*}}"

fallback() {
  echo "queue_action: $1 — falling back to Telegram ACTION ping"
  bash "$(dirname "$0")/notify_telegram.sh" "🖐 ACTION NEEDED
${TITLE}
${BODY}"
  exit 0
}

[ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_KEY:-}" ] \
  || fallback "SUPABASE_URL/SUPABASE_SERVICE_KEY not set"

export QA_KEY="$KEY" QA_TITLE="$TITLE" QA_BODY="$BODY" QA_PROJECT="$PROJECT"
python3 - <<'PYEOF' || fallback "queue write failed"
import json, os, urllib.parse, urllib.request, datetime

url, svc = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
key, title = os.environ["QA_KEY"], os.environ["QA_TITLE"]
body, project = os.environ["QA_BODY"], os.environ["QA_PROJECT"]

def sb(path, method="GET", payload=None, prefer=None):
    h = {"apikey": svc, "Authorization": f"Bearer {svc}",
         "Content-Type": "application/json"}
    if prefer: h["Prefer"] = prefer
    req = urllib.request.Request(f"{url}/rest/v1/{path}", method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else []

qkey = urllib.parse.quote(key)
now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
existing = sb(f"actions?action_key=eq.{qkey}&select=action_key,status,times_seen")
if existing:
    if existing[0]["status"] != "open":
        print(f"queue_action: '{key}' already {existing[0]['status']} — skipped")
    else:
        sb(f"actions?action_key=eq.{qkey}", "PATCH",
           {"last_seen_at": now,
            "times_seen": existing[0].get("times_seen", 1) + 1,
            "title": title, "body": body}, "return=minimal")
        print(f"queue_action: '{key}' re-seen (no ping)")
else:
    sb("actions", "POST",
       [{"action_key": key, "project": project, "title": title,
         "body": body, "source": os.environ.get("GITHUB_WORKFLOW", "ci")}],
       "return=minimal")
    print(f"queue_action: queued '{key}' — surfaces in the Saturday digest")
PYEOF
