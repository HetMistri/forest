from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import check_db_connection

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # ── Database ─────────────────────────────────────────────────────
    if settings.database_url:
        if check_db_connection():
            logger.info("Database connection established")
        else:
            logger.warning("Database configured but connection check failed")
    else:
        logger.warning("DATABASE_URL not set. API will run without DB access.")

    # ── ML Model ─────────────────────────────────────────────────────
    try:
        from services.ml_bridge import MLBridge

        ml = MLBridge.get_instance()
        model_path = Path(settings.ml_model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[1] / model_path
        if ml.load_model(model_path):
            logger.info("ML model loaded successfully at startup")
        else:
            logger.warning("ML model failed to load — using hardcoded fallbacks")
    except Exception as exc:
        logger.warning("ML subsystem init failed: %s — using hardcoded fallbacks", exc)

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import api_router  # noqa: E402

app.include_router(api_router)
