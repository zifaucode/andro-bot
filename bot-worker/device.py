"""
device.py — ADB wrapper untuk device Android fisik (berjalan di Termux).

Berbeda dengan emulator.py (BOT-EMU):
  - Tidak ada launch_emulator() / ldconsole
  - ADB binary dari android-tools Termux (command: 'adb')
  - Target adalah diri sendiri via ADB over WiFi (127.0.0.1:ADB_PORT)
  - Screenshot disimpan ke storage lokal Termux (bukan pull dari Windows)

CARA KERJA:
  Bot Worker berjalan di Termux (Android).
  Termux memanggil 'adb -s 127.0.0.1:PORT shell input tap x y'
  untuk mengontrol layar HP itu sendiri.

CATATAN ANDROID 10+:
  Tanpa root, ADB over WiFi perlu diaktifkan dulu:
  - Android 10 : sambung USB sekali, jalankan 'adb tcpip 5555' dari PC,
                  atau aktifkan 'ADB over network' di Developer Options (beberapa ROM).
  - Android 11+: Settings → Developer Options → Wireless Debugging → aktifkan.

  Setelah aktif, dari Termux:
    adb connect 127.0.0.1:<PORT>
    adb devices   ← harus muncul '127.0.0.1:<PORT>  device'
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


# ── ADB core ────────────────────────────────────────────────────────────────

def _adb(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Jalankan command ADB ke device lokal (diri sendiri)."""
    cmd = [settings.ADB_PATH, "-s", settings.DEVICE_SERIAL, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        logger.error(f"ADB Error ({' '.join(args)}): {proc.stderr.strip()}")
    return proc


def connect_device() -> bool:
    """
    Hubungkan ADB ke device lokal (127.0.0.1:PORT).
    Dipanggil saat startup bot worker.
    Aman dipanggil berkali-kali (idempotent).
    """
    serial = settings.DEVICE_SERIAL
    logger.info(f"Menghubungkan ADB ke {serial}...")
    try:
        result = subprocess.run(
            [settings.ADB_PATH, "connect", serial],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout.strip()
        logger.info(f"ADB connect: {output}")

        # Verifikasi koneksi
        devices_result = subprocess.run(
            [settings.ADB_PATH, "devices"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if serial in devices_result.stdout and "device" in devices_result.stdout:
            logger.info(f"✅ Device {serial} terkoneksi")
            return True
        else:
            logger.error(f"❌ Device {serial} tidak terdeteksi!\n{devices_result.stdout}")
            return False
    except Exception as exc:
        logger.error(f"Gagal connect ADB: {exc}")
        return False


def wait_for_device(timeout: int = 30) -> bool:
    """Tunggu device siap (untuk antisipasi ADB baru reconnect)."""
    try:
        subprocess.run(
            [settings.ADB_PATH, "-s", settings.DEVICE_SERIAL, "wait-for-device"],
            capture_output=True,
            timeout=timeout,
        )
        return True
    except subprocess.TimeoutExpired:
        logger.error("Timeout menunggu device ADB siap")
        return False


# ── Screen interaction ───────────────────────────────────────────────────────

def tap(x: int, y: int) -> None:
    """Tap koordinat (x, y) di layar."""
    _adb("shell", "input", "tap", str(x), str(y))
    time.sleep(settings.ACTION_DELAY)


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500) -> None:
    """Swipe dari (x1,y1) ke (x2,y2) dalam duration_ms milidetik."""
    _adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
    time.sleep(settings.ACTION_DELAY)


def input_text(text: str) -> None:
    """Ketik teks ke field yang sedang difokus."""
    # Escape karakter khusus untuk ADB shell
    safe = text.replace("\\", "\\\\").replace(" ", "%s").replace("'", "\\'").replace('"', '\\"').replace("&", "\\&").replace(";", "\\;").replace("<", "\\<").replace(">", "\\>").replace("|", "\\|")
    _adb("shell", "input", "text", safe)
    time.sleep(settings.ACTION_DELAY)


def press_key(keycode: int) -> None:
    """Tekan keycode Android (4=BACK, 3=HOME, 66=ENTER, dll)."""
    _adb("shell", "input", "keyevent", str(keycode))
    time.sleep(settings.ACTION_DELAY)


def press_back() -> None:
    press_key(4)


def press_home() -> None:
    press_key(3)


# ── Screen capture ───────────────────────────────────────────────────────────

def get_screenshot(save_path: Optional[str] = None) -> Optional[bytes]:
    """
    Ambil screenshot device.
    Karena berjalan di Termux (device itu sendiri), tidak perlu 'adb pull' dari PC.
    Screenshot disimpan ke /sdcard/ lalu dibaca langsung sebagai bytes.

    Args:
        save_path: Path lengkap untuk menyimpan file PNG (opsional).
                   Jika None, hanya return bytes tanpa simpan permanen.
    Returns:
        bytes PNG jika berhasil, None jika gagal.
    """
    sdcard_tmp = "/sdcard/bot_screen_temp.png"

    # 1. Ambil screenshot ke sdcard
    _adb("shell", "screencap", "-p", sdcard_tmp)
    time.sleep(0.3)  # beri waktu screencap selesai

    if save_path:
        # 2a. Jika diminta simpan ke path tertentu — pull ke Termux
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        _adb("pull", sdcard_tmp, save_path)
        _adb("shell", "rm", sdcard_tmp)
        logger.info(f"Screenshot saved: {save_path}")
        try:
            return Path(save_path).read_bytes()
        except Exception as exc:
            logger.error(f"Gagal baca screenshot: {exc}")
            return None
    else:
        # 2b. Hanya butuh bytes (untuk check_screen) — pull ke file temp Termux
        temp_path = str(Path(settings.OUTPUT_BASE_DIR).parent / "_temp_screen.png")
        Path(temp_path).parent.mkdir(parents=True, exist_ok=True)
        _adb("pull", sdcard_tmp, temp_path)
        _adb("shell", "rm", sdcard_tmp)
        try:
            data = Path(temp_path).read_bytes()
            Path(temp_path).unlink(missing_ok=True)
            return data
        except Exception as exc:
            logger.error(f"Gagal baca screenshot sementara: {exc}")
            return None


# ── App control ──────────────────────────────────────────────────────────────

def launch_app(package: str, activity: str = "") -> None:
    """Buka app Android berdasarkan package name."""
    if activity:
        _adb("shell", "am", "start", "-n", f"{package}/{activity}")
    else:
        _adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(3)


def stop_app(package: str) -> None:
    """Force-stop sebuah app."""
    _adb("shell", "am", "force-stop", package)
    time.sleep(1)
