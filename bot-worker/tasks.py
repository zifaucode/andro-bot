"""
tasks.py — Task definitions untuk BOT-ANDRO.
Menggunakan 'device' sebagai pengganti 'emulator'.
"""

import logging
import time

import device
import capture
import folder_manager

logger = logging.getLogger(__name__)


def _log(txn: str, msg: str) -> None:
    logger.info(f"[{txn}] {msg}")
    folder_manager.write_log(txn, msg)


def _shot(txn: str, step: str) -> str:
    path = capture.capture_screen(txn, step)
    _log(txn, f"Screenshot saved: {path}")
    return path


# ── Built-in task: standby ───────────────────────────────────────────────────

def task_standby(transaction_id: str, params: dict) -> None:
    """Kembali ke state standby / home screen."""
    _log(transaction_id, "Returning to standby...")
    device.press_home()
    time.sleep(1)
    _shot(transaction_id, "standby_final")
    _log(transaction_id, "Standby complete.")


# ── Task: open_app ───────────────────────────────────────────────────────────

def task_open_app(transaction_id: str, params: dict) -> None:
    """
    Buka app dan ambil screenshot.
    Required params: package (str), activity (str, optional)
    """
    package = params.get("package")
    if not package:
        raise ValueError("task_open_app requires 'package' in params")

    activity = params.get("activity", "")
    _log(transaction_id, f"Launching app: {package}")
    device.launch_app(package, activity)
    time.sleep(3)
    _shot(transaction_id, "app_opened")
    _log(transaction_id, "task_open_app complete")


# ── Task: tap_sequence ───────────────────────────────────────────────────────

def task_tap_sequence(transaction_id: str, params: dict) -> None:
    """
    Eksekusi urutan tap.
    Required params: steps (list of {x, y, label?}), capture_each (bool, optional)
    """
    steps = params.get("steps", [])
    capture_each = params.get("capture_each", False)

    if not steps:
        raise ValueError("task_tap_sequence requires 'steps' list in params")

    for i, step in enumerate(steps):
        x, y = int(step["x"]), int(step["y"])
        label = step.get("label", f"step_{i+1}")
        _log(transaction_id, f"Tap [{label}] at ({x}, {y})")
        device.tap(x, y)
        if capture_each:
            _shot(transaction_id, f"after_tap_{label}")

    _shot(transaction_id, "tap_sequence_done")
    _log(transaction_id, "task_tap_sequence complete")


# ── Task registry ─────────────────────────────────────────────────────────────

TASK_REGISTRY: dict = {
    "standby": task_standby,
    "open_app": task_open_app,
    "tap_sequence": task_tap_sequence,
}
