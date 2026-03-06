const DEFAULT_BASE = import.meta.env.DEV
  ? import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"
  : "/api";
const BASE = (import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE).replace(
  /\/$/,
  "",
);
const API_DEBUG =
  import.meta.env.DEV || import.meta.env.VITE_API_DEBUG === "true";

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

function toApiUrl(path: string): string {
  return `${BASE}${path}`;
}

function logRequest(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): number {
  const startedAt = Date.now();
  if (API_DEBUG) {
    console.log(
      `[forestApi] ${method} ${toApiUrl(path)} — request started`,
      body ?? "",
    );
  }
  return startedAt;
}

function logSuccess(
  method: "GET" | "POST",
  path: string,
  status: number,
  startedAt: number,
): void {
  if (API_DEBUG) {
    console.log(`[forestApi] ${method} ${toApiUrl(path)} — success`, {
      status,
      durationMs: Date.now() - startedAt,
    });
  }
}

function logWarning(
  method: "GET" | "POST",
  path: string,
  status: number,
  startedAt: number,
): void {
  console.warn(`[forestApi] ${method} ${toApiUrl(path)} — non-OK response`, {
    status,
    durationMs: Date.now() - startedAt,
  });
}

function logError(
  method: "GET" | "POST",
  path: string,
  startedAt: number,
  error: unknown,
): void {
  console.error(`[forestApi] ${method} ${toApiUrl(path)} — request failed`, {
    durationMs: Date.now() - startedAt,
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
  const startedAt = logRequest("POST", path, body);
  try {
    const res = await fetch(toApiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      logWarning("POST", path, res.status, startedAt);
      const detail = await parseErrorDetail(res);
      throw new Error(`API ${path} failed: ${detail}`);
    }
    logSuccess("POST", path, res.status, startedAt);
    return res.json() as Promise<T>;
  } catch (error) {
    logError("POST", path, startedAt, error);
    throw error;
  }
}

async function get<T>(path: string): Promise<T> {
  const startedAt = logRequest("GET", path);
  try {
    const res = await fetch(toApiUrl(path));
    if (!res.ok) {
      logWarning("GET", path, res.status, startedAt);
      const detail = await parseErrorDetail(res);
      throw new Error(`API ${path} failed: ${detail}`);
    }
    logSuccess("GET", path, res.status, startedAt);
    return res.json() as Promise<T>;
  } catch (error) {
    logError("GET", path, startedAt, error);
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

  // Layer endpoints
  getNDVIMap: () => get<NDVIMapResponse>("/ndvi-map"),
  getRiskZones: () => get<RiskZonesResponse>("/risk-zones"),

  // Utility
  getSystemStatus: () => get<SystemStatusResponse>("/system-status"),
};
