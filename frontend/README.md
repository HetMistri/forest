# Forest Frontend v0.1 Beta — React Dashboard

The frontend is an interactive geospatial dashboard where users draw polygons and inspect forest metrics, health trends, and risk outputs.

[![React](https://img.shields.io/badge/React-19-blue.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-7-purple.svg)](https://vitejs.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)

---

## 📋 Table of Contents

- 🚀 What Frontend Does
- 🧠 How It Works (Simple Explanation)
- 📦 Setup & Run
- 🧭 Main Commands
- 🧪 Typical First-Time Usage
- ⚙️ Requirements
- 🛡️ Reliability Notes
- ✨ Features
- 🔌 Backend API Integration

---

# 🚀 What Frontend Does

Frontend allows users to:

✅ Draw polygon regions on a map

✅ Request forest analysis for selected area

✅ See metrics (area, tree count, health, risk)

✅ View secondary analytics (forecast, species, alerts, density)

✅ Track backend pipeline status during analysis

---

# 🧠 How It Works (Simple Explanation)

At a high level:

🗺️ User draws polygon

🔄 Frontend polls `/pipeline-status`

📊 Once ready, frontend requests `/forest-metrics`

⚡ Then it fetches secondary analytics in parallel

All this is handled from the dashboard flow without manual API calls.

---

# 📦 Setup & Run

```bash
npm install
cp .env.example .env
npm run dev
```

Default URL: `http://127.0.0.1:5173`

---

# 🧭 Main Commands

- `npm run dev`
- `npm run build`
- `npm run preview`
- `npm run lint`

---

# 🧪 Typical First-Time Usage

1. Start backend on `http://127.0.0.1:8000`
2. Run frontend dev server
3. Open dashboard in browser
4. Draw a polygon
5. Wait for status and review analytics

---

# ⚙️ Requirements

🟩 Node.js + npm

🌐 Running backend API (`localhost:8000` by default)

🗺️ Optional map token in `.env` (`VITE_MAPBOX_TOKEN`)

---

# 🛡️ Reliability Notes

- Frontend treats temporary `503`/network issues as retryable during analysis.
- Current flow is pipeline-status-first to avoid immediate metrics failures while processing.
- Production base URL can be configured using `VITE_API_BASE_URL`.

---

# ✨ Features

📍 Polygon-based interactive analysis

📈 KPI, forecast, risk, and species presentation

🧾 API request logging support for debugging

⚙️ TypeScript + modular component architecture

---

# 🔌 Backend API Integration

Client location: `src/utils/forestApi.ts`

Expected endpoints:

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

Environment variables:

- `VITE_API_BASE_URL` (default `/api`)
- `VITE_BACKEND_URL` (default `http://localhost:8000` in dev)
- `VITE_MAPBOX_TOKEN`
