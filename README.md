# Forest Intelligence Platform v0.1 Beta — All-Weather Forest Analytics

Forest Intelligence Platform is a map-driven analytics system that estimates forest metrics from satellite features and exposes them through a practical dashboard + API workflow.

It is designed to demonstrate geospatial system design, satellite feature engineering, and production-style backend/frontend integration—while remaining usable for real polygon analysis.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-blue.svg)](https://react.dev/)
[![PostGIS](https://img.shields.io/badge/PostGIS-16-blue.svg)](https://postgis.net/)

---

## 📋 Table of Contents

- 🚀 What This Project Does
- 🧠 How It Works (Simple Explanation)
- 📦 Download & Run
- 🧭 Main Commands
- 🧪 Typical First-Time Usage
- ⚙️ Requirements
- 🛡️ Reliability & Data Notes (Plain English)
- ✨ Features
- 🗂️ Repository Structure
- 👤 Author

---

# 🚀 What This Project Does

This project allows you to:

✅ Draw a polygon and receive forest analytics for that area

✅ Estimate tree density and tree count based on satellite-derived features

✅ Compute forest health and risk indicators

✅ View forecast trends and secondary analytics in one dashboard

✅ Run locally with FastAPI + React + PostGIS

---

# 🧠 How It Works (Simple Explanation)

At a high level:

🛰️ Sentinel features are prepared through ingestion + processing + extraction

🗺️ You draw a polygon on the map

📊 Backend computes area-scoped metrics from DB/features and ML utilities

🔄 Frontend polls pipeline status first, then requests metrics when ready

You do not need GIS expertise to use it—the dashboard coordinates this workflow for you.

---

# 📦 Download & Run

Step 1 — Clone and enter project

```bash
git clone https://github.com/HetMistri/forest.git
cd forest
```

Step 2 — Start backend

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Step 3 — Start frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

App URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend Docs: `http://127.0.0.1:8000/docs`

---

# 🧭 Main Commands

## Backend

- `uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`
- `uv run python main.py`
- `uv run pytest`

## Frontend

- `npm run dev`
- `npm run build`
- `npm run preview`

## Pipeline

- `python scripts/run_backend_pipeline.py`
- `cd backend && uv run python scripts/run_smoke_pipeline.py`

## Docker (Backend + PostGIS)

- `docker compose up --build`
- `docker compose down -v`

---

# 🧪 Typical First-Time Usage

1. Start backend and frontend
2. Open dashboard in browser
3. Draw polygon on map
4. Wait for pipeline status to become ready
5. Review forest metrics + forecast + risk outputs
6. Run smoke pipeline if polygon has no prepared features

---

# ⚙️ Requirements

To run locally:

🐍 Python 3.11+

📦 Node.js + npm

🗄️ PostgreSQL/PostGIS (or Docker compose service)

🛰️ Earth Engine credentials for full ingestion pipeline

---

# 🛡️ Reliability & Data Notes (Plain English)

- Metrics are model/data-derived estimates, not manual field census numbers.
- In strict mode, backend may return `503` when data is not yet available.
- `DEMO_CACHE_ENABLED` can return cached responses for known polygons.
- Best results require prepared feature data in `forest_features` for the selected area.

---

# ✨ Features

🌧️ All-weather oriented pipeline support (including SAR-driven features)

📉 Health and risk scoring from NDVI/NDMI/SAR summaries

📈 Forecast and secondary analytics endpoints

🧩 API + frontend integration with request logging and retry logic

🐳 Docker-ready local backend + PostGIS stack

---

# 🗂️ Repository Structure

```text
backend/                      FastAPI API + services + SQL + pipeline modules
frontend/                     React dashboard
backend/services/ml/          ML utilities (density, health/risk, forecast)
data/                         Raw/processed artifacts and metadata
scripts/                      Root pipeline runner
docker-compose.yml            Local PostGIS + backend services
README.md                     Main project guide
```

---

# 👤 Author

Het Mistri

LinkedIn: https://www.linkedin.com/in/het-mistri-7a52a533a/

GitHub: https://github.com/HetMistri

---

For module-level setup details, see:

- `backend/README.md`
- `frontend/README.md`
- `backend/services/ml/ml_README.md`
