"""
folder_manager.py — Transaction-based folder management. (BOT-ANDRO)
Path default: ~/BOT-ANDRO/bot-worker/output/

Struktur per transaksi:
  output/
  └── {transaction_id}/
      ├── screenshots/   ← PERMANENT, tidak pernah dihapus
      └── logs/
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


def get_transaction_dir(transaction_id: str) -> Path:
    """Return (dan buat jika belum ada) root folder untuk transaksi."""
    base = Path(settings.OUTPUT_BASE_DIR) / transaction_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_screenshots_dir(transaction_id: str) -> Path:
    """Return (dan buat jika belum ada) folder screenshots. TIDAK pernah dihapus."""
    d = get_transaction_dir(transaction_id) / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_logs_dir(transaction_id: str) -> Path:
    """Return (dan buat jika belum ada) folder logs."""
    d = get_transaction_dir(transaction_id) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_log(transaction_id: str, content: str) -> Path:
    """Append log ke file logs/run.log milik transaksi."""
    log_file = get_logs_dir(transaction_id) / "run.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {content}\n")
    return log_file


def cleanup_old_logs(days: int = 30) -> None:
    """
    Hapus hanya FILE LOG lama (bukan folder, bukan screenshots).
    Screenshots TIDAK pernah disentuh.
    """
    base = Path(settings.OUTPUT_BASE_DIR)
    if not base.exists():
        return

    cutoff = datetime.now() - timedelta(days=days)
    deleted_logs = 0

    for txn_folder in base.iterdir():
        if not txn_folder.is_dir():
            continue
        logs_dir = txn_folder / "logs"
        if not logs_dir.exists():
            continue
        for log_file in logs_dir.glob("*.log"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff:
                    log_file.unlink()
                    deleted_logs += 1
            except Exception as exc:
                logger.warning(f"Gagal hapus log {log_file}: {exc}")

    logger.info(f"Cleanup: {deleted_logs} log file dihapus (>{days} hari)")


def list_transactions() -> list[dict]:
    """List semua folder transaksi beserta info screenshot."""
    base = Path(settings.OUTPUT_BASE_DIR)
    if not base.exists():
        return []

    result = []
    for txn_folder in sorted(base.iterdir(), reverse=True):
        if not txn_folder.is_dir():
            continue
        screenshots = list((txn_folder / "screenshots").glob("*")) if (txn_folder / "screenshots").exists() else []
        result.append({
            "transaction_id": txn_folder.name,
            "path": str(txn_folder),
            "screenshot_count": len(screenshots),
            "screenshots": [str(s) for s in screenshots],
            "created_at": datetime.fromtimestamp(txn_folder.stat().st_ctime).isoformat(),
        })
    return result
