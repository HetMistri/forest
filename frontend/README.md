# Frontend (React + Vite)

Dashboard UI for the Forest Intelligence Platform.

## Setup

```bash
npm install
cp .env.example .env
```

## Run (dev)

```bash
npm run dev
```

Default URL: `http://127.0.0.1:5173`

## Backend Integration

Frontend API client is in `src/utils/forestApi.ts` and expects these backend routes:

- `POST /forest-metrics`
- `POST /tree-density`
- `POST /health-score`
- `POST /risk-alerts`
- `POST /species-composition`
- `POST /health-forecast`
- `GET /ndvi-map`
- `GET /risk-zones`
- `GET /system-status`
- `GET /demo-metrics`

### Environment variables

- `VITE_API_BASE_URL` (default `/api`)
- `VITE_BACKEND_URL` (default `http://localhost:8000`) for Vite dev proxy
- `VITE_MAPBOX_TOKEN`

## Build

```bash
npm run build
npm run preview
```

## Notes

- `npm run dev` uses `node ./node_modules/vite/bin/vite.js` to avoid executable-bit issues on systems where `.bin/vite` loses `+x` permission.
- If backend runs in Docker at `localhost:8000`, no frontend code changes are needed.
