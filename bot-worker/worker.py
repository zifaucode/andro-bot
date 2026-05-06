"""
worker.py — BOT-ANDRO Worker main entry point.

Berjalan di Termux (Android).
Dipanggil oleh FastAPI bot_trigger.py sebagai subprocess:
    python worker.py --transaction_id TXN001 --task_type topup --params '{...}'

Perbedaan dari BOT-EMU:
  - Tidak ada launch_emulator() — tidak butuh ldconsole
  - connect_device() dipanggil saat startup untuk memastikan ADB ke diri sendiri
  - Import 'device' bukan 'emulator'
"""

import argparse
import json
import logging
import sys
import threading
import time

import folder_manager
import macro_runner
import device
from config import settings


# ── Built-in fallback tasks ──────────────────────────────────────────────────

def _builtin_standby(transaction_id: str, params: dict) -> None:
    """Fallback standby jika macros/standby.json tidak ada."""
    import capture
    folder_manager.write_log(transaction_id, "Standby: tekan Home")
    device.press_home()
    import time
    time.sleep(1)
    capture.capture_screen(transaction_id, "standby_home")
    folder_manager.write_log(transaction_id, "Standby selesai.")


BUILTIN_TASKS: dict = {
    "standby": _builtin_standby,
}


# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging(transaction_id: str) -> None:
    log_file = str(folder_manager.get_logs_dir(transaction_id) / "run.log")
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=handlers,
        force=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="BOT-ANDRO Worker")
    parser.add_argument("--transaction_id", required=True)
    parser.add_argument("--task_type", required=True)
    parser.add_argument("--params", default="{}")
    args = parser.parse_args()

    transaction_id = args.transaction_id
    task_type = args.task_type

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] --params JSON tidak valid: {exc}", file=sys.stderr)
        return 1

    # Pastikan folder transaksi ada
    folder_manager.get_transaction_dir(transaction_id)
    setup_logging(transaction_id)
    logger = logging.getLogger("worker")

    logger.info("=" * 50)
    logger.info(f"BOT-ANDRO Worker")
    logger.info(f"Transaction  : {transaction_id}")
    logger.info(f"Task type    : {task_type}")
    logger.info(f"Params       : {params}")
    logger.info(f"Device serial: {settings.DEVICE_SERIAL}")
    logger.info(f"Macros dir   : {macro_runner.MACROS_DIR}")
    logger.info(f"Macros tersedia: {macro_runner.list_macros()}")
    logger.info("=" * 50)

    # ── Pastikan ADB terkoneksi ke device lokal ──────────────────────────────
    logger.info(f"Menghubungkan ADB ke {settings.DEVICE_SERIAL}...")
    connected = device.connect_device()
    if not connected:
        logger.error(f"Gagal koneksi ADB ke {settings.DEVICE_SERIAL}!")
        logger.error("Pastikan Wireless Debugging sudah aktif di Developer Options.")
        folder_manager.write_log(transaction_id, f"ERROR: ADB tidak terkoneksi ke {settings.DEVICE_SERIAL}")
        return 1

    logger.info("Menunggu device siap...")
    if not device.wait_for_device(timeout=15):
        logger.error("Device tidak siap setelah menunggu")
        folder_manager.write_log(transaction_id, "ERROR: Device tidak siap")
        return 1

    logger.info("Verifikasi ADB health...")
    if not device.check_adb_health():
        logger.error("ADB health check gagal — device tidak responsif")
        folder_manager.write_log(transaction_id, "ERROR: ADB health check gagal")
        return 1

    # ── Start ADB keepalive ─────────────────────────────────────────────────
    keepalive_stop = threading.Event()
    keepalive_thread = _start_adb_keepalive(keepalive_stop, logger)

    exit_code = 1
    try:
        # ── Lookup: cek macro JSON dulu ──────────────────────────────────────
        if macro_runner.macro_exists(task_type):
            logger.info(f"Menjalankan macro JSON: '{task_type}'")
            try:
                macro_runner.run_macro(task_type, transaction_id, params)
                exit_code = 0
            except macro_runner.MacroAbortError as exc:
                logger.warning(f"Macro '{task_type}' aborted: {exc}")
                folder_manager.write_log(transaction_id, f"ABORT: {exc}")
                exit_code = 2
            except Exception as exc:
                logger.exception(f"Macro '{task_type}' error: {exc}")
                folder_manager.write_log(transaction_id, f"ERROR: {exc}")
                _run_standby(transaction_id, logger)
                exit_code = 1

        # ── Lookup: cek built-in Python task ────────────────────────────────
        elif task_type in BUILTIN_TASKS:
            logger.info(f"Menjalankan built-in task: '{task_type}'")
            try:
                BUILTIN_TASKS[task_type](transaction_id, params)
                exit_code = 0
            except Exception as exc:
                logger.exception(f"Built-in task '{task_type}' error: {exc}")
                folder_manager.write_log(transaction_id, f"ERROR: {exc}")
                _run_standby(transaction_id, logger)
                exit_code = 1

        # ── Tidak ditemukan ──────────────────────────────────────────────────
        else:
            available_macros = macro_runner.list_macros()
            available_builtins = list(BUILTIN_TASKS.keys())
            msg = (
                f"Task '{task_type}' tidak ditemukan.\n"
                f"  Macros tersedia  : {available_macros}\n"
                f"  Built-in tersedia: {available_builtins}\n"
                f"  Tambah macro baru: buat file macros/{task_type}.json"
            )
            logger.error(msg)
            folder_manager.write_log(transaction_id, f"ERROR: {msg}")
            exit_code = 1
    finally:
        keepalive_stop.set()
        keepalive_thread.join(timeout=2)

    logger.info(f"=== Worker selesai: {transaction_id} ===")
    return exit_code


def _run_standby(transaction_id: str, logger: logging.Logger) -> None:
    """Jalankan standby setelah task selesai."""
    try:
        if macro_runner.macro_exists("standby"):
            macro_runner.run_macro("standby", transaction_id, {})
        elif "standby" in BUILTIN_TASKS:
            BUILTIN_TASKS["standby"](transaction_id, {})
    except Exception as e:
        logger.warning(f"Standby gagal: {e}")


def _start_adb_keepalive(stop_event: threading.Event, logger: logging.Logger) -> threading.Thread:
    """Background thread: ping ADB setiap 30 detik agar koneksi tidak idle-timeout."""
    def _ping():
        while not stop_event.is_set():
            stop_event.wait(30)
            if stop_event.is_set():
                break
            if not device.check_adb_health():
                logger.warning("ADB keepalive: health check gagal, mencoba reconnect...")
                device.connect_device()
    t = threading.Thread(target=_ping, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    sys.exit(main())
