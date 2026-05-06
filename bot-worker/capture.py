"""
capture.py — Screen capture utilities tied to transaction folders. (BOT-ANDRO)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import device
from folder_manager import get_screenshots_dir
from config import settings

logger = logging.getLogger(__name__)


def capture_screen(
    transaction_id: str,
    step_name: str,
    label: Optional[str] = None,
) -> str:
    """
    Ambil screenshot device dan simpan ke folder screenshots transaksi.

    Args:
        transaction_id: ID unik transaksi
        step_name: Nama step (digunakan sebagai bagian nama file)
        label: Label extra opsional

    Returns:
        Path absolut file screenshot yang tersimpan
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_step = step_name.replace(" ", "_").replace("/", "-")
    suffix = f"_{label}" if label else ""
    filename = f"{timestamp}_{safe_step}{suffix}.{settings.SCREENSHOT_FORMAT}"

    save_dir = get_screenshots_dir(transaction_id)
    save_path = str(save_dir / filename)

    result = device.get_screenshot(save_path=save_path)
    if result is None:
        logger.error(f"[{transaction_id}] Screenshot GAGAL: {filename}")
        folder_manager.write_log(transaction_id, f"ERROR: Screenshot gagal: {filename}")
    else:
        logger.info(f"[{transaction_id}] Screenshot captured: {filename}")
    return save_path
