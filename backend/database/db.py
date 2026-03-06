from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass(slots=True)
class DBConfig:
    database_url: str
    pool_pre_ping: bool = True

    @classmethod
    def from_env(cls) -> DBConfig:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise ValueError("DATABASE_URL is required for database operations")

        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        return cls(database_url=database_url)


@dataclass(slots=True)
class FeatureRecord:
    grid_id: str
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    ndvi: float
    ndmi: float
    evi: float | None
    vv: float | None
    vh: float | None
    vv_vh_ratio: float | None
    ndvi_trend: float | None
    source: str
    captured_at: datetime


class PostgresFeatureStore:
    def __init__(self, config: DBConfig | None = None) -> None:
        self.config = config or DBConfig.from_env()
        self._engine: Engine = create_engine(
            self.config.database_url,
            pool_pre_ping=self.config.pool_pre_ping,
        )

    def upsert_forest_features(self, records: list[FeatureRecord]) -> int:
        if not records:
            return 0

        statement = text(
            """
            SELECT upsert_forest_feature(
                :grid_id,
                ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326),
                :ndvi,
                :ndmi,
                :sar_ratio,
                NULL,
                :source,
                :captured_at,
                :evi,
                :vv,
                :vh,
                :vv_vh_ratio,
                :ndvi_trend
            )
            """
        )

        with self._engine.begin() as connection:
            for row in records:
                connection.execute(
                    statement,
                    {
                        "grid_id": row.grid_id,
                        "min_lon": row.min_lon,
                        "min_lat": row.min_lat,
                        "max_lon": row.max_lon,
                        "max_lat": row.max_lat,
                        "ndvi": row.ndvi,
                        "ndmi": row.ndmi,
                        "sar_ratio": row.vv_vh_ratio,
                        "evi": row.evi,
                        "vv": row.vv,
                        "vh": row.vh,
                        "vv_vh_ratio": row.vv_vh_ratio,
                        "ndvi_trend": row.ndvi_trend,
                        "source": row.source,
                        "captured_at": row.captured_at,
                    },
                )

        return len(records)
