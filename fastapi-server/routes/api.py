"""
routes/api.py — All API route handlers. (BOT-ANDRO)

Perbedaan dari BOT-EMU:
  - /api/devices menggantikan /api/emulators
  - List device via 'adb devices' (bukan LDPlayer-specific)
  - /api/screenshot — live screenshot untuk Macro Recorder
  - /api/device-info — resolusi layar device
"""

import base64
import io
import json
import os
import time
from pathlib import Path
from typing import Any
import subprocess
import dotenv
import requests
from urllib.parse import urlparse, urljoin

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status, Request, UploadFile, File
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

import bot_trigger
from config import settings

router = APIRouter()

MACROS_DIR = Path(settings.BOT_WORKER_PATH).parent / "macros"


# ── Auth ───────────────────────────────────────────────────────────────────────

def verify_api_key(request: Request, x_api_key: str = Header(None, alias="X-API-Key")) -> str:
    if request.query_params.get("web") == "1" and request.cookies.get("andro_auth") == settings.DASHBOARD_PASS:
        return "web_auth"
    
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


# ── Schemas ───────────────────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=100)
    task_type: str = Field(..., min_length=1, max_length=100)
    amount: str = Field(default="")
    id_player: str = Field(default="")
    params: dict[str, Any] = Field(default_factory=dict)


class TriggerResponse(BaseModel):
    success: bool
    transaction_id: str
    message: str


class StatusResponse(BaseModel):
    transaction_id: str
    status: str
    detail: str
    updated_at: str


# ── Trigger ───────────────────────────────────────────────────────────────────

@router.post(
    "/trigger",
    response_model=TriggerResponse,
    status_code=202,
    summary="Trigger BOT Macro",
)
def trigger_bot(
    body: TriggerRequest,
    _key: str = Depends(verify_api_key),
) -> TriggerResponse:
    merged_params = dict(body.params)
    if body.amount:
        merged_params["amount"] = body.amount
    if body.id_player:
        merged_params["id_player"] = body.id_player

    bot_trigger.trigger(
        transaction_id=body.transaction_id,
        task_type=body.task_type,
        params=merged_params,
    )
    return TriggerResponse(
        success=True,
        transaction_id=body.transaction_id,
        message=f"Job '{body.task_type}' diterima dan dijalankan",
    )


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status/{transaction_id}", response_model=StatusResponse)
def job_status(
    transaction_id: str,
    _key: str = Depends(verify_api_key),
) -> StatusResponse:
    data = bot_trigger.get_status(transaction_id)
    return StatusResponse(
        transaction_id=transaction_id,
        status=data["status"],
        detail=data["detail"],
        updated_at=data["updated_at"],
    )


@router.get("/statuses", summary="List All Jobs")
def list_jobs_status() -> dict:
    return bot_trigger._load_store()


@router.delete("/statuses", summary="Clear All Jobs")
def clear_all_jobs_status() -> dict:
    return bot_trigger.clear_jobs()


@router.delete("/statuses/{transaction_id}", summary="Delete Job")
def delete_single_job_status(transaction_id: str) -> dict:
    return bot_trigger.delete_job(transaction_id)


@router.get("/statuses/{transaction_id}/screenshots", summary="List Screenshots for Job")
def list_job_screenshots(transaction_id: str) -> dict:
    screenshots_dir = Path(settings.BOT_WORKER_PATH).parent / "output" / transaction_id / "screenshots"
    if not screenshots_dir.exists():
        return {"images": []}
    images = [f.name for f in sorted(screenshots_dir.glob("*.png"))]
    return {"images": images}


@router.get("/statuses/{transaction_id}/screenshots/{filename}")
def get_job_screenshot(transaction_id: str, filename: str):
    target = Path(settings.BOT_WORKER_PATH).parent / "output" / transaction_id / "screenshots" / filename
    if not target.exists() or not target.name.endswith(".png"):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return Response(content=target.read_bytes(), media_type="image/png")


# ── Device Status ─────────────────────────────────────────────────────────────

@router.get(
    "/devices",
    summary="List ADB Devices",
    description="Cek device yang terdeteksi via ADB (termasuk koneksi lokal).",
)
def list_adb_devices() -> dict:
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")

        devices = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                label = "Local (Self)" if "127.0.0.1" in serial or "localhost" in serial else serial
                devices.append({"serial": serial, "label": label, "status": "online"})

        return {"success": True, "total": len(devices), "devices": devices}
    except Exception as err:
        return {"success": False, "total": 0, "devices": [], "error": str(err)}


