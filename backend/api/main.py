from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import check_db_connection
from .routers import api_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.database_url:
        if check_db_connection():
            logger.info("Database connection established")
        else:
            logger.warning("Database configured but connection check failed")
    else:
        logger.warning("DATABASE_URL not set. API will run without DB access.")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)
