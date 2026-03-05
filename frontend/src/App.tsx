import { useMemo, useState } from "react";
import { fetchForestMetrics, type ForestMetricsResponse } from "./api";
import "./App.css";

const DEFAULT_POLYGON = [
  [73.9, 20.2],
  [73.91, 20.2],
  [73.91, 20.21],
  [73.9, 20.2],
];

function App() {
  const [polygonText, setPolygonText] = useState(
    JSON.stringify(DEFAULT_POLYGON),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<ForestMetricsResponse | null>(null);

  const prettySpecies = useMemo(() => {
    if (!metrics) {
      return [];
    }
    return Object.entries(metrics.species_distribution);
  }, [metrics]);

  const handleRun = async () => {
    setError(null);

    let parsedPolygon: number[][];
    try {
      parsedPolygon = JSON.parse(polygonText) as number[][];
    } catch {
      setError(
        "Polygon must be valid JSON. Example: [[73.9,20.2],[73.91,20.2],[73.91,20.21],[73.9,20.2]]",
      );
      return;
    }

    setLoading(true);
    try {
      const response = await fetchForestMetrics({ polygon: parsedPolygon });
      setMetrics(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Request failed",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container">
      <h1>Forest Analytics Dashboard (Backend Integration)</h1>

      <section className="card">
        <label htmlFor="polygon">Polygon coordinates (JSON)</label>
        <textarea
          id="polygon"
          rows={6}
          value={polygonText}
          onChange={(event) => setPolygonText(event.target.value)}
        />
        <button onClick={handleRun} disabled={loading}>
          {loading ? "Loading..." : "Run /forest-metrics"}
        </button>
        {error ? <p className="error">{error}</p> : null}
      </section>

      {metrics ? (
        <section className="card results">
          <h2>Metrics</h2>
          <p>Area (km²): {metrics.area_km2}</p>
          <p>Tree count: {metrics.tree_count}</p>
          <p>Tree density: {metrics.tree_density}</p>
          <p>Health score: {metrics.health_score}</p>
          <p>Risk level: {metrics.risk_level}</p>

          <h3>Species distribution</h3>
          <ul>
            {prettySpecies.map(([name, value]) => (
              <li key={name}>
                {name}: {value}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}

export default App;
