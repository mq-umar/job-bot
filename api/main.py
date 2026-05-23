"""
api/main.py — FastAPI application entry point.
Serves the React UI from ui/dist and all API routes under /api/.
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from api.routers import bot, jobs, resumes, profiles, settings as settings_router
from api.websocket import router as ws_router

app = FastAPI(title="Job Bot", version="2.0.0")

# ── Security headers ──────────────────────────────────────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]         = "DENY"
    response.headers["X-XSS-Protection"]        = "1; mode=block"
    response.headers["Referrer-Policy"]         = "no-referrer"
    return response


# ── Token enforcement on all /api/* routes ────────────────────────────────────
# Exemptions: /api/settings/token (how the UI fetches the token on load)

_TOKEN_EXEMPT = {"/api/settings/token"}

@app.middleware("http")
async def enforce_token(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in _TOKEN_EXEMPT:
        from api.security import verify_token
        token = request.headers.get("X-Bot-Token", "")
        if not verify_token(token):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ── CORS — localhost only ─────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8099",
        "http://127.0.0.1:8099",
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ───────────────────────────────────────────────────────────────

app.include_router(bot.router,             prefix="/api/bot",      tags=["bot"])
app.include_router(jobs.router,            prefix="/api/jobs",     tags=["jobs"])
app.include_router(resumes.router,         prefix="/api/resumes",  tags=["resumes"])
app.include_router(profiles.router,        prefix="/api/profiles", tags=["profiles"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(ws_router)

# ── Serve built React app ─────────────────────────────────────────────────────

_UI_DIST = Path(__file__).parent.parent / "ui" / "dist"
_UI_DIST_RESOLVED = _UI_DIST.resolve()

if _UI_DIST.exists():
    _assets = _UI_DIST / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(str(_UI_DIST / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Resolve and ensure the path stays within ui/dist — prevents traversal
        candidate = (_UI_DIST / full_path).resolve()
        try:
            candidate.relative_to(_UI_DIST_RESOLVED)
        except ValueError:
            # Path escaped ui/dist — serve index.html (SPA fallback)
            return FileResponse(str(_UI_DIST / "index.html"))
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_UI_DIST / "index.html"))
