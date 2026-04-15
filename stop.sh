#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# stop.sh — Hentikan semua service BOT-ANDRO
# ================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

echo "🛑 Menghentikan BOT-ANDRO..."

# Stop via PID file
if [ -f "$LOG_DIR/fastapi.pid" ]; then
    FASTAPI_PID=$(cat "$LOG_DIR/fastapi.pid")
    kill "$FASTAPI_PID" 2>/dev/null && echo "  ✅ FastAPI (PID $FASTAPI_PID) dihentikan"
    rm -f "$LOG_DIR/fastapi.pid"
fi

if [ -f "$LOG_DIR/cloudflare.pid" ]; then
    CF_PID=$(cat "$LOG_DIR/cloudflare.pid")
    kill "$CF_PID" 2>/dev/null && echo "  ✅ Cloudflare (PID $CF_PID) dihentikan"
    rm -f "$LOG_DIR/cloudflare.pid"
fi

# Fallback: kill by name
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true

echo "  ✅ Semua service dihentikan."
