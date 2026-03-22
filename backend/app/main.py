"""
FastAPI application entry point.
On startup: ingest data → build graph.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import get_db, close_db
from app.api import graph as graph_router
from app.api import chat as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    db = get_db()

    # Check if data has been ingested
    try:
        count = db.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='sales_order_headers'"
        ).fetchone()[0]
    except Exception:
        count = 0

    if count == 0:
        print("Running ETL ingest...")
        from app.etl.ingest import ingest_all
        backend_root = Path(__file__).resolve().parents[2]
        configured_data_dir = Path(settings.data_dir)
        data_root = configured_data_dir if configured_data_dir.is_absolute() else (backend_root / configured_data_dir).resolve()
        ingest_all(data_root)

    # Build or load graph
    cache_path = Path(settings.graph_cache_path)
    if not cache_path.exists():
        print("Building graph...")
        from app.graph.builder import build_and_save
        build_and_save()
    else:
        from app.graph.builder import load_graph
        load_graph()

    print("Startup complete.")
    yield

    # ── Shutdown ─────────────────────────────────────────────
    close_db()


app = FastAPI(
    title="O2C Graph API",
    description="Order-to-Cash Graph + LLM Query Interface",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(graph_router.router)
app.include_router(chat_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve frontend build if present (production)
frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
