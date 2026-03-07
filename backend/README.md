# Forest Backend v0.1 Beta — FastAPI Geospatial Analytics API

The backend is the core analytics service for polygon-based forest insights. It serves metrics APIs, coordinates data readiness checks, and connects to PostGIS for spatial computation.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)

---

## 📋 Table of Contents

- 🚀 What Backend Does
- 🧠 How It Works (Simple Explanation)
- 📦 Setup & Run
- 🧭 Main Commands
- 🧪 Typical First-Time Usage
- ⚙️ Requirements
- 🛡️ Reliability Notes
- ✨ Features
- 🔌 API Surface

---

# 🚀 What Backend Does

Backend provides:

✅ Polygon-driven forest metrics APIs

✅ Pipeline status checks (`/pipeline-status`)

✅ DB + feature-derived analytics flow

✅ Layer/utility endpoints for dashboard integration

✅ Strict-mode safeguards for unavailable real data

---

# 🧠 How It Works (Simple Explanation)

At a high level:

🗺️ Frontend sends polygon coordinates

🧮 Backend checks PostGIS functions and feature summaries

📊 If data exists, responses are computed and returned

🔄 If data is still preparing, status indicates processing

⚠️ In strict mode, unavailable real data can return `503`

---

# 📦 Setup & Run

Step 1 — Install dependencies and environment

```bash
uv sync
cp .env.example .env
```

Step 2 — Configure `.env`

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

Step 3 — Run API

```bash
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Alternative:

```bash
uv run python main.py
```

Docs:

- Swagger: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

---

# 🧭 Main Commands

- `uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`
- `uv run python main.py`
- `uv run pytest`
- `uv run python scripts/run_smoke_pipeline.py`

DB bootstrap (manual):

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

---

# 🧪 Typical First-Time Usage

1. Start local PostGIS (`docker compose up -d db` from repo root)
2. Bootstrap DB (`sql/bootstrap.sql`, auto in docker init)
3. Start backend server
4. Open `/docs` and test `/pipeline-status` and `/forest-metrics`
5. Run smoke pipeline if selected polygon has no data

---

# ⚙️ Requirements

🐍 Python 3.11+

🗄️ PostgreSQL/PostGIS

🛰️ Earth Engine credentials for ingestion workflows

📦 `uv` package manager (recommended)

---

# 🛡️ Reliability Notes

- `STRICT_PROD_MODE=true` avoids silent dummy responses when real data is missing.
- `DEMO_CACHE_ENABLED=true` allows cached polygon fallback responses.
- Pipeline processing may temporarily return `503` for metrics until data is ready.

---

# ✨ Features

🌲 Forest analytics endpoints for metrics, density, health, risk, species, forecast

📡 Pipeline-ready checks and request-triggered region pipeline support

🗃️ Spatial DB integration with PostGIS helper functions

🧪 Test suite for API contract and service-level behavior

---

# 🔌 API Surface

- `POST /forest-metrics`
- `POST /tree-density`
- `POST /health-score`
- `POST /risk-alerts`
- `POST /species-composition`
- `POST /health-forecast`
- `POST /pipeline-status`
- `GET /ndvi-map`
- `GET /risk-zones`
- `GET /system-status`
- `GET /demo-metrics`
