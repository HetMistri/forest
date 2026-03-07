# Forest Intelligence Platform

Smart forest monitoring prototype for district-scale geospatial analytics using satellite data fusion.

This repository combines:

- A **FastAPI backend** for forest metrics, health/risk analytics, and pipeline status APIs
- A **React + Vite frontend** for polygon-based interactive dashboard analysis
- A **satellite data pipeline** for ingestion, preprocessing, and feature extraction
- A **PostgreSQL + PostGIS data layer** for spatial querying and metric aggregation

---

## Table of Contents

1. [What this project does](#what-this-project-does)
2. [System architecture](#system-architecture)
3. [Repository structure](#repository-structure)
4. [API surface](#api-surface)
5. [Run modes](#run-modes)
6. [Configuration](#configuration)
7. [Technology stack](#technology-stack)
8. [Known implementation notes](#known-implementation-notes)

---

## What this project does

Forest Intelligence Platform provides end-to-end forest analytics for user-drawn polygons:

- **Draw polygon on map** to request area-scoped analysis
- **Estimate tree density and tree count** from satellite-derived features
- **Compute health score and risk level** using NDVI/NDMI + SAR indicators
- **Return species composition** and short-term health forecast
- **Track pipeline state** so the frontend can wait while data is being prepared

The core focus is all-weather monitoring by combining optical and radar signals.

---

## System architecture

### 1) Frontend (`frontend/`)

- React 19 + Vite + TypeScript
- Leaflet map with polygon drawing workflow
- Dashboard components for metrics, forecast, alerts, and KPIs
- API client in `frontend/src/utils/forestApi.ts`
- Default local app URL: `http://127.0.0.1:5173`

### 2) Backend (`backend/`)

- FastAPI application (`api.main:app`)
- Router-based endpoints for metrics, density, health, species, forecast, layers, and system status
- Service layer (`services/forest_metrics_service.py`) with DB-first and feature-derived fallback flow
- Optional on-request region pipeline trigger for missing polygon data
- Swagger docs at `/docs`

### 3) Data Pipeline (`backend/ingestion`, `backend/processing`, `backend/features`)

- **Ingestion:** Sentinel composite download (Earth Engine)
- **Processing:** NDVI/NDMI/EVI and SAR preprocessing
- **Feature extraction:** tabular feature generation + optional DB writes
- Pipeline entry points:
  - `scripts/run_backend_pipeline.py` (repo root)
  - `backend/scripts/run_smoke_pipeline.py`

### 4) Spatial Database (`docker-compose.yml`, `backend/sql/bootstrap.sql`)

- PostgreSQL + PostGIS
- Spatial tables/functions for polygon intersection and aggregate metrics
- Bootstrap SQL creates required extensions, tables, and helper functions

---

## Repository structure

```text
backend/                 FastAPI API + services + pipeline modules + SQL
frontend/                React SPA dashboard
data/                    Raw/processed outputs and metadata artifacts
scripts/                 Root automation scripts (pipeline runner)
docker-compose.yml       Local PostGIS + backend runtime stack
README.md                Main project documentation
```

---

## API surface

### Core analytics endpoints

- `POST /forest-metrics`
- `POST /tree-density`
- `POST /health-score`
- `POST /risk-alerts`
- `POST /species-composition`
- `POST /health-forecast`

### Pipeline and utility endpoints

- `POST /pipeline-status`
- `GET /system-status`
- `GET /demo-metrics`

### Layer endpoints

- `GET /ndvi-map`
- `GET /risk-zones`

---

## Run modes

### Local development (backend + frontend)

#### 1) Start backend

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend URLs:

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

#### 2) Start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- App: `http://127.0.0.1:5173`

#### 3) Optional: run pipeline manually

From repo root:

```bash
python scripts/run_backend_pipeline.py
```

Or smoke pipeline from `backend/`:

```bash
uv run python scripts/run_smoke_pipeline.py
```

### Docker runtime (local PostGIS + backend)

From repo root:

```bash
docker compose up --build
```

Services:

- backend: `8000`
- postgis: `5433`

To reset DB volume and re-bootstrap:

```bash
docker compose down -v
docker compose up --build
```

---

## Configuration

### Backend env file

- Template: `backend/.env.example`
- Active local file: `backend/.env`

Important keys:

- `DATABASE_URL`
- `STRICT_PROD_MODE`
- `DEMO_CACHE_ENABLED`
- `REGION_PIPELINE_ENABLED`
- `REGION_PIPELINE_TRIGGER_ON_REQUEST`
- `REGION_PIPELINE_MIN_INTERVAL_SEC`
- `INGESTION_INTERACTIVE_AUTH`
- `GEE_PROJECT`
- `GEE_SERVICE_ACCOUNT`
- `GEE_PRIVATE_KEY_FILE`

### Frontend env keys

- `VITE_API_BASE_URL` (default `/api`)
- `VITE_BACKEND_URL` (default `http://localhost:8000` in dev)
- `VITE_MAPBOX_TOKEN`

---

## Technology stack

### Backend and pipeline

- FastAPI + Uvicorn
- SQLAlchemy + Psycopg
- GeoAlchemy2 + PostGIS
- Earth Engine API
- Pandas / NumPy / scikit-learn
- Rasterio / Shapely

### Frontend

- React 19 + TypeScript
- Vite
- Leaflet + React-Leaflet + Leaflet Draw
- Chart.js / React-Chartjs-2

### Infra

- Docker Compose
- PostGIS container (`postgis/postgis`)

---

## Known implementation notes

1. Frontend uses pipeline-first polling for polygon analysis and only requests metrics once pipeline status is not `processing`.
2. In strict mode, endpoints can return `503` when real data is unavailable instead of silently returning dummy values.
3. `DEMO_CACHE_ENABLED` controls whether cached polygon responses are allowed as a fallback path.
4. API behavior depends on spatial data readiness (`forest_features`) and pipeline configuration in backend `.env`.

---

For component-specific details, see:

- `backend/README.md`
- `frontend/README.md`
