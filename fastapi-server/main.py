"""
main.py — FastAPI Server entry point. (BOT-ANDRO)
Berjalan di Termux Android.
Run with: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes.api import router as api_router

app = FastAPI(
    title="BOT-ANDRO API Server",
    description="BOT Automation berjalan langsung di device Android via Termux",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health() -> dict:
    """
    Health check endpoint.
    Juga menampilkan URL tunnel aktif jika ada.
    """
    tunnel_url = settings.CLOUDFLARE_URL
    tunnel_file = Path(settings.TUNNEL_URL_FILE)
    if tunnel_file.exists():
        tunnel_url = tunnel_file.read_text(encoding="utf-8").strip() or tunnel_url

    return {
        "status": "ok",
        "server": "BOT-ANDRO",
        "tunnel_url": tunnel_url,
        "bot_worker": settings.BOT_WORKER_PATH,
    }


# ── Dashboard Auth ────────────────────────────────────────────────────────────
def get_auth_token(request: Request) -> bool:
    return request.cookies.get("andro_auth") == settings.DASHBOARD_PASS


@app.get("/login", tags=["Auth"], response_class=HTMLResponse)
def get_login(request: Request, error: int = 0) -> HTMLResponse:
    if get_auth_token(request):
        return RedirectResponse(url="/dashboard", status_code=303)

    login_path = Path(__file__).parent / "login.html"
    if not login_path.exists():
        return HTMLResponse("<h1>Error: login.html not found</h1>")

    content = login_path.read_text(encoding="utf-8")
    if error == 1:
        err_html = '<div class="alert alert-danger py-2 small border-0 mb-4" style="background: rgba(244, 63, 94, 0.1); color: #f43f5e;"><i class="fa-solid fa-triangle-exclamation me-1"></i> Username atau password salah!</div>'
        content = content.replace("<!-- ERROR_MESSAGE_PLACEHOLDER -->", err_html)
    return HTMLResponse(content)


@app.post("/login", tags=["Auth"])
def post_login(username: str = Form(...), password: str = Form(...)) -> Response:
    if username == settings.DASHBOARD_USER and password == settings.DASHBOARD_PASS:
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie(key="andro_auth", value=settings.DASHBOARD_PASS, httponly=True, max_age=86400 * 7)
        return resp
    return RedirectResponse(url="/login?error=1", status_code=303)


@app.get("/logout", tags=["Auth"])
def logout() -> Response:
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("andro_auth")
    return resp


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/dashboard", tags=["Monitoring"], response_class=HTMLResponse)
def get_dashboard(request: Request) -> Response:
    if not get_auth_token(request):
        return RedirectResponse(url="/login", status_code=303)

    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        return dashboard_path.read_text(encoding="utf-8")
    return "<h1>Dashboard template not found</h1>"


# ── Macro Recorder ────────────────────────────────────────────────────────────
@app.get("/recorder", tags=["Tools"], response_class=HTMLResponse)
def get_recorder(request: Request) -> Response:
    if not get_auth_token(request):
        return RedirectResponse(url="/login", status_code=303)

    recorder_path = Path(__file__).parent / "recorder.html"
    if recorder_path.exists():
        return recorder_path.read_text(encoding="utf-8")
    return "<h1>Recorder template not found</h1>"


# ── Setup & Settings ──────────────────────────────────────────────────────────
@app.get("/setup", tags=["Tools"], response_class=HTMLResponse)
def get_setup(request: Request) -> Response:
    # Anyone can access setup page HTML, but the API calls inside require the default api key
    setup_path = Path(__file__).parent / "setup.html"
    if setup_path.exists():
        return setup_path.read_text(encoding="utf-8")
    return "<h1>Setup template not found</h1>"

@app.get("/settings", tags=["Tools"], response_class=HTMLResponse)
def get_settings(request: Request) -> Response:
    if not get_auth_token(request):
        return RedirectResponse(url="/login", status_code=303)

    settings_path = Path(__file__).parent / "settings.html"
    if settings_path.exists():
        return settings_path.read_text(encoding="utf-8")
    return "<h1>Settings template not found</h1>"


# ── Direct run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(
            "main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=False,
        )
    except KeyboardInterrupt:
        print("\n[INFO] Server FastAPI telah dihentikan.")
