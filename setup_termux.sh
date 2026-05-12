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

# ─── Termux User Repository (TUR) Index ─────────────────────────
# Menyediakan pre-built wheels untuk library Python yang sulit
# di-compile di Termux (pydantic-core, dll).
TUR_INDEX="https://termux-user-repository.github.io/pypi/"

# ─── 0. Mencegah Android Sleep ──────────────────────────────────
echo "[0/7] Mengaktifkan Termux Wake-Lock (Agar jalan di background)..."
termux-wake-lock

# ─── 1. Update package list ─────────────────────────────────────
echo "[1/7] Update & upgrade packages Termux..."
pkg update -y && pkg upgrade -y

# ─── 2. Install dependencies system ─────────────────────────────
echo ""
echo "[2/7] Install dependencies sistem Android (Python, Git, ADB, dll)..."
# clang, make, binutils      → dibutuhkan untuk compile library Python (fallback)
# libffi, openssl             → dibutuhkan oleh beberapa library (cryptography, dll)
# rust                        → dibutuhkan oleh pydantic-core jika TUR gagal
# proot, resolv-conf          → jaringan & kompatibilitas
pkg install -y \
    python \
    git \
    android-tools \
    wget \
    clang \
    make \
    binutils \
    proot \
    resolv-conf \
    libffi \
    openssl \
    rust

# ─── 3. Upgrade pip & setuptools ────────────────────────────────
echo ""
echo "[3/7] Menyiapkan pip & build tools..."
python -m ensurepip --upgrade 2>/dev/null || true
pip install --upgrade pip setuptools wheel 2>/dev/null || true

# ─── 4. Install Python dependencies ─────────────────────────────
echo ""
echo "[4/7] Install library dependencies Python..."

# --- 4a. Install pydantic-core terlebih dahulu dari TUR ----------
# pydantic-core ditulis dalam Rust dan TIDAK tersedia sebagai
# pre-built wheel di PyPI untuk Android/Termux.
# TUR menyediakan wheel yang sudah di-compile untuk aarch64/arm.
echo "    > [1/6] Menginstall pydantic-core dari Termux User Repository..."
echo "    ⏳ Menggunakan pre-built wheel dari TUR (lebih cepat & stabil)..."
if pip install --extra-index-url "$TUR_INDEX" pydantic-core; then
    echo "    ✅ pydantic-core berhasil diinstall dari TUR"
else
    echo "    ⚠️  TUR gagal, mencoba fallback compile dari source..."
    echo "    ⏳ Ini akan memakan waktu lama, mohon ditunggu..."
    CARGO_BUILD_TARGET="" pip install pydantic-core --no-binary :none: || {
        echo ""
        echo "    ❌ GAGAL install pydantic-core!"
        echo "    Coba jalankan manual:"
        echo "      pip install --extra-index-url $TUR_INDEX pydantic-core"
        echo ""
        exit 1
    }
fi

# --- 4b. Install pydantic ----------------------------------------
echo "    > [2/6] Menginstall pydantic..."
pip install pydantic

# --- 4c. Install requests ----------------------------------------
echo "    > [3/6] Menginstall requests (Digunakan untuk menembak API)..."
pip install requests

# --- 4d. Install python-dotenv ------------------------------------
echo "    > [4/6] Menginstall python-dotenv (Digunakan untuk membaca konfigurasi .env)..."
pip install python-dotenv

# --- 4e. Install uvicorn -----------------------------------------
echo "    > [5/6] Menginstall uvicorn (Digunakan untuk server web aplikasi)..."
pip install uvicorn

# --- 4f. Install fastapi & python-multipart -----------------------
echo "    > [6/6] Menginstall fastapi & python-multipart (Arsitektur API Bot)..."
pip install fastapi python-multipart

# ─── 5. Verifikasi instalasi Python ─────────────────────────────
echo ""
echo "[5/7] Verifikasi instalasi Python..."

VERIFY_FAILED=0
for pkg_name in fastapi uvicorn pydantic requests dotenv; do
    MOD_NAME="$pkg_name"
    # python-dotenv diimport sebagai 'dotenv'
    if [ "$pkg_name" = "dotenv" ]; then
        MOD_NAME="dotenv"
    fi
    if python -c "import $MOD_NAME" 2>/dev/null; then
        echo "    ✅ $pkg_name OK"
    else
        echo "    ❌ $pkg_name GAGAL diimport!"
        VERIFY_FAILED=1
    fi
done

if [ "$VERIFY_FAILED" -eq 1 ]; then
    echo ""
    echo "    ⚠️  Beberapa library gagal diinstall."
    echo "    Coba jalankan ulang: bash setup_termux.sh"
    echo "    Atau install manual: pip install --extra-index-url $TUR_INDEX <nama-library>"
fi

# ─── 6. Install Cloudflared ─────────────────────────────────────
echo ""
echo "[6/7] Install cloudflared (Cloudflare Quick Tunnel)..."

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

# ─── 7. Setup konfigurasi & folder ──────────────────────────────
echo ""
echo "[7/7] Membuat file .env & folder yang diperlukan..."

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

# Buat folder output & logs
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
