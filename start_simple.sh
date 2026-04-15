#!/data/data/com.termux/files/usr/bin/bash
# start_simple.sh — Jalankan worker bot (untuk trigger via web API)
# Script ini dipanggil oleh FastAPI untuk menjalankan bot worker di background.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$SCRIPT_DIR/bot-worker"
LOG_DIR="$SCRIPT_DIR/logs"

# Buat folder log/output jika belum ada
mkdir -p "$LOG_DIR"
mkdir -p "$WORKER_DIR/output"

# Pastikan ADB status
ADB_DEV=$(adb devices | grep -v "List" | grep "device" || true)
if [ -z "$ADB_DEV" ]; then
    echo "[!] Tidak ada ADB device yang terdeteksi!" >> "$LOG_DIR/worker.log"
    # Lanjutkan saja, mungkin config manual atau nunggu di-connect ulang via setup
fi

# Matikan bot worker lama jika ada
pkill -f "worker.py" 2>/dev/null || true
sleep 1

# Jalankan bot worker dan simpan log
cd "$WORKER_DIR"
nohup python worker.py >> "$LOG_DIR/worker.log" 2>&1 &
WORKER_PID=$!

echo $WORKER_PID > "$LOG_DIR/worker.pid"
echo "[OK] Bot Worker berjalan (PID: $WORKER_PID)" >> "$LOG_DIR/worker.log"
