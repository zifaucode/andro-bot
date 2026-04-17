#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# setup_termux.sh — One-time setup BOT-ANDRO di Termux
#
# Cara penggunaan:
#   1. Install Termux dari F-Droid (BUKAN dari Play Store)
#   2. Copy folder BOT-ANDRO ke HP (via USB / git clone / Termux)
#   3. Di Termux jalankan:
#        bash setup_termux.sh
# ================================================================

set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     BOT-ANDRO — Setup Termux             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── 0. Mencegah Android Sleep ──────────────────────────────────
echo "[0/6] Mengaktifkan Termux Wake-Lock (Agar jalan di background)..."
termux-wake-lock

# ─── 1. Update package list ─────────────────────────────────────
echo "[1/6] Update & upgrade packages Termux..."
pkg update -y && pkg upgrade -y

# ─── 2. Install dependencies system ─────────────────────────────
echo ""
echo "[2/6] Install dependencies sistem Android (Python, Git, ADB, Wget)..."
# Ditambahkan clang make binutils karena terkadang instalasi library python butuh dicompile di Termux
pkg install -y python git android-tools wget clang make binutils

# ─── 3. Install Python dependencies ─────────────────────────────
echo ""
echo "[3/6] Install library dependencies Python..."

echo "    > [1/5] Menyiapkan pip (Package Manager)..."
# Termux melarang `pip install --upgrade pip`, jadi kita skip langkah upgrade
python -m ensurepip --upgrade || true

echo "    > [2/5] Menginstall requests (Digunakan untuk menembak API)..."
pip install requests

echo "    > [3/5] Menginstall python-dotenv (Digunakan untuk membaca konfigurasi .env)..."
pip install python-dotenv

echo "    > [4/5] Menginstall uvicorn (Digunakan untuk server web aplikasi)..."
pip install uvicorn

echo "    > [5/5] Menginstall fastapi & python-multipart (Digunakan untuk arsitektur API Bot)..."
echo "    ⏳ PENTING: Proses instalasi FastAPI biasanya memakan waktu agak lama karena kompilasi 'pydantic'. Jangan ditutup, mohon ditunggu..."
pip install fastapi python-multipart

# ─── 4. Install Cloudflared ─────────────────────────────────────
echo ""
echo "[4/6] Install cloudflared (Cloudflare Quick Tunnel)..."

# Deteksi arsitektur
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    CF_ARCH="arm64"
elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv7" ]; then
    CF_ARCH="arm"
else
    echo "    ⚠️  Arsitektur tidak dikenal: $ARCH (coba arm64)"
    CF_ARCH="arm64"
fi

echo "    Arsitektur terdeteksi: $ARCH → cloudflared-linux-$CF_ARCH"

CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$CF_ARCH"
wget -q --show-progress "$CF_URL" -O "$PREFIX/bin/cloudflared"
chmod +x "$PREFIX/bin/cloudflared"

# Verifikasi
CLOUDFLARED_VERSION=$(cloudflared --version 2>&1 | head -1)
echo "    ✅ $CLOUDFLARED_VERSION"

# ─── 5. Buat file .env dari .env.example ────────────────────────
echo ""
echo "[5/6] Membuat file .env..."

# Bot worker .env
WORKER_ENV="$SCRIPT_DIR/bot-worker/.env"
if [ ! -f "$WORKER_ENV" ]; then
    cp "$SCRIPT_DIR/bot-worker/.env.example" "$WORKER_ENV"
    # Update OUTPUT_BASE_DIR ke path aktual
    sed -i "s|OUTPUT_BASE_DIR=.*|OUTPUT_BASE_DIR=$SCRIPT_DIR/bot-worker/output|" "$WORKER_ENV"
    echo "    ✅ $WORKER_ENV dibuat"
else
    echo "    ℹ️  $WORKER_ENV sudah ada, tidak ditimpa"
fi

# FastAPI .env
FASTAPI_ENV="$SCRIPT_DIR/fastapi-server/.env"
if [ ! -f "$FASTAPI_ENV" ]; then
    cp "$SCRIPT_DIR/fastapi-server/.env.example" "$FASTAPI_ENV"
    # Update BOT_WORKER_PATH ke path aktual
    sed -i "s|BOT_WORKER_PATH=.*|BOT_WORKER_PATH=$SCRIPT_DIR/bot-worker/worker.py|" "$FASTAPI_ENV"
    sed -i "s|JOB_STATUS_PATH=.*|JOB_STATUS_PATH=$SCRIPT_DIR/fastapi-server/job_status.json|" "$FASTAPI_ENV"
    echo "    ✅ $FASTAPI_ENV dibuat"
else
    echo "    ℹ️  $FASTAPI_ENV sudah ada, tidak ditimpa"
fi

# ─── 6. Buat folder yang diperlukan ─────────────────────────────
echo ""
echo "[6/6] Membuat folder output & logs..."
mkdir -p "$SCRIPT_DIR/bot-worker/output"
mkdir -p "$SCRIPT_DIR/fastapi-server"
mkdir -p "$SCRIPT_DIR/logs"

# Beri izin eksekusi ke script
chmod +x "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/stop.sh"

# ─── Selesai ─────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup selesai!                                            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Langkah selanjutnya:                                         ║"
echo "║                                                               ║"
echo "║  1. Aktifkan Wireless Debugging di HP:                        ║"
echo "║     Settings → Developer Options → Wireless Debugging → ON   ║"
echo "║                                                               ║"
echo "║  2. Edit API key di fastapi-server/.env:                      ║"
echo "║     nano $SCRIPT_DIR/fastapi-server/.env"
echo "║                                                               ║"
echo "║  3. Jalankan bot:                                             ║"
echo "║     bash $SCRIPT_DIR/start.sh"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

echo "⚠️  PENTING: Backup API key yang Anda set di .env!"
echo "   File .env kamu ada di: $SCRIPT_DIR/fastapi-server/.env"
