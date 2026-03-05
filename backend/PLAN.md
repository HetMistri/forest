# Forest Intelligence Platform — Backend + Data Pipeline Plan

Owner: Backend Engineer (also Data & ML Pipeline)
Scope: Deliver reliable polygon-based forest analytics for Dang district with production-safe demo behavior.
git 
## 1) Goals and Non-Negotiables

### Primary Goal
Enable a live flow where a user draws/selects a polygon and receives instant analytics:
- tree_count
- tree_density
- health_score
- risk_level
- species_distribution

### Fixed Core Contract (lock first)
Endpoint: POST /forest-metrics

Request
{
  "polygon": [[lon, lat], [lon, lat], ...]
}

Response
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
  }
}

### Guardrails
- Working product > new features.
- Keep coordinate convention consistent: [lon, lat] across FE, API, DB.
- No last-minute schema changes after integration freeze.

---

## 2) Architecture Responsibilities (Your Scope)

### Data & ML Responsibilities
- Ingest Sentinel-based raster inputs for Dang (NDVI, NDMI first).
- Convert raster to hectare-level feature table.
- Produce model metrics per grid cell:
  - tree_density
  - health_score
  - risk_level
  - optional forecast_health
- Publish outputs in DB-ready format keyed by grid_id.

### Backend Responsibilities
- Maintain PostGIS schema + aggregation functions.
- Build and harden API/service layer.
- Support demo-cache fast path for pitch reliability.
- Expose stable endpoints for frontend and integration tests.

---

## 3) Work Breakdown Structure (Backend + Data)

## Phase A — API Contract Lock + Repo Baseline (1–2 hours)

Tasks
- Freeze JSON contract for POST /forest-metrics.
- Confirm polygon convention ([lon, lat]) in docs and schema validation.
- Freeze supporting endpoint payload shapes.

Deliverables
- Signed contract in backend README or API docs.
- OpenAPI checked and shared with frontend.

Acceptance Criteria
- Frontend can integrate without guessing fields.
- No breaking contract changes afterward.

---

## Phase B — Data Ingestion (4 hours)

Inputs
- Dang district boundary (Bhuvan/authoritative boundary source).
- Satellite-derived layers (NDVI/NDMI raster exports).

Tasks
- Prepare ingestion script structure under ingestion/.
- Load boundary geometry and align CRS.
- Validate raster bounds overlap Dang boundary.
- Export/store raw layers under data/raw/.

Expected Artifacts
- data/raw/ndvi.tif
- data/raw/ndmi.tif

Acceptance Criteria
- Rasters readable, georeferenced, and clipped/usable for Dang.
- Metadata logged (date range, source, CRS, resolution).

---

## Phase C — Feature Extraction to Grid (4 hours)

Tasks
- Define hectare grid strategy and stable grid_id generation.
- Compute grid-level features from raster:
  - ndvi
  - ndmi
  - centroid lat/lon
- Save features table for backend load.

Expected Artifact
- data/processed/features.csv
  - grid_id, lat, lon, ndvi, ndmi

Acceptance Criteria
- No null/invalid index values beyond expected sparse edges.
- grid_id is deterministic across reruns.

---

## Phase D — ML & Metric Generation (5–6 hours)

Tasks
- Tree Density Model
  - Train/use RandomForestRegressor with ndvi/ndmi (+ optional SAR when available).
- Health Scoring
  - Apply: health = 0.6 * NDVI + 0.4 * NDMI.
  - Scale to 0–100.
- Risk Detection
  - Flag high risk if NDVI drop > 25% in short window.
- Forecast
  - Prophet-based NDVI trend projection.
- Export metrics keyed by grid_id.

Expected Artifact (DB-ready)
- grid_id, tree_density, health_score, risk_level, forecast_health

Acceptance Criteria
- Values constrained to expected ranges.
- Repeatable inference output for same input snapshot.

---

## Phase E — Database Layer (3 hours)

Tasks
- Validate and finalize tables:
  - forest_features (grid_id, geometry, ndvi, ndmi)
  - forest_metrics (grid_id, tree_density, health_score, risk_level, forecast_health)
- Ensure spatial indexes and helper SQL functions are working.
- Implement idempotent upsert paths for feature/metric loads.

Acceptance Criteria
- Polygon intersection queries run with acceptable latency.
- Upserts can be rerun safely.

---

## Phase F — Backend Services & Endpoints (4 hours)

Tasks
- Finalize ForestMetricsService aggregation logic:
  - polygon -> intersecting cells -> aggregate -> response
- Validate supporting endpoints:
  - POST /forest-metrics
  - POST /tree-density
  - POST /health-score
  - POST /risk-alerts
  - POST /species-composition
  - GET /ndvi-map
  - GET /risk-zones
- Enforce response schema strictness.

Acceptance Criteria
- Endpoints return contract-compliant JSON.
- Invalid polygon payloads fail with clear validation errors.

---

## Phase G — Demo Cache Reliability (1 hour)

Tasks
- Seed fixed demo polygon cache entry (Dang).
- Add fast-path return for exact demo polygon match.
- Ensure response matches pitch-safe values and is instantaneous.

Acceptance Criteria
- Demo call succeeds without external dependencies.
- Stable response under network/API failures.

---

## Phase H — Integration with Frontend (6 hours shared)

Your Focus
- Verify API calls from frontend map flow.
- Confirm coordinate ordering and polygon closure behavior.
- Validate payloads consumed by dashboard panels.

End-to-End Test Flow
draw polygon -> frontend POST /forest-metrics -> backend aggregates -> JSON response -> dashboard update

Acceptance Criteria
- End-to-end succeeds repeatedly with no manual patching.
- Response time acceptable for demo.

---

## 4) Day-wise Timeline (Backend + Data Focus)

Day 1
- 0–2h: Contract lock + schema alignment
- 2–6h: Ingestion setup and raw raster handling
- 6–10h: Feature extraction to hectare grid
- 10–16h: Model/metric generation and DB upsert path

Day 2
- 16–20h: Service hardening + endpoint validation
- 20–24h: Integration testing with frontend
- 24–30h: Forecast/risk refinements (only if core stable)
- 30–36h: Demo cache hardening + test runbooks
- 36–48h: Reliability pass, bug fixes, presentation support

---

## 5) Definition of Done (for Your Ownership)

- Data pipeline produces reproducible features/metrics for Dang.
- PostGIS stores and serves polygon-based aggregates correctly.
- POST /forest-metrics is stable and contract-compliant.
- Supporting endpoints are functional and validated.
- Demo polygon returns fast, deterministic output.
- Automated tests pass for API contract and service logic.

---

## 6) Risk Register + Mitigations

Risk: Coordinate order mismatch ([lat, lon] vs [lon, lat])
- Mitigation: enforce [lon, lat] in schema/docs/tests.

Risk: Data ingestion delays or missing satellite exports
- Mitigation: keep seeded dataset + demo cache fallback.

Risk: Slow spatial queries
- Mitigation: GIST indexes, pre-aggregation, bounded polygon area for demo.

Risk: Last-minute feature creep
- Mitigation: freeze scope after core flow passes integration.

---

## 7) Immediate Next Actions (Start Now)

1. Lock and publish final /forest-metrics contract with frontend teammate.
2. Implement/verify ingestion script skeleton and feature CSV pipeline.
3. Validate DB bootstrap + upsert routines with sample Dang cells.
4. Run full API tests and add one end-to-end polygon aggregation test with seeded data.
5. Seed demo polygon cache and smoke-test presentation path.
