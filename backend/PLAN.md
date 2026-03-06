# Forest Intelligence Platform — Backend + Data Pipeline Master Plan (Dang District)

Owner: Backend + Data/ML team  
Scope: Backend services, geospatial database, and satellite-to-metrics pipeline only.  
Out of scope here: frontend implementation details except API dependencies.

---

## 1) Mission and Technical Differentiator

### Mission

Deliver reliable forest intelligence for Dang district from polygon input:

- tree density and total tree count
- forest health score
- deforestation risk alerts
- ecosystem composition
- 6-month health forecast

### Core Differentiator

Fuse optical + radar satellite signals for all-weather monitoring:

- Sentinel-2 (optical): NDVI, NDMI, EVI
- Sentinel-1 (SAR): VV, VH, VV/VH ratio

This removes dependence on clear-sky-only optical imagery and improves monsoon robustness.

---

## 2) Current Project Analysis (Backend + Pipeline)

### What is already implemented

1. FastAPI surface is in place with routers for:

- POST /forest-metrics
- POST /tree-density
- POST /health-score
- POST /risk-alerts
- POST /species-composition
- POST /health-forecast
- GET /ndvi-map
- GET /risk-zones
- GET /system-status
- GET /demo-metrics

2. API schemas enforce strict payloads and `[lon, lat]` polygon format.

3. Postgres/PostGIS bootstrap exists with:

- `forest_features`, `forest_metrics`, `species_composition`, `risk_alerts`, `demo_polygon_cache`
- spatial indexes + helper SQL functions (`get_forest_metrics`, `get_health_score`, etc.)

4. Polygon analytics flow exists:

- API -> `ForestMetricsService` -> SQL function aggregation -> JSON response
- DB fallback to ML/hardcoded defaults is present

5. Data pipeline components exist:

- Sentinel-2 downloader via Earth Engine
- NDVI/NDMI preprocessing
- feature extraction from rasters to grid cells and DB upsert

6. ML bridge exists:

- tree density inference (RandomForest model loading supported)
- health score, risk detection, forecast helper methods

7. Automated tests exist for API contracts and ML integration.

### Critical gaps vs final target system

1. Sentinel-1 ingestion is not yet implemented in ingestion pipeline.
2. EVI is not yet computed/stored in processing/features.
3. Feature table is not yet fully aligned with final fused schema (NDVI trend + SAR fields in serving path).
4. Health scoring weights in current ML helper are 0.7/0.3; final target is 0.6/0.4.
5. Region pipeline currently runs synchronously inside request flow; this can hurt API latency.
6. `species_distribution` key naming in fallback path is inconsistent (`mixed` vs `mixed_deciduous`).
7. Forecast serving currently relies on fallback/simple monthly projection if DB history is limited.

---

## 3) Final Target Backend System (Authoritative)

### Main analysis endpoint (core)

POST /forest-metrics

Request:
{
"polygon": [[lon, lat], [lon, lat], ...]
}

Response:
{
"area_km2": 5.1,
"tree_count": 84200,
"tree_density": 162,
"health_score": 68,
"risk_level": "Moderate",
"species_distribution": {
"teak": 58,
"bamboo": 27,
"mixed_deciduous": 15
},
"forecast_health": 64
}

### Full API map (target)

- POST /forest-metrics
- POST /tree-density
- POST /health-score
- POST /risk-alerts
- POST /species-composition
- POST /health-forecast
- GET /ndvi-map
- GET /risk-zones
- GET /system-status
- GET /demo-metrics

### Primary frontend dependency

- POST /forest-metrics
- GET /ndvi-map
- GET /risk-zones

---

## 4) Final Data Pipeline (Authoritative)

### Stage A: Data ingestion (Earth Engine)

Inputs:

- Sentinel-2 multispectral data (B4, B8, B11 + bands needed for EVI)
- Sentinel-1 SAR data (VV, VH)
- Dang district boundary (Bhuvan)

Outputs:

- clipped, time-filtered optical and SAR rasters / data cubes for Dang

### Stage B: Feature processing (hectare blocks)

For each hectare block:

- NDVI mean
- NDVI trend (short historical window)
- NDMI mean
- EVI mean
- VV mean
- VH mean
- VV/VH ratio

Output dataset key:

- `grid_id`

### Stage C: Tree density estimation

Model:

- RandomForestRegressor

Output:

- `tree_density_per_hectare`

Derived metric:

- `tree_count = tree_density_per_hectare * area_hectares`

### Stage D: Forest health score

Scoring rule:

- `health_score = (0.6 * NDVI + 0.4 * NDMI) * 100` (clamped 0..100)

Bands:

- 0–40 degraded
- 40–70 moderate
- 70–100 healthy

### Stage E: Risk detection

Rule:

- NDVI drop > 25% over short period -> hotspot alert

Output:

- risk zones + severity labels for mapping

### Stage F: Forecasting

Model:

- ARIMA or Prophet

Input:

- NDVI time series per region/block aggregate

Output:

- 6-month health projection

### Stage G: Species composition integration (no satellite species detection)

Source:

- Forest Survey of India + Bhuvan ecological data

Output format:
{
"teak": 58,
"bamboo": 27,
"mixed_deciduous": 15
}

---

## 5) Backend Architecture and Data Contracts

### FastAPI router structure

