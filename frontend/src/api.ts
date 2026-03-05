export type ForestMetricsRequest = {
  polygon: number[][];
};

export type ForestMetricsResponse = {
  area_km2: number;
  tree_count: number;
  tree_density: number;
  health_score: number;
  risk_level: string;
  species_distribution: Record<string, number>;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchForestMetrics(
  payload: ForestMetricsRequest,
): Promise<ForestMetricsResponse> {
  const response = await fetch(`${API_BASE_URL}/forest-metrics`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed (${response.status}): ${text}`);
  }

  return (await response.json()) as ForestMetricsResponse;
}
