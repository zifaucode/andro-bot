"""
config.py — FastAPI Server Configuration (BOT-ANDRO / Termux)
"""

import os
from dotenv import load_dotenv

load_dotenv()

_TERMUX_HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
_PROJECT_DIR = os.path.join(_TERMUX_HOME, "BOT-ANDRO")


class Settings:
    # API Authentication
    API_KEY: str = os.getenv("API_KEY", "change_me")

    # Cloudflare Quick Tunnel URL — diupdate otomatis saat start
    # Karena Quick Tunnel URL berubah setiap restart, simpan di file
    CLOUDFLARE_URL: str = os.getenv("CLOUDFLARE_URL", "http://localhost:8000")

    # BOT Worker Path (Linux path di Termux)
    BOT_WORKER_PATH: str = os.getenv(
        "BOT_WORKER_PATH",
        os.path.join(_PROJECT_DIR, "bot-worker", "worker.py"),
    )
    PYTHON_EXE: str = os.getenv("PYTHON_EXE", "python")

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    ]

    # Job status persistence
    JOB_STATUS_PATH: str = os.getenv(
        "JOB_STATUS_PATH",
        os.path.join(_PROJECT_DIR, "fastapi-server", "job_status.json"),
    )

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Dashboard Authentication
    DASHBOARD_USER: str = os.getenv("DASHBOARD_USER", "admin")
    DASHBOARD_PASS: str = os.getenv("DASHBOARD_PASS", "admin123")

    # File penyimpan URL tunnel aktif (dibaca oleh dashboard)
    TUNNEL_URL_FILE: str = os.path.join(_PROJECT_DIR, "fastapi-server", "tunnel_url.txt")


settings = Settings()