```
api/routers/
  forest_metrics.py
  density.py
  health.py
  risk.py
  species.py
  forecast.py
  layers.py
  system.py
```

### Service layer responsibilities

- `ForestMetricsService`: API orchestration and fallback policy
- SQL functions: polygon aggregation and risk/species/forecast retrieval
- region pipeline trigger: ingestion -> preprocess -> feature extract -> DB load

### Database contract (minimum)

`forest_features`

- `grid_id`, `geometry`
- `ndvi`, `ndmi`, `evi`
- `vv`, `vh`, `vv_vh_ratio`
- `captured_at`, `source`

`forest_metrics`

- `grid_id`, `geometry`
- `tree_density`, `health_score`, `risk_level`, `forecast_health`
- `metric_timestamp`, `model_version`

`species_composition`

- `grid_id`
- `teak`, `bamboo`, `mixed_deciduous`

---

## 6) Execution Plan (Backend + Data Pipeline Only)

## Phase 0 — Contract Freeze (1–2 hours)

Tasks:

1. Freeze exact request/response shapes for all 10 endpoints.
2. Confirm coordinate order is `[lon, lat]` everywhere.
3. Freeze field names (`mixed_deciduous`, `forecast_health`, etc.).

Done when:

- OpenAPI reflects frozen schema and frontend can integrate without assumption work.

## Phase 1 — Ingestion upgrade to fusion pipeline (4–6 hours)

Tasks:

1. Extend ingestion module for Sentinel-1 collection and export.
2. Keep existing Sentinel-2 flow and add EVI-supporting bands.
3. Standardize date windows and metadata logging for both sensors.

Done when:

- Raw outputs for Sentinel-1 + Sentinel-2 exist and are traceable by run metadata.

## Phase 2 — Feature engineering at hectare level (4–6 hours)

Tasks:

1. Add EVI computation in preprocess.
2. Add SAR feature extraction (VV, VH, VV/VH).
3. Add NDVI trend computation over recent temporal slices.
4. Emit unified feature rows keyed by deterministic `grid_id`.

Done when:

- Features table contains fused optical+radar predictors per hectare block.

## Phase 3 — Model and metric generation alignment (5–7 hours)

Tasks:

1. Keep RandomForestRegressor for tree density with fused predictors.
2. Align health formula to 0.6 NDVI / 0.4 NDMI.
3. Keep rule-based risk: NDVI drop > 25%.
4. Produce 6-month forecast from ARIMA/Prophet pipeline.
5. Publish DB-ready metrics by `grid_id`.

Done when:

- Each `grid_id` has density, health, risk, and forecast metrics with bounded values.

## Phase 4 — Database and SQL aggregation hardening (3–4 hours)

Tasks:

1. Update schema for missing fused columns where needed.
2. Keep spatial indexes and idempotent upserts.
3. Validate SQL aggregate functions for polygon intersections.
4. Add/verify risk and forecast query paths with realistic test fixtures.

Done when:

- Polygon queries are correct and performant for demo-size polygons.

## Phase 5 — Service/API hardening (4 hours)

Tasks:

1. Keep `/forest-metrics` as single source of dashboard truth.
2. Ensure fallback responses use contract-consistent keys.
3. Decouple heavy region pipeline work from synchronous request path where possible.
4. Validate all endpoint contracts through tests.

Done when:

- APIs are contract-stable, predictable, and demo-safe.

## Phase 6 — Demo reliability path (1–2 hours)

Tasks:

1. Cache precomputed Dang demo polygon response.
2. Return cached values instantly for exact demo geometry.
3. Keep fallback path safe if external services fail.

Demo target payload:

- Area: 5.1 km²
- Estimated Trees: 84,200
- Density: 162 trees/hectare
- Health Score: 68
- Risk Zones: 2
- Species mix: teak/bamboo dominant

Done when:

- Demo route is deterministic and fast under unstable network conditions.

---

## 7) Priority Rule (Strict)

No new features after core pipeline works.

Execution order:

1. Dashboard-driving backend path working (`/forest-metrics` + layers)
2. Tree density + health metrics
3. Risk detection
4. Forecast
5. Demo polish and pitch support

Working product > ambitious unfinished scope.

---

## 8) Validation and Acceptance Checklist

### Functional

- Polygon query returns area, trees, density, health, risk, species, forecast.
- Supporting endpoints return subset/layer data correctly.
- Species endpoint uses external ecological sources, not image-level species classification.

### Data quality

- All numeric outputs bounded and unit-consistent.
- Hectare aggregation is deterministic for same inputs.
- Risk rule triggers only on configured NDVI drop threshold.

### Reliability

- DB unavailable -> graceful fallback path.
- External satellite query unavailable -> cached/demo response still works.
- API contracts protected by tests.

---

## 9) Immediate Backend + Pipeline Action Items

1. Lock frozen schema and update any inconsistent response keys.
2. Implement Sentinel-1 ingestion branch and fused feature output.
3. Add EVI + NDVI trend to preprocessing/feature extraction.
4. Align health score formula to 0.6/0.4 in ML logic.
5. Ensure `/forest-metrics` returns `forecast_health` in core response path.
6. Add one end-to-end test for polygon -> SQL aggregate -> API response using seeded Dang fixture.
7. Finalize demo polygon cache and verify instant response path.
