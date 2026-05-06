#!/usr/bin/env bash
# teardown.sh — stop the AAM Teams bot stack.
#
# Modes:
#   ./teardown.sh              soft  — stop processes only (cloudflared + bot server)
#   ./teardown.sh --hard       hard  — also delete Azure resources (bot, app reg, RG)
#
# After a soft teardown you can `./redeploy.sh` to bring everything back up
# (a new cloudflared URL will be issued and rotated into the Azure bot config
# automatically). After a hard teardown the Azure resources are gone and
# you'd need to run the full Path B setup again.

set -euo pipefail
cd "$(dirname "$0")/.."

MODE="soft"
[[ "${1:-}" == "--hard" ]] && MODE="hard"

echo "→ Mode: $MODE"

# 1. Kill local processes (idempotent — pkill returns nonzero if nothing matched)
echo "→ Stopping cloudflared tunnel(s)…"
pkill -f "cloudflared tunnel --url http://localhost:3978" 2>/dev/null && echo "  cloudflared stopped" || echo "  no cloudflared running"

echo "→ Stopping bot server (anything bound to :3978)…"
PIDS=$(lsof -ti :3978 2>/dev/null || true)
if [[ -n "$PIDS" ]]; then
  echo "$PIDS" | xargs kill 2>/dev/null || true
  sleep 1
  # Force kill anything that didn't go down cleanly
  REMAINING=$(lsof -ti :3978 2>/dev/null || true)
  [[ -n "$REMAINING" ]] && echo "$REMAINING" | xargs kill -9 2>/dev/null || true
  echo "  bot server stopped (pids: $PIDS)"
else
  echo "  no bot server running"
fi

# 2. Clear the local conversation refs so a redeploy starts clean
if [[ -f aam.db ]]; then
  echo "→ Clearing teams_conversation_refs (forces re-install on redeploy)"
  /Users/anthony/b2b-agent-portfolio/.venv/bin/python -c "
import sqlite3
c = sqlite3.connect('aam.db')
try:
    n = c.execute('DELETE FROM teams_conversation_refs').rowcount
    c.commit()
    print(f'  deleted {n} ref(s)')
except sqlite3.OperationalError:
    print('  no refs table yet')
"
fi

if [[ "$MODE" == "soft" ]]; then
  echo
  echo "✓ Soft teardown complete. Azure resources still exist."
  echo "  Restart with: ./scripts/redeploy.sh"
  exit 0
fi

# 3. Hard teardown — delete Azure resources
echo
echo "→ Hard teardown: deleting Azure resources"

if [[ ! -f /tmp/aam_bot_app_id.txt ]]; then
  echo "  ⚠ /tmp/aam_bot_app_id.txt not found — can't auto-delete the app reg."
  echo "    Find it manually with: az ad app list --display-name 'AAM Briefings Bot'"
else
  APP_ID=$(cat /tmp/aam_bot_app_id.txt)
  echo "  deleting app registration $APP_ID"
  az ad app delete --id "$APP_ID" 2>&1 | tail -1 || echo "    (app already deleted)"
fi

echo "  deleting resource group aam-portfolio-rg (this removes the Azure Bot resource)"
az group delete --name aam-portfolio-rg --yes --no-wait 2>&1 | tail -1 || echo "    (resource group already deleted or doesn't exist)"

echo
echo "✓ Hard teardown initiated."
echo "  Resource group deletion runs async; check progress with:"
echo "    az group show -n aam-portfolio-rg"
echo
echo "  You'll also want to remove the AAM Briefings app from Teams manually:"
echo "    Teams → Apps → Manage your apps → AAM Briefings → ⋯ → Uninstall"
