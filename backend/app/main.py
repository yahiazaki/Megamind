"""Megamind API + static frontend."""
import logging
import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .ingest.pipeline import recover_interrupted
from .rag.index import index
from .routers import library, owner, public, study
from .services import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()
app = FastAPI(title="Megamind", version="0.1.0")

for r in (public.router, library.router, study.router, owner.router):
    app.include_router(r)


@app.on_event("startup")
def startup():
    init_db()
    recover_interrupted()
    threading.Thread(target=index.reload, daemon=True).start()
    scheduler.start()


@app.get("/api/health")
def health():
    return {"ok": True, "index": index.stats()}


# ------------------------------------------------------------------ frontend (built SPA)
dist = settings.frontend_dist
if (dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = (dist / path).resolve()
    if path and candidate.is_file() and dist.resolve() in candidate.parents:
        return FileResponse(candidate)
    index_html = dist / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    return JSONResponse({"detail": "Frontend not built. Run: cd frontend && npm install && npm run build"},
                        status_code=404)
