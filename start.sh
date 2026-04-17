#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# start.sh — Script startup BOT-ANDRO
# Jalankan dengan: bash start.sh
# ================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASTAPI_DIR="$SCRIPT_DIR/fastapi-server"
TUNNEL_URL_FILE="$FASTAPI_DIR/tunnel_url.txt"
LOG_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOG_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          BOT-ANDRO Startup               ║"
echo "║   Android Device sebagai Server BOT      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ─── Step 1: Hubungkan ADB ke diri sendiri ──────────────────────
echo "[1/3] Menghubungkan ADB ke device lokal..."

# Coba port default 5555 dulu
if adb connect 127.0.0.1:5555 2>&1 | grep -q "connected"; then
    echo "    ✅ ADB terkoneksi ke 127.0.0.1:5555"
    ADB_SERIAL="127.0.0.1:5555"
else
    echo "    ⚠️  Port 5555 gagal, coba deteksi port otomatis..."
    # Android 11+ Wireless Debugging pakai port random
    # Coba baca dari /proc/net/tcp (port yang listening)
    echo "    → Pastikan Wireless Debugging aktif di Developer Options"
    echo "    → Masukkan port ADB secara manual:"
    read -p "      Port ADB (default: 5555): " ADB_PORT
    ADB_PORT="${ADB_PORT:-5555}"
    adb connect "127.0.0.1:$ADB_PORT"
    ADB_SERIAL="127.0.0.1:$ADB_PORT"
fi

# Update .env bot-worker dengan serial yang berhasil
sed -i "s/^DEVICE_SERIAL=.*/DEVICE_SERIAL=$ADB_SERIAL/" "$SCRIPT_DIR/bot-worker/.env" 2>/dev/null || true

echo ""
echo "[2/3] Menjalankan FastAPI Server di background..."
cd "$FASTAPI_DIR"

# Matikan proses FastAPI lama jika ada
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 1

# Jalankan FastAPI di background
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 \
    > "$LOG_DIR/fastapi.log" 2>&1 &
FASTAPI_PID=$!
echo "    ✅ FastAPI berjalan (PID: $FASTAPI_PID)"
echo "    📋 Log: $LOG_DIR/fastapi.log"

# Tunggu FastAPI siap
sleep 2

echo ""
echo "[3/3] Menjalankan Cloudflare Quick Tunnel..."
echo "    (URL akan berubah setiap restart — ini normal untuk Quick Tunnel)"
echo ""

# Matikan tunnel lama
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1

# Jalankan cloudflared dan capture URL
# Simpan output ke file sementara untuk parse URL
CLOUDFLARED_LOG="$LOG_DIR/cloudflare.log"

nohup cloudflared tunnel --url http://localhost:8000 \
    --no-autoupdate \
    > "$CLOUDFLARED_LOG" 2>&1 &
CLOUDFLARE_PID=$!

echo "    ⏳ Menunggu Cloudflare URL..."

# Tunggu URL muncul di log (max 30 detik)
for i in $(seq 1 30); do
    TUNNEL_URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' "$CLOUDFLARED_LOG" 2>/dev/null | grep -v 'api.trycloudflare.com' | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        # Simpan URL ke file agar FastAPI bisa membacanya
        echo "$TUNNEL_URL" > "$TUNNEL_URL_FILE"
        echo ""
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║  ✅ BOT-ANDRO SIAP!                                          ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║  🌐 URL Publik (Cloudflare):                                 ║"
        echo "║  $TUNNEL_URL"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║  📡 URL Lokal   : http://localhost:8000                      ║"
        echo "║  📊 Dashboard   : $TUNNEL_URL/dashboard"
        echo "║  📖 API Docs    : $TUNNEL_URL/docs"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║  ⚠️  Simpan URL di atas ke config Laravel Anda!              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo ""
        break
    fi
    sleep 1
    echo -n "."
done

if [ -z "$TUNNEL_URL" ]; then
    echo ""
    echo "    ⚠️  URL belum terdeteksi otomatis. Cek log:"
    echo "    cat $CLOUDFLARED_LOG"
fi

echo ""
echo "PID summary:"
echo "  FastAPI    : $FASTAPI_PID"
echo "  Cloudflare : $CLOUDFLARE_PID"
echo ""
echo "Untuk stop semua: bash stop.sh"
echo "Untuk lihat log FastAPI: tail -f $LOG_DIR/fastapi.log"

# Simpan PID untuk stop.sh
echo "$FASTAPI_PID" > "$LOG_DIR/fastapi.pid"
echo "$CLOUDFLARE_PID" > "$LOG_DIR/cloudflare.pid"