# ── Tunnel URL (Quick Tunnel) ─────────────────────────────────────────────────

@router.get(
    "/tunnel-url",
    summary="Get Active Tunnel URL",
    description="Baca URL Cloudflare Quick Tunnel yang sedang aktif.",
)
def get_tunnel_url() -> dict:
    tunnel_file = Path(settings.TUNNEL_URL_FILE)
    if tunnel_file.exists():
        url = tunnel_file.read_text(encoding="utf-8").strip()
        return {"success": True, "url": url}
    return {"success": False, "url": "", "message": "Tunnel belum aktif atau URL belum tersimpan"}



# ── Live Screenshot (untuk Macro Recorder) ───────────────────────────────────

DEVICE_SERIAL = os.getenv("DEVICE_SERIAL", "127.0.0.1:5555")
_SCREENSHOT_TEMP = "/data/local/tmp/bot_recorder_temp.png"


def _get_device_serial() -> str:
    """Baca DEVICE_SERIAL dari .env bot-worker secara dinamis."""
    try:
        bot_worker_env = Path(settings.BOT_WORKER_PATH).parent / ".env"
        if bot_worker_env.exists():
            for line in bot_worker_env.read_text().splitlines():
                if line.startswith("DEVICE_SERIAL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return DEVICE_SERIAL


@router.get(
    "/screenshot",
    summary="Live Screenshot",
    description="Ambil screenshot langsung dari device untuk Macro Recorder.",
    tags=["Recorder"],
)
def get_live_screenshot():
    """
    Return screenshot device sebagai PNG binary.
    Tidak butuh auth — hanya untuk recorder internal.
    """
    try:
        serial = _get_device_serial()
        # Gunakan folder tmp milik Termux, bukan /tmp sistem Android yg tidak bisa diakses
        termux_prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        temp_local = os.path.join(termux_prefix, "tmp", f"bot_recorder_{int(time.time())}.png")

        # screencap ke device tmp
        r1 = subprocess.run(
            ["adb", "-s", serial, "shell", "screencap", "-p", _SCREENSHOT_TEMP],
            capture_output=True, timeout=10
        )
        if r1.returncode != 0:
            raise RuntimeError(f"screencap gagal: {r1.stderr.decode(errors='ignore')}")

        # pull ke Termux temp
        r2 = subprocess.run(
            ["adb", "-s", serial, "pull", _SCREENSHOT_TEMP, temp_local],
            capture_output=True, timeout=10
        )
        if r2.returncode != 0:
            raise RuntimeError(f"adb pull gagal: {r2.stderr.decode(errors='ignore')}")

        # hapus dari device tmp
        subprocess.run(
            ["adb", "-s", serial, "shell", "rm", "-f", _SCREENSHOT_TEMP],
            capture_output=True, timeout=5
        )

        png_data = Path(temp_local).read_bytes()
        Path(temp_local).unlink(missing_ok=True)
        return Response(content=png_data, media_type="image/png")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Screenshot gagal: {exc}")


@router.get(
    "/screenshot/delayed",
    summary="Delayed Screenshot",
    description="Tunggu N detik lalu ambil screenshot. Berguna agar user bisa pindah ke app yang mau direkam.",
    tags=["Recorder"],
)
def get_delayed_screenshot(seconds: int = 5):
    """
    Tunggu `seconds` detik (max 15) lalu ambil screenshot device.
    Gunakan ini saat recorder dibuka di HP yang sama, user punya waktu
    untuk minimize browser dan pindah ke app yang ingin direkam.
    """
    seconds = max(1, min(seconds, 15))  # clamp 1-15 detik
    time.sleep(seconds)

    try:
        serial = _get_device_serial()
        termux_prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        temp_local = os.path.join(termux_prefix, "tmp", f"bot_recorder_{int(time.time())}.png")

        r1 = subprocess.run(
            ["adb", "-s", serial, "shell", "screencap", "-p", _SCREENSHOT_TEMP],
            capture_output=True, timeout=10
        )
        if r1.returncode != 0:
            raise RuntimeError(f"screencap gagal: {r1.stderr.decode(errors='ignore')}")

        r2 = subprocess.run(
            ["adb", "-s", serial, "pull", _SCREENSHOT_TEMP, temp_local],
            capture_output=True, timeout=10
        )
        if r2.returncode != 0:
            raise RuntimeError(f"adb pull gagal: {r2.stderr.decode(errors='ignore')}")

        subprocess.run(
            ["adb", "-s", serial, "shell", "rm", "-f", _SCREENSHOT_TEMP],
            capture_output=True, timeout=5
        )

        png_data = Path(temp_local).read_bytes()
        Path(temp_local).unlink(missing_ok=True)
        return Response(content=png_data, media_type="image/png")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Delayed screenshot gagal: {exc}")


@router.get(
    "/device-info",
    summary="Device Screen Info",
    description="Ambil resolusi layar device (untuk scaling koordinat di Recorder).",
    tags=["Recorder"],
)
def get_device_info() -> dict:
    """Return resolusi layar device."""
    try:
        serial = _get_device_serial()
        result = subprocess.run(
            ["adb", "-s", serial, "shell", "wm", "size"],
            capture_output=True, text=True, timeout=5
        )
        # Output: "Physical size: 1080x2340"
        line = result.stdout.strip()
        if "x" in line:
            parts = line.split(":")[-1].strip().split("x")
            width = int(parts[0].strip())
            height = int(parts[1].strip())
            return {"success": True, "width": width, "height": height, "serial": serial}
        return {"success": False, "width": 1080, "height": 1920, "serial": serial}
    except Exception as exc:
        return {"success": False, "width": 1080, "height": 1920, "error": str(exc)}


@router.post(
    "/test-step",
    summary="Test Single Step",
    description="Eksekusi satu step macro langsung (untuk preview saat merekam).",
    tags=["Recorder"],
)
def test_single_step(body: dict = Body(...)) -> dict:
    """
    Eksekusi satu ADB command langsung tanpa harus buat macro dulu.
    Berguna untuk preview koordinat tap saat merekam.
    body: {"action": "tap", "x": 500, "y": 800}
    """
    try:
        serial = _get_device_serial()
        action = body.get("action", "").lower()

        if action == "tap":
            x, y = int(body.get("x", 0)), int(body.get("y", 0))
            subprocess.run(["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)],
                          capture_output=True, timeout=10)
            return {"success": True, "message": f"Tap ({x}, {y}) berhasil"}

        elif action == "swipe":
            x1, y1 = int(body.get("x1", 0)), int(body.get("y1", 0))
            x2, y2 = int(body.get("x2", 0)), int(body.get("y2", 0))
            dur = int(body.get("duration_ms", 500))
            subprocess.run(["adb", "-s", serial, "shell", "input", "swipe",
                           str(x1), str(y1), str(x2), str(y2), str(dur)],
                          capture_output=True, timeout=10)
            return {"success": True, "message": f"Swipe ({x1},{y1})→({x2},{y2}) berhasil"}

        elif action == "key_home":
            subprocess.run(["adb", "-s", serial, "shell", "input", "keyevent", "3"],
                          capture_output=True, timeout=5)
            return {"success": True, "message": "Key HOME ditekan"}

        elif action == "key_back":
            subprocess.run(["adb", "-s", serial, "shell", "input", "keyevent", "4"],
                          capture_output=True, timeout=5)
            return {"success": True, "message": "Key BACK ditekan"}

        elif action == "launch_app":
            pkg = body.get("package", "")
            subprocess.run(["adb", "-s", serial, "shell", "monkey", "-p", pkg,
                           "-c", "android.intent.category.LAUNCHER", "1"],
                          capture_output=True, timeout=10)
            return {"success": True, "message": f"App '{pkg}' dibuka"}

        else:
            return {"success": False, "message": f"Action '{action}' tidak didukung di test-step"}

    except Exception as exc:
        return {"success": False, "message": str(exc)}


# ── Macro Management ──────────────────────────────────────────────────────────

@router.get("/macros", summary="List Macros")
def list_macros(_key: str = Depends(verify_api_key)) -> dict:
    MACROS_DIR.mkdir(parents=True, exist_ok=True)
    macros = []
    for f in sorted(MACROS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            macros.append({
                "name": f.stem,
                "description": data.get("description", ""),
                "step_count": len(data.get("steps", [])),
                "file": f.name,
            })
        except Exception:
            macros.append({"name": f.stem, "description": "Error parsing JSON", "step_count": 0})
    return {"macros": macros, "count": len(macros)}


@router.get("/macros/backup", summary="Download Single Macro as JSON")
def download_single_macro(name: str, _key: str = Depends(verify_api_key)) -> StreamingResponse:
    """Download satu macro sebagai file JSON berdasarkan nama."""
    path = MACROS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Macro '{name}' tidak ditemukan")
    content = path.read_text(encoding="utf-8")
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}.json"'},
    )


@router.post("/macros/restore", summary="Restore Macro from JSON")
async def restore_single_macro(
    file: UploadFile = File(...),
    _key: str = Depends(verify_api_key),
) -> dict:
    """Restore / upload macro dari file JSON. Kalau nama sudah ada, auto-rename jadi 'nama (1).json'."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File harus berupa JSON")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="File macro harus berupa JSON object")

        # Dukung format single macro langsung {...} atau format { "nama": {...} }
        if "steps" in data:
            macro_data = data
            name = data.get("name", Path(file.filename).stem)
        else:
            first_key = next(iter(data.keys()))
            macro_data = data[first_key]
            name = first_key

        if not isinstance(macro_data, dict) or "steps" not in macro_data:
            raise HTTPException(status_code=400, detail="Macro harus memiliki field 'steps'")

        MACROS_DIR.mkdir(parents=True, exist_ok=True)

        target = MACROS_DIR / f"{name}.json"
        if target.exists():
            counter = 1
            while True:
                new_name = f"{name} ({counter}).json"
                new_target = MACROS_DIR / new_name
                if not new_target.exists():
                    target = new_target
                    name = f"{name} ({counter})"
                    break
                counter += 1

        target.write_text(json.dumps(macro_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"success": True, "message": f"Macro '{name}' berhasil di-restore.", "file": str(target)}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="File JSON tidak valid")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error restore: {exc}")


@router.get("/macros/{name}", summary="Get Macro Detail")
def get_macro(name: str, _key: str = Depends(verify_api_key)) -> dict:
    path = MACROS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Macro '{name}' tidak ditemukan")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error membaca macro: {exc}")


@router.post("/macros/{name}", status_code=201, summary="Create/Update Macro")
def save_macro(
    name: str,
    body: dict = Body(...),
    _key: str = Depends(verify_api_key),
) -> dict:
    if "steps" not in body or not isinstance(body["steps"], list):
        raise HTTPException(status_code=422, detail="Macro harus memiliki field 'steps' berupa list")

    MACROS_DIR.mkdir(parents=True, exist_ok=True)
    path = MACROS_DIR / f"{name}.json"
    exists = path.exists()
    body["name"] = name
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")

    action = "diperbarui" if exists else "dibuat"
    return {
        "success": True,
        "message": f"Macro '{name}' berhasil {action}",
        "file": str(path),
        "step_count": len(body["steps"]),
    }


@router.delete("/macros/{name}", summary="Delete Macro")
def delete_macro(name: str, _key: str = Depends(verify_api_key)) -> dict:
    path = MACROS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Macro '{name}' tidak ditemukan")
    path.unlink()
    return {"success": True, "message": f"Macro '{name}' dihapus"}

# ── System / Setup ────────────────────────────────────────────────────────────

FASTAPI_ENV_PATH = Path(settings.BOT_WORKER_PATH).parent.parent / "fastapi-server" / ".env"
WORKER_ENV_PATH = Path(settings.BOT_WORKER_PATH).parent / ".env"

@router.get("/system/config", summary="Get System Config")
def get_system_config(_key: str = Depends(verify_api_key)) -> dict:
    fastapi_config = dotenv.dotenv_values(FASTAPI_ENV_PATH)
    worker_config = dotenv.dotenv_values(WORKER_ENV_PATH)
    
    return {
        "fastapi": fastapi_config,
        "worker": worker_config
    }

@router.post("/system/config", summary="Save System Config")
def save_system_config(
    body: dict = Body(...),
    _key: str = Depends(verify_api_key)
) -> dict:
    fastapi_data = body.get("fastapi", {})
    worker_data = body.get("worker", {})
    
    # Save the keys using dotenv.set_key
    for k, v in fastapi_data.items():
        if v is not None:
            dotenv.set_key(str(FASTAPI_ENV_PATH), k, str(v))
            
    for k, v in worker_data.items():
        if v is not None:
            dotenv.set_key(str(WORKER_ENV_PATH), k, str(v))
            
    return {"success": True, "message": "Konfigurasi berhasil disimpan."}

@router.post("/system/adb/connect", summary="Connect ADB via IP:Port")
def connect_adb(
    body: dict = Body(...),
    _key: str = Depends(verify_api_key)
) -> dict:
    device = body.get("device", "127.0.0.1:5555")
    try:
        result = subprocess.run(["adb", "connect", device], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        
        if "connected to" in output.lower() or "already connected" in output.lower():
            # Save to worker_env
            dotenv.set_key(str(WORKER_ENV_PATH), "DEVICE_SERIAL", device)
            return {"success": True, "message": f"Berhasil terkoneksi ke {device}", "output": output}
        else:
            return {"success": False, "message": f"Gagal koneksi. Output: {output}", "output": output}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/system/bot/start", summary="Start Bot Worker")
def start_bot(
    _key: str = Depends(verify_api_key)
) -> dict:
    script_dir = Path(settings.BOT_WORKER_PATH).parent.parent
    start_sh = script_dir / "start_simple.sh"
    if not start_sh.exists():
        return {"success": False, "message": "start_simple.sh tidak ditemukan!"}
        
    try:
        # Start in background using Popen
        subprocess.Popen(
            ["bash", str(start_sh)], 
            cwd=str(script_dir)
        )
        return {"success": True, "message": "Bot process sedang dijalankan di background."}
    except Exception as e:
         return {"success": False, "message": str(e)}

@router.post("/system/bot/stop", summary="Stop Bot Worker")
def stop_bot(
    _key: str = Depends(verify_api_key)
) -> dict:
    script_dir = Path(settings.BOT_WORKER_PATH).parent.parent
    stop_sh = script_dir / "stop.sh"
    try:
        subprocess.run(["bash", str(stop_sh)], cwd=str(script_dir), timeout=5)
        return {"success": True, "message": "Bot process telah dihentikan."}
    except Exception as e:
         return {"success": False, "message": str(e)}


# ── Target Server Settings (Update URL) ───────────────────────────────────────

class TargetServerConfig(BaseModel):
    device_id: str = Field(default="", min_length=0, max_length=200)
    target_server_url: str = Field(default="", min_length=0, max_length=500)
    target_api_secret: str = Field(default="", min_length=0, max_length=500)


@router.get("/settings/target-server", summary="Get Target Server Config")
def get_target_server_config(_key: str = Depends(verify_api_key)) -> dict:
    """Baca konfigurasi target server dari bot-worker/.env"""
    worker_env = Path(settings.BOT_WORKER_PATH).parent / ".env"
    values = dotenv.dotenv_values(worker_env)
    return {
        "device_id": values.get("DEVICE_ID", ""),
        "target_server_url": values.get("TARGET_SERVER_URL", ""),
        "target_api_secret": values.get("TARGET_API_SECRET", ""),
    }


@router.post("/settings/target-server", summary="Save Target Server Config")
def save_target_server_config(
    body: TargetServerConfig,
    _key: str = Depends(verify_api_key)
) -> dict:
    """Simpan konfigurasi target server ke bot-worker/.env"""
    worker_env = Path(settings.BOT_WORKER_PATH).parent / ".env"
    worker_env.parent.mkdir(parents=True, exist_ok=True)
    if not worker_env.exists():
        worker_env.write_text("", encoding="utf-8")

    dotenv.set_key(str(worker_env), "DEVICE_ID", body.device_id)
    dotenv.set_key(str(worker_env), "TARGET_SERVER_URL", body.target_server_url)
    dotenv.set_key(str(worker_env), "TARGET_API_SECRET", body.target_api_secret)

    return {"success": True, "message": "Konfigurasi target server berhasil disimpan."}


@router.post("/settings/update-url", summary="Update URL to Target Server")
def update_url_to_target_server(
    _key: str = Depends(verify_api_key)
) -> dict:
    """
    Baca DEVICE_ID, TARGET_SERVER_URL, TARGET_API_SECRET dari .env,
    baca tunnel URL aktif, lalu POST ke target server.
    """
    worker_env = Path(settings.BOT_WORKER_PATH).parent / ".env"
    values = dotenv.dotenv_values(worker_env)

    device_id = values.get("DEVICE_ID", "").strip()
    target_url = values.get("TARGET_SERVER_URL", "").strip()
    api_secret = values.get("TARGET_API_SECRET", "").strip()

    if not target_url:
        raise HTTPException(status_code=400, detail="Target server URL belum diatur. Simpan konfigurasi dulu.")
    if not device_id:
        raise HTTPException(status_code=400, detail="Device ID belum diatur. Simpan konfigurasi dulu.")
    if not api_secret:
        raise HTTPException(status_code=400, detail="API Secret belum diatur. Simpan konfigurasi dulu.")

    # Validasi URL
    parsed = urlparse(target_url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Target server URL tidak valid.")

    # Baca tunnel URL aktif
    tunnel_file = Path(settings.TUNNEL_URL_FILE)
    tunnel_url = ""
    if tunnel_file.exists():
        tunnel_url = tunnel_file.read_text(encoding="utf-8").strip()

    # Ambil URL tunnel terbaru / yang sedang eksis, fallback ke local URL
    url_update = tunnel_url if tunnel_url else f"http://{settings.HOST}:{settings.PORT}"

    payload = {
        "device_id": device_id,
        "url_update": url_update,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-SECRET": api_secret,
    }

    try:
        # Manual redirect handling agar POST tidak berubah jadi GET saat redirect (misal http→https)
        resp = requests.post(target_url, json=payload, headers=headers, timeout=30, allow_redirects=False)
        if resp.status_code in (301, 302, 307, 308):
            location = resp.headers.get("Location", "")
            if location:
                redirect_url = urljoin(target_url, location)
                resp = requests.post(redirect_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return {
            "success": True,
            "message": "URL berhasil di-update ke target server.",
            "target_response": resp.text,
            "status_code": resp.status_code,
        }
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request ke target server timeout.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Tidak bisa terkoneksi ke target server.")
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Target server merespons error: HTTP {exc.response.status_code} - {exc.response.text}"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal mengirim ke target server: {str(exc)}")


@router.post("/bot/update-status", summary="Send Update Status to Target Server")
def send_update_status_manual(
    body: dict = Body(...),
    _key: str = Depends(verify_api_key),
) -> dict:
    """
    Kirim invoice ke target server /api/bot/update-status.
    Body: {"invoice": "TXN-123"}
    """
    invoice = body.get("invoice", "").strip()
    if not invoice:
        raise HTTPException(status_code=400, detail="Field 'invoice' wajib diisi.")

    worker_env = Path(settings.BOT_WORKER_PATH).parent / ".env"
    values = dotenv.dotenv_values(worker_env)

    target_url = values.get("TARGET_SERVER_URL", "").strip()
    api_secret = values.get("TARGET_API_SECRET", "").strip()

    if not target_url:
        raise HTTPException(status_code=400, detail="Target server URL belum diatur. Simpan konfigurasi dulu.")
    if not api_secret:
        raise HTTPException(status_code=400, detail="API Secret belum diatur. Simpan konfigurasi dulu.")

    url = target_url.rstrip("/") + "/api/bot/update-status"
    payload = {"invoice": invoice}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-SECRET": api_secret,
    }

    try:
        # Manual redirect handling agar POST tidak berubah jadi GET saat redirect (misal http→https)
        resp = requests.post(url, json=payload, headers=headers, timeout=30, allow_redirects=False)
        if resp.status_code in (301, 302, 307, 308):
            location = resp.headers.get("Location", "")
            if location:
                redirect_url = urljoin(url, location)
                resp = requests.post(redirect_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return {
            "success": True,
            "message": f"Update status berhasil dikirim ({resp.status_code}).",
            "target_response": resp.text,
            "status_code": resp.status_code,
        }
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request ke target server timeout.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Tidak bisa terkoneksi ke target server.")
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Target server merespons error: HTTP {exc.response.status_code} - {exc.response.text}"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal mengirim ke target server: {str(exc)}")
