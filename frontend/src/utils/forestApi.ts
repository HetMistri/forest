import { createLogger } from "./logger";

const DEFAULT_BASE = import.meta.env.DEV
  ? import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"
  : "/api";
const BASE = (import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE).replace(
  /\/$/,
  "",
);
const API_DEBUG =
  import.meta.env.DEV || import.meta.env.VITE_API_DEBUG === "true";
const logger = createLogger("forestApi");

logger.info("API client initialized", {
  baseUrl: BASE,
  debug: API_DEBUG,
  mode: import.meta.env.MODE,
});

function createRequestId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

interface RequestMeta {
  startedAt: number;
  requestId: string;
}

export interface PolygonRequest {
  polygon: [number, number][];
}

export interface ForestMetricsResponse {
  area_km2: number;
  tree_count: number;
  tree_density: number;
  health_score: number;
  risk_level: string;
  species_distribution: Record<string, number>;
  forecast_health?: number;
  ndvi_avg?: number;
  ndmi_avg?: number;
}

export interface HealthForecastResponse {
  forecast: { month: string; health_score: number }[];
}

export interface RiskAlertsResponse {
  risk_level: string;
  alerts: { type: string; severity: string; location: [number, number] }[];
}

export interface TreeDensityResponse {
  tree_density: number;
  total_trees: number;
}

export interface HealthScoreResponse {
  health_score: number;
  ndvi_avg: number;
  ndmi_avg: number;
}

export interface SpeciesCompositionResponse {
  [species: string]: number;
}

export interface NDVIMapResponse {
  tile_url?: string;
  geojson?: unknown;
}

export interface RiskZonesResponse {
  zones: { risk: string; geometry: unknown }[];
}

export interface SystemStatusResponse {
  satellite_data_loaded: boolean;
  feature_dataset_rows: number;
  model_status: string;
}

export interface ActionPlanRequest {
  tree_count: number;
  tree_density: number;
  health_score: number;
  risk_level: string;
  species_distribution: Record<string, number>;
}

export interface ActionPlanResponse {
  guidelines_markdown: string;
}

export interface PipelineStatusResponse {
  status: "processing" | "ready" | "unavailable";
  in_progress: boolean;
  has_feature_data: boolean;
  detail: string;
}

function toApiUrl(path: string): string {
  return `${BASE}${path}`;
}

function logRequest(
  method: "GET" | "POST",
  path: string,
  requestId: string,
  body?: unknown,
): RequestMeta {
  const startedAt = Date.now();
  if (API_DEBUG) {
    logger.info(`${method} request started`, {
      path,
      url: toApiUrl(path),
      requestId,
      body: body ?? null,
      startedAt,
    });
  }
  return { startedAt, requestId };
}

function logSuccess(
  method: "GET" | "POST",
  path: string,
  status: number,
  meta: RequestMeta,
): void {
  if (API_DEBUG) {
    logger.info(`${method} request success`, {
      path,
      url: toApiUrl(path),
      requestId: meta.requestId,
      status,
      durationMs: Date.now() - meta.startedAt,
    });
  }
}

function logWarning(
  method: "GET" | "POST",
  path: string,
  status: number,
  meta: RequestMeta,
): void {
  logger.warn(`${method} non-OK response`, {
    path,
    url: toApiUrl(path),
    requestId: meta.requestId,
    status,
    durationMs: Date.now() - meta.startedAt,
  });
}

function logError(
  method: "GET" | "POST",
  path: string,
  meta: RequestMeta,
  error: unknown,
): void {
  logger.error(`${method} request failed`, {
    path,
    url: toApiUrl(path),
    requestId: meta.requestId,
    durationMs: Date.now() - meta.startedAt,
    error,
  });
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const payload = (await res.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch (error) {
    void error;
  }

  try {
    const text = await res.text();
    if (text.trim()) {
      return text;
    }
  } catch (error) {
    void error;
  }

  return `HTTP ${res.status}`;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const requestId = createRequestId();
  const meta = logRequest("POST", path, requestId, body);
  try {
    const res = await fetch(toApiUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      logWarning("POST", path, res.status, meta);
      const detail = await parseErrorDetail(res);
      throw new Error(`API ${path} failed: ${detail}`);
    }
    logSuccess("POST", path, res.status, meta);
    return res.json() as Promise<T>;
  } catch (error) {
    logError("POST", path, meta, error);
    throw error;
  }
}

async function get<T>(path: string): Promise<T> {
  const requestId = createRequestId();
  const meta = logRequest("GET", path, requestId);
  try {
    const res = await fetch(toApiUrl(path), {
      headers: { "X-Request-ID": requestId },
    });
    if (!res.ok) {
      logWarning("GET", path, res.status, meta);
      const detail = await parseErrorDetail(res);
      throw new Error(`API ${path} failed: ${detail}`);
    }
    logSuccess("GET", path, res.status, meta);
    return res.json() as Promise<T>;
  } catch (error) {
    logError("GET", path, meta, error);
    throw error;
  }
}

export const forestApi = {
  // Core analysis
  getForestMetrics: (polygon: [number, number][]) =>
    post<ForestMetricsResponse>("/forest-metrics", { polygon }),

  // Specific analytics
  getTreeDensity: (polygon: [number, number][]) =>
    post<TreeDensityResponse>("/tree-density", { polygon }),

  getHealthScore: (polygon: [number, number][]) =>
    post<HealthScoreResponse>("/health-score", { polygon }),

  getRiskAlerts: (polygon: [number, number][]) =>
    post<RiskAlertsResponse>("/risk-alerts", { polygon }),

  getSpeciesComposition: (polygon: [number, number][]) =>
    post<SpeciesCompositionResponse>("/species-composition", { polygon }),

  getHealthForecast: (polygon: [number, number][]) =>
    post<HealthForecastResponse>("/health-forecast", { polygon }),

  getActionPlan: (req: ActionPlanRequest) =>
    post<ActionPlanResponse>("/action-plan", req),

  // Layer endpoints
  getNDVIMap: () => get<NDVIMapResponse>("/ndvi-map"),
  getRiskZones: () => get<RiskZonesResponse>("/risk-zones"),

  // Utility
  getSystemStatus: () => get<SystemStatusResponse>("/system-status"),
  getPipelineStatus: (polygon: [number, number][]) =>
    post<PipelineStatusResponse>("/pipeline-status", { polygon }),
};
