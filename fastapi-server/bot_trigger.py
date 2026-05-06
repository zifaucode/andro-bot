"""
bot_trigger.py — Spawn BOT Worker sebagai subprocess dan track job status.
(BOT-ANDRO — identik dengan BOT-EMU)
"""

import json
import subprocess
import threading
import queue
from datetime import datetime
from pathlib import Path

from config import settings

_lock = threading.Lock()


def _load_store() -> dict:
    path = Path(settings.JOB_STATUS_PATH)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_store(store: dict) -> None:
    path = Path(settings.JOB_STATUS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def _update_status(transaction_id: str, status: str, detail: str = "", extra: dict = None) -> None:
    with _lock:
        store = _load_store()
        if transaction_id not in store:
            store[transaction_id] = {}

        store[transaction_id]["status"] = status
        store[transaction_id]["detail"] = detail
        store[transaction_id]["updated_at"] = datetime.now().isoformat()

        if extra:
            store[transaction_id].update(extra)

        _save_store(store)


# ── Public API ───────────────────────────────────────────────────────────────

def get_status(transaction_id: str) -> dict:
    store = _load_store()
    return store.get(
        transaction_id,
        {"status": "not_found", "detail": "", "updated_at": ""},
    )


def clear_jobs() -> dict:
    with _lock:
        _save_store({})
    return {"success": True, "message": "All transaction records have been cleared."}


def delete_job(transaction_id: str) -> dict:
    with _lock:
        store = _load_store()
        if transaction_id in store:
            del store[transaction_id]
            _save_store(store)
            return {"success": True, "message": f"Transaction {transaction_id} deleted."}
        return {"success": False, "message": "Transaction not found."}


def trigger(transaction_id: str, task_type: str, params: dict) -> None:
    """Masukkan job ke antrian untuk dijalankan satu per satu."""
    _update_status(transaction_id, "queued", "Job queued", extra={
        "task_type": task_type,
        "id_player": params.get("id_player", ""),
        "amount": params.get("amount", "")
    })

    _job_queue.put({
        "transaction_id": transaction_id,
        "task_type": task_type,
        "params": params
    })


# ── Background Worker Queue ──────────────────────────────────────────────────

_job_queue = queue.Queue()


def _queue_worker() -> None:
    while True:
        job = _job_queue.get()
        if job is None:
            break
        transaction_id = job["transaction_id"]
        task_type = job["task_type"]
        params = job["params"]

        cmd = [
            settings.PYTHON_EXE,
            settings.BOT_WORKER_PATH,
            "--transaction_id", transaction_id,
            "--task_type", task_type,
            "--params", json.dumps(params),
        ]

        _update_status(transaction_id, "running", "Worker started")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=getattr(settings, 'TASK_TIMEOUT', 300),
            )
            if result.returncode == 0:
                _update_status(transaction_id, "done", result.stdout.strip()[-2000:])
            elif result.returncode == 2:
                _update_status(transaction_id, "failed", result.stdout.strip()[-2000:] or "Macro aborted")
            else:
                stderr_detail = result.stderr.strip() or result.stdout.strip()
                _update_status(transaction_id, "error", stderr_detail[-2000:] or "Worker error")
        except subprocess.TimeoutExpired:
            _update_status(transaction_id, "timeout", f"Worker exceeded {getattr(settings, 'TASK_TIMEOUT', 300)}s time limit")
        except Exception as exc:
            _update_status(transaction_id, "error", f"Exception: {exc}")
        finally:
            _job_queue.task_done()


_worker_thread = threading.Thread(target=_queue_worker, daemon=True)
_worker_thread.start()
