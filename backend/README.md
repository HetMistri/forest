# Backend

FastAPI backend for forest analytics, with environment-based config and PostgreSQL/PostGIS connectivity.

## 1) Setup

```bash
uv sync
cp .env.example .env
```

Update `.env` with your Render external DB URL using SQLAlchemy format:

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
STRICT_PROD_MODE=true
DEMO_CACHE_ENABLED=false
REGION_PIPELINE_TRIGGER_ON_REQUEST=true
INGESTION_INTERACTIVE_AUTH=false
GEE_PROJECT=<gcp-project-id>
GEE_SERVICE_ACCOUNT=<service-account>@<project>.iam.gserviceaccount.com
GEE_PRIVATE_KEY_FILE=/absolute/path/to/service-account-key.json
```

When `STRICT_PROD_MODE=true`, endpoints return `503` if real DB/pipeline data is unavailable (no dummy/static fallback).

## 2) Run server

```bash
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

or

```bash
uv run python main.py
```

## 3) Access API

- Swagger: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

## 4) API surface

- POST `/forest-metrics`
- POST `/tree-density`
- POST `/health-score`
- POST `/risk-alerts`
- POST `/species-composition`
- POST `/health-forecast`
- GET `/ndvi-map`
- GET `/risk-zones`
- GET `/system-status`
- GET `/demo-metrics`

## 5) Database bootstrap

SQL scaffold is in `sql/bootstrap.sql` and creates:

- PostGIS + pgcrypto extensions
- Core tables (`forest_features`, `forest_metrics`, `species_composition`, `risk_alerts`, `demo_polygon_cache`)
- Indexes, update triggers, views, and stored functions for aggregation

Apply with:

```bash
uv run python - <<'PY'
from pathlib import Path
from api.db import get_engine

engine = get_engine()
script = Path('sql/bootstrap.sql').read_text()

with engine.raw_connection() as raw:
	with raw.cursor() as cur:
		cur.execute(script)
	raw.commit()

print('Bootstrap applied')
PY
```

## 6) Docker local stack (PostGIS + Backend)

From repository root:

```bash
docker compose up --build
```

Services:

- Backend API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Local PostGIS: `localhost:5433`

Notes:

- `docker-compose.yml` uses local PostGIS (`postgis/postgis`) and mounts `backend/sql/bootstrap.sql` into `/docker-entrypoint-initdb.d/`.
- Bootstrap runs automatically on first DB initialization.
- The container backend uses local DB URL, so remote `DATABASE_URL` latency is avoided.
- To reset DB and re-run bootstrap from scratch:

```bash
docker compose down -v
docker compose up --build
```

## 7) Backend smoke pipeline (download -> processing -> DB)

Use local Docker PostGIS (fast, no remote DB latency):

```bash
cd ..
docker compose up -d db
```

Then run from `backend/`:

```bash
DATABASE_URL=postgresql+psycopg://forest:forest@127.0.0.1:5433/forest_local \
uv run python scripts/run_smoke_pipeline.py
```

This executes:

- Sentinel-2 download from Earth Engine (small smoke bbox)
- NDVI/NDMI/EVI preprocessing
- Feature extraction and insert into `forest_features`
- Row-count verification for smoke source
