const BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

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

export interface DemoMetricsResponse {
  tree_count: number;
  health_score: number;
  risk: string;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const forestApi = {
  // Core analysis
  getForestMetrics: (polygon: [number, number][]) =>
    post<ForestMetricsResponse>('/forest-metrics', { polygon }),

  // Specific analytics
  getTreeDensity: (polygon: [number, number][]) =>
    post<TreeDensityResponse>('/tree-density', { polygon }),

  getHealthScore: (polygon: [number, number][]) =>
    post<HealthScoreResponse>('/health-score', { polygon }),

  getRiskAlerts: (polygon: [number, number][]) =>
    post<RiskAlertsResponse>('/risk-alerts', { polygon }),

  getSpeciesComposition: (polygon: [number, number][]) =>
    post<SpeciesCompositionResponse>('/species-composition', { polygon }),

  getHealthForecast: (polygon: [number, number][]) =>
    post<HealthForecastResponse>('/health-forecast', { polygon }),

  // Layer endpoints
  getNDVIMap: () => get<NDVIMapResponse>('/ndvi-map'),
  getRiskZones: () => get<RiskZonesResponse>('/risk-zones'),

  // Utility
  getSystemStatus: () => get<SystemStatusResponse>('/system-status'),
  getDemoMetrics: () => get<DemoMetricsResponse>('/demo-metrics'),
};
