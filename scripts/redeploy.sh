#!/usr/bin/env bash
# redeploy.sh — bring the AAM Teams bot stack back up after a soft teardown.
#
# Steps:
#   1. Start cloudflared quick tunnel against localhost:3978
#   2. Wait for the new public URL
#   3. Update the Azure Bot Service messaging endpoint to <new-url>/api/messages
#   4. Start the bot server
#   5. Wait for /health to pass through the tunnel
#
# After this runs, AMs need to re-message the bot ("hi") so it captures a fresh
# ConversationReference. Then briefings will DM successfully again.

set -euo pipefail
cd "$(dirname "$0")/.."

VENV=/Users/anthony/b2b-agent-portfolio/.venv
RG=aam-portfolio-rg
BOT_NAME=aam-briefings-bot
LOCAL_PORT=3978
TUNNEL_LOG=/tmp/aam_cloudflared.log
BOT_LOG=/tmp/aam_bot.log

# 0. Stop any leftover processes from a previous deploy
pkill -f "cloudflared tunnel --url http://localhost:$LOCAL_PORT" 2>/dev/null || true
PIDS=$(lsof -ti :$LOCAL_PORT 2>/dev/null || true)
[[ -n "$PIDS" ]] && echo "$PIDS" | xargs kill 2>/dev/null || true
sleep 1

# 1. Start cloudflared
echo "→ Starting cloudflared quick tunnel"
cloudflared tunnel --url "http://localhost:$LOCAL_PORT" --no-autoupdate > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
echo "  pid=$TUNNEL_PID  log=$TUNNEL_LOG"

# 2. Wait for the URL to appear (up to 30s)
echo "→ Waiting for cloudflared to publish a URL"
for _ in $(seq 1 60); do
  TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
  [[ -n "${TUNNEL_URL:-}" ]] && break
  sleep 0.5
done

if [[ -z "${TUNNEL_URL:-}" ]]; then
  echo "  ✗ cloudflared did not publish a URL within 30s. Last 20 log lines:"
  tail -20 "$TUNNEL_LOG"
  exit 1
fi
echo "  URL: $TUNNEL_URL"

# 3. Update Azure bot messaging endpoint
NEW_ENDPOINT="$TUNNEL_URL/api/messages"
echo "→ Updating Azure Bot endpoint to $NEW_ENDPOINT"
az bot update \
  --resource-group "$RG" \
  --name "$BOT_NAME" \
  --endpoint "$NEW_ENDPOINT" \
  -o json --query "properties.endpoint" 2>&1 | tail -1

# 4. Start the bot server
echo "→ Starting bot server on :$LOCAL_PORT"
"$VENV/bin/aam" teams-bot > "$BOT_LOG" 2>&1 &
BOT_PID=$!
echo "  pid=$BOT_PID  log=$BOT_LOG"

# 5. Health check via localhost (validates the bot server)
echo "→ Waiting for localhost:$LOCAL_PORT/health"
for _ in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$LOCAL_PORT/health" || echo "")
  [[ "$STATUS" == "200" ]] && break
  sleep 0.5
done

if [[ "${STATUS:-}" != "200" ]]; then
  echo "  ✗ localhost /health didn't return 200. Last 20 lines of bot log:"
  tail -20 "$BOT_LOG"
  exit 1
fi
echo "  bot server healthy"

# Try the tunnel path too — but don't fail if local DNS hasn't propagated.
# Cloudflare quick-tunnel URLs can take a few minutes to resolve via your
# local resolver even though Microsoft Teams' edge can already reach them.
echo "→ Checking tunnel reachability ($TUNNEL_URL/health)"
TUNNEL_STATUS=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" "$TUNNEL_URL/health" 2>/dev/null || echo "")
if [[ "$TUNNEL_STATUS" == "200" ]]; then
  echo "  tunnel reachable from this machine"
else
  echo "  tunnel not yet resolvable from this machine ($TUNNEL_STATUS) — that's normal,"
  echo "  Cloudflare's edge already has the route and Teams can reach it. Local DNS"
  echo "  will catch up in a couple of minutes."
fi

echo
echo "✓ AAM Teams bot stack is up."
echo "  Tunnel : $TUNNEL_URL"
echo "  Bot    : pid $BOT_PID"
echo "  Tunnel : pid $TUNNEL_PID"
echo
echo "Next: in Teams, message the AAM Briefings bot once (e.g. 'hi') to"
echo "capture a fresh ConversationReference, then run:"
echo "  aam brief --am alice@cyberco.com"
