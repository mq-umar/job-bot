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

# Allow only localhost — never external origins
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

# API routers
app.include_router(bot.router,             prefix="/api/bot",      tags=["bot"])
app.include_router(jobs.router,            prefix="/api/jobs",     tags=["jobs"])
app.include_router(resumes.router,         prefix="/api/resumes",  tags=["resumes"])
app.include_router(profiles.router,        prefix="/api/profiles", tags=["profiles"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(ws_router)

# Serve built React app (SPA routing — all unknown paths return index.html)
_UI_DIST = Path(__file__).parent.parent / "ui" / "dist"
if _UI_DIST.exists():
    _assets = _UI_DIST / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(str(_UI_DIST / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Serve actual files that exist (favicons, manifests, etc.)
        candidate = _UI_DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_UI_DIST / "index.html"))
