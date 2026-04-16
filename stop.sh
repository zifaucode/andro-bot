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

# Kill worker python script jika ada yang tersangkut/berjalan di background
pkill -f "python worker.py" 2>/dev/null || true
echo "  ✅ Membersihkan memori proses Bot (Worker)..."

# Mematikan Wake Lock agar baterai kembali normal (bisa mode sleep/istirahat)
echo "  ✅ Mematikan fitur Wake-Lock (Baterai HP kembali nomal)..."
termux-wake-unlock 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✅ SELURUH SERVICE SERVER TELAH BERHASIL DIMATIKAN!     ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Untuk menutup Termux hingga bersih dan tak memakan RAM: ║"
echo "║  👉 Ketik perintah ---->  exit   (lalu tekan Enter)      ║"
echo "║                                                          ║"
echo "║  Atau klik tanda (X) 'EXIT' di bar Notifikasi Termux.    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
