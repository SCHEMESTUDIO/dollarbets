#!/bin/bash
# notify_telegram.sh — send a message to the Scheme Ops Telegram channel.
# Usage: notify_telegram.sh "message text"   OR   notify_telegram.sh --file path.txt
# Env: TELEGRAM_BOT_TOKEN, TELEGRAM_OPS_CHAT_ID
# Plain text (no parse_mode) so arbitrary report content can never break the send.
set -u

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_OPS_CHAT_ID:-}" ]; then
  echo "notify_telegram: TELEGRAM_BOT_TOKEN / TELEGRAM_OPS_CHAT_ID not set — skipping notify"
  exit 0
fi

if [ "${1:-}" = "--file" ]; then
  MSG=$(cat "$2")
else
  MSG="$*"
fi

# Telegram hard limit is 4096 chars per message; truncate with a marker.
if [ "${#MSG}" -gt 3900 ]; then
  MSG="${MSG:0:3900}
…[truncated — full report in repo]"
fi

HTTP=$(curl -sS -o /tmp/tg_resp.json -w "%{http_code}" \
  --data-urlencode "chat_id=${TELEGRAM_OPS_CHAT_ID}" \
  --data-urlencode "text=${MSG}" \
  --data-urlencode "disable_web_page_preview=true" \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" || echo "000")

if [ "$HTTP" != "200" ]; then
  echo "notify_telegram: send failed (HTTP $HTTP)"; cat /tmp/tg_resp.json 2>/dev/null
  exit 1
fi
echo "notify_telegram: sent (${#MSG} chars)"
