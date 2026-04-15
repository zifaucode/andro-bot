"""
macro_runner.py — Dynamic macro executor. (BOT-ANDRO — identik dengan BOT-EMU,
hanya ganti import 'emulator' → 'device')

Macros adalah file JSON di folder macros/.
Setiap macro mendefinisikan list steps dengan actions dan parameters.

Supported actions:
    tap           — tap(x, y)
    swipe         — swipe(x1, y1, x2, y2, duration_ms)
    input_text    — ketik teks ke field aktif
    press_key     — kirim Android keycode
    key_back      — tekan BACK
    key_home      — tekan HOME
    launch_app    — buka app Android by package name
    stop_app      — force stop app
    wait          — sleep N detik
    screenshot    — ambil screenshot (selalu disimpan)
    repeat        — ulangi sub-sequence N kali
    swipe_up      — shorthand scroll atas
    swipe_down    — shorthand scroll bawah
    swipe_left    — shorthand swipe kiri
    swipe_right   — shorthand swipe kanan
    check_screen  — cek pixel color, abort jika gagal
    check_screen_not — cek pixel BUKAN warna tertentu, abort jika match
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import device
import capture
import folder_manager
import screen_checker

logger = logging.getLogger(__name__)


class MacroAbortError(Exception):
    """Raised saat check_screen gagal — graceful abort."""
    pass


# Path ke folder macros (relatif terhadap lokasi file ini)
MACROS_DIR = Path(__file__).parent / "macros"


# ── Macro loader ─────────────────────────────────────────────────────────────

def list_macros() -> list[str]:
    """Return list nama macro tersedia (filename tanpa .json)."""
    if not MACROS_DIR.exists():
        return []
    return [f.stem for f in MACROS_DIR.glob("*.json")]


def load_macro(macro_name: str) -> dict:
    """Load macro dari macros/{macro_name}.json."""
    path = MACROS_DIR / f"{macro_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Macro tidak ditemukan: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def macro_exists(macro_name: str) -> bool:
    return (MACROS_DIR / f"{macro_name}.json").exists()


# ── Step executor ─────────────────────────────────────────────────────────────

def _execute_step(step: dict, transaction_id: str, params: dict) -> None:
    """Eksekusi satu step macro."""
    action = step.get("action", "").lower()
    label = step.get("label", action)

    def _log(msg: str) -> None:
        logger.info(f"[{transaction_id}] {msg}")
        folder_manager.write_log(transaction_id, msg)

    if action == "tap":
        x, y = _resolve(step, "x", params), _resolve(step, "y", params)
        _log(f"  tap({x}, {y}) — {label}")
        device.tap(int(x), int(y))

    elif action == "swipe":
        x1 = int(_resolve(step, "x1", params))
        y1 = int(_resolve(step, "y1", params))
        x2 = int(_resolve(step, "x2", params))
        y2 = int(_resolve(step, "y2", params))
        dur = int(step.get("duration_ms", 500))
        _log(f"  swipe({x1},{y1}→{x2},{y2}) — {label}")
        device.swipe(x1, y1, x2, y2, dur)

    elif action == "swipe_up":
        cx = int(step.get("cx", 540))
        top = int(step.get("top", 200))
        bottom = int(step.get("bottom", 1400))
        dur = int(step.get("duration_ms", 400))
        _log(f"  swipe_up — {label}")
        device.swipe(cx, bottom, cx, top, dur)

    elif action == "swipe_down":
        cx = int(step.get("cx", 540))
        top = int(step.get("top", 200))
        bottom = int(step.get("bottom", 1400))
        dur = int(step.get("duration_ms", 400))
        _log(f"  swipe_down — {label}")
        device.swipe(cx, top, cx, bottom, dur)

    elif action == "swipe_left":
        cy = int(step.get("cy", 960))
        left = int(step.get("left", 100))
        right = int(step.get("right", 980))
        dur = int(step.get("duration_ms", 400))
        _log(f"  swipe_left — {label}")
        device.swipe(right, cy, left, cy, dur)

    elif action == "swipe_right":
        cy = int(step.get("cy", 960))
        left = int(step.get("left", 100))
        right = int(step.get("right", 980))
        dur = int(step.get("duration_ms", 400))
        _log(f"  swipe_right — {label}")
        device.swipe(left, cy, right, cy, dur)

    elif action == "input_text":
        text = str(_resolve(step, "text", params, default=""))
        _log(f"  input_text: {text[:30]}{'...' if len(text) > 30 else ''}")
        device.input_text(text)

    elif action == "press_key":
        keycode = int(_resolve(step, "keycode", params))
        _log(f"  press_key({keycode}) — {label}")
        device.press_key(keycode)

    elif action == "key_back":
        _log(f"  key_back")
        device.press_back()

    elif action == "key_home":
        _log(f"  key_home")
        device.press_home()

    elif action == "launch_app":
        package = str(_resolve(step, "package", params))
        activity = str(step.get("activity", ""))
        _log(f"  launch_app: {package}")
        device.launch_app(package, activity)

    elif action == "stop_app":
        package = str(_resolve(step, "package", params))
        _log(f"  stop_app: {package}")
        device.stop_app(package)

    elif action == "wait":
        seconds = float(_resolve(step, "seconds", params, default=1.0))
        _log(f"  wait({seconds}s)")
        time.sleep(seconds)

    elif action == "screenshot":
        path = capture.capture_screen(transaction_id, label)
        _log(f"  screenshot saved: {path}")

    elif action == "check_screen":
        x = int(_resolve(step, "x", params))
        y = int(_resolve(step, "y", params))
        expected = str(_resolve(step, "expected_color", params, default="#FFFFFF"))
        tol = int(step.get("tolerance", 50))
        fail_reason = str(step.get("fail_reason", "Kondisi layar tidak sesuai"))
        on_fail_steps = step.get("on_fail", [])

        _log(f"  check_screen({x},{y}) expected={expected} tol={tol} — {label}")
        match, detail = screen_checker.check_pixel_color(x, y, expected, tol, transaction_id)
        _log(f"  check_screen result: match={match} | {detail}")

        if not match:
            _log(f"  [FAIL] CHECK FAILED: {fail_reason}")
            for fail_step in on_fail_steps:
                _execute_step(fail_step, transaction_id, params)
            raise MacroAbortError(fail_reason)
        else:
            _log(f"  [OK] CHECK PASSED")

    elif action == "check_screen_not":
        x = int(_resolve(step, "x", params))
        y = int(_resolve(step, "y", params))
        unexpected = str(_resolve(step, "unexpected_color", params, default="#000000"))
        tol = int(step.get("tolerance", 50))
        fail_reason = str(step.get("fail_reason", "Kondisi layar tidak sesuai"))
        on_fail_steps = step.get("on_fail", [])

        _log(f"  check_screen_not({x},{y}) unexpected={unexpected} tol={tol} — {label}")
        passed, detail = screen_checker.check_pixel_not_color(x, y, unexpected, tol, transaction_id)
        _log(f"  check_screen_not result: passed={passed} | {detail}")

        if not passed:
            _log(f"  [FAIL] CHECK FAILED: {fail_reason}")
            for fail_step in on_fail_steps:
                _execute_step(fail_step, transaction_id, params)
            raise MacroAbortError(fail_reason)
        else:
            _log(f"  [OK] CHECK PASSED")

    elif action == "repeat":
        n = int(step.get("times", 1))
        sub_steps = step.get("steps", [])
        _log(f"  repeat x{n} — {label}")
        for i in range(n):
            _log(f"    iteration {i + 1}/{n}")
            for sub in sub_steps:
                _execute_step(sub, transaction_id, params)

    else:
        _log(f"  [WARN] Unknown action: '{action}' — skipped")


def _resolve(step: dict, key: str, params: dict, default: Any = None) -> Any:
    """
    Resolve nilai step — support dynamic params injection.
    Jika value adalah string seperti '$amount', cari di dict params.
    """
    val = step.get(key, default)
    if isinstance(val, str) and val.startswith("$"):
        param_key = val[1:]
        return params.get(param_key, val)
    return val


# ── Main run ─────────────────────────────────────────────────────────────────

def run_macro(macro_name: str, transaction_id: str, params: dict) -> None:
    """
    Load dan eksekusi macro berdasarkan nama.
    params dapat override nilai step yang diawali $ di JSON macro.
    Screenshots SELALU disimpan, TIDAK PERNAH dihapus.
    """
    macro = load_macro(macro_name)
    steps = macro.get("steps", [])
    desc = macro.get("description", macro_name)

    logger.info(f"[{transaction_id}] Running macro '{macro_name}': {desc}")
    folder_manager.write_log(transaction_id, f"=== Macro: {macro_name} | {desc} ===")
    folder_manager.write_log(transaction_id, f"Params: {params}")

    for i, step in enumerate(steps):
        step_label = step.get("label", step.get("action", f"step_{i+1}"))
        folder_manager.write_log(transaction_id, f"Step {i+1}/{len(steps)}: {step_label}")
        try:
            _execute_step(step, transaction_id, params)
        except Exception as exc:
            logger.exception(f"[{transaction_id}] Step {i+1} failed: {exc}")
            folder_manager.write_log(transaction_id, f"ERROR step {i+1}: {exc}")
            raise

    folder_manager.write_log(transaction_id, f"=== Macro '{macro_name}' selesai ===")
    logger.info(f"[{transaction_id}] Macro '{macro_name}' selesai.")
