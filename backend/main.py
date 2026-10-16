"""FastAPI application: CORS, routers under /api, table creation on startup."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db import init_db
from backend.routers import applications, auth, cron, portfolio, scholarships

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("scholartrack")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # create_all is idempotent and cheap; it keeps the project migration-free.
    try:
        init_db()
    except Exception:
        # A cold serverless invocation should still serve /health if the DB is
        # briefly unreachable, so log and carry on rather than crash the worker.
        log.exception("init_db failed during startup")
    yield


app = FastAPI(
    title="ScholarTrack API",
    version="1.0.0",
    description="Scholarship discovery and application tracker for Indian students.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


@api.get("/health", tags=["meta"])
def health() -> dict:
    return {"ok": True}


api.include_router(auth.router)
api.include_router(scholarships.router)
api.include_router(portfolio.router)
api.include_router(applications.router)
api.include_router(cron.router)

app.include_router(api)
