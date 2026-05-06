"""
config.py — BOT Worker Configuration (BOT-ANDRO / Termux)

Semua path menggunakan format Linux (Termux di Android).
Path default Termux: /data/data/com.termux/files/home/
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Deteksi home Termux secara otomatis
_TERMUX_HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
_PROJECT_DIR = os.path.join(_TERMUX_HOME, "BOT-ANDRO")


class WorkerSettings:
    # ADB — gunakan 'adb' dari package android-tools Termux
    ADB_PATH: str = os.getenv("ADB_PATH", "adb")

    # Serial device lokal — ADB over WiFi ke diri sendiri
    # Android 10 : biasanya 127.0.0.1:5555
    # Android 11+: cek port di Settings → Wireless Debugging
    DEVICE_SERIAL: str = os.getenv("DEVICE_SERIAL", "127.0.0.1:5555")

    # Output — simpan ke storage Termux
    OUTPUT_BASE_DIR: str = os.getenv(
        "OUTPUT_BASE_DIR",
        os.path.join(_PROJECT_DIR, "bot-worker", "output"),
    )
    SCREENSHOT_FORMAT: str = os.getenv("SCREENSHOT_FORMAT", "png")

    # Timing
    TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "300"))
    ACTION_DELAY: float = float(os.getenv("ACTION_DELAY", "1.0"))

    # Target Server (untuk update URL / store data ke website tujuan)
    DEVICE_ID: str = os.getenv("DEVICE_ID", "")
    TARGET_SERVER_URL: str = os.getenv("TARGET_SERVER_URL", "")
    TARGET_API_SECRET: str = os.getenv("TARGET_API_SECRET", "")


settings = WorkerSettings()
