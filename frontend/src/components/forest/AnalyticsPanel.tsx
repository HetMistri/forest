import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";
import type {
  ForestMetricsResponse,
  HealthForecastResponse,
  HealthScoreResponse,
  SpeciesCompositionResponse,
} from "../../utils/forestApi";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

const PURPLE = "#401c86";
const NAVY = "#020f50";

const SPECIES_COLORS: Record<string, string> = {
  teak: "#401c86",
  bamboo: "#0693e3",
  mixed_deciduous: "#22c55e",
  sal: "#f59e0b",
  tectona: "#ef4444",
  mixed: "#8b5cf6",
};

interface Props {
  metrics: ForestMetricsResponse | null;
  forecast: HealthForecastResponse | null;
  healthScore: HealthScoreResponse | null;
  species: SpeciesCompositionResponse | null;
  loading: boolean;
  error: string | null;
}

function HealthBar({ score }: { score: number }) {
  const color = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";
  const label =
    score >= 70 ? "Healthy" : score >= 40 ? "Moderate Stress" : "Degraded";
  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 5,
          fontSize: 12,
        }}
      >
        <span style={{ color: "#6b7280" }}>Forest Health</span>
        <span style={{ fontWeight: 700, color }}>
          {score}/100 — {label}
        </span>
      </div>
      <div style={{ background: "#e5e7eb", borderRadius: 6, height: 9 }}>
        <div
          style={{
            width: `${score}%`,
            background: color,
            borderRadius: 6,
            height: "100%",
            transition: "width 0.6s ease",
          }}
        />
      </div>
    </div>
  );
}

function Stat({
  icon,
  value,
  label,
  color = NAVY,
}: {
  icon: string;
  value: string | number;
  label: string;
  color?: string;
}) {
  return (
    <div
      style={{
        background: "#f9fafb",
        borderRadius: 9,
        padding: "12px 14px",
        border: "1px solid #f3f4f6",
      }}
    >
      <div style={{ fontSize: 18, marginBottom: 2 }}>{icon}</div>
      <div style={{ fontSize: 19, fontWeight: 800, color, lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
        {label}
      </div>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    High: "#ef4444",
    Moderate: "#f59e0b",
    Low: "#22c55e",
  };
  const bg: Record<string, string> = {
    High: "#fee2e2",
    Moderate: "#fef3c7",
    Low: "#dcfce7",
  };
  const c = colors[level] || "#6b7280";
  const b = bg[level] || "#f3f4f6";
  return (
    <span
      style={{
        background: b,
        color: c,
        borderRadius: 20,
        padding: "3px 12px",
        fontSize: 12,
        fontWeight: 700,
        border: `1px solid ${c}`,
      }}
    >
      {level} Risk
    </span>
  );
}

export default function AnalyticsPanel({
  metrics,
  forecast,
  healthScore,
  species,
  loading,
  error,
}: Props) {
  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: 14,
        }}
      >
        <div
          style={{
            width: 38,
            height: 38,
            border: "3px solid #e5e7eb",
            borderTopColor: PURPLE,
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
        <p style={{ color: "#6b7280", fontSize: 13 }}>
          Analysing forest data… this may take up to 1–2 minutes while satellite
          features are prepared.
        </p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div style={{ padding: 22, textAlign: "center" }}>
        <div style={{ fontSize: 30, marginBottom: 8 }}>⚠️</div>
        <p style={{ color: "#ef4444", fontSize: 13 }}>{error}</p>
        <p style={{ color: "#6b7280", fontSize: 12, marginTop: 6 }}>
          Start the backend and draw a polygon to load live analytics.
        </p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div
        style={{ padding: "22px 20px", textAlign: "center", color: "#6b7280" }}
      >
        <div style={{ fontSize: 44, marginBottom: 10 }}>🌲</div>
        <p
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: NAVY,
            marginBottom: 6,
          }}
        >
          Draw a Polygon
        </p>
        <p style={{ fontSize: 12, lineHeight: 1.6, margin: "0 0 18px" }}>
          Use the polygon tool on the map to select a forest area. Full
          analytics will appear here instantly.
        </p>
        <div
          style={{
            padding: "14px",
            background: "#f0f4ff",
            borderRadius: 10,
            fontSize: 12,
            textAlign: "left",
          }}
        >
          <p
            style={{
              fontWeight: 700,
              color: NAVY,
              marginBottom: 6,
              marginTop: 0,
            }}
          >
            Live Backend Mode
          </p>
          <p style={{ margin: 0 }}>
            Draw a polygon to fetch real backend metrics and forecasts for the
            selected forest region.
          </p>
        </div>
      </div>
    );
  }

  // Merge species: prefer dedicated species endpoint if available
  const speciesData: Record<string, number> =
    species ?? metrics.species_distribution;
  const speciesEntries = Object.entries(speciesData);

  // NDVI / NDMI — prefer health score endpoint if available
  const ndvi = healthScore?.ndvi_avg ?? metrics.ndvi_avg ?? 0.72;
  const ndmi = healthScore?.ndmi_avg ?? metrics.ndmi_avg ?? 0.41;
  const displayHealth = healthScore?.health_score ?? metrics.health_score;

  const chartData = forecast
    ? {
        labels: forecast.forecast.map((p) => {
          const [y, m] = p.month.split("-");
          return new Date(+y, +m - 1).toLocaleDateString("en-IN", {
            month: "short",
            year: "2-digit",
          });
        }),
        datasets: [
          {
            label: "Health Score",
            data: forecast.forecast.map((p) => p.health_score),
            borderColor: PURPLE,
            backgroundColor: "rgba(64,28,134,0.08)",
            fill: true,
            tension: 0.4,
            pointBackgroundColor: PURPLE,
            pointRadius: 4,
          },
        ],
      }
    : null;

  return (
    <div
      style={{
        padding: "18px 16px",
        overflowY: "auto",
        height: "100%",
        fontFamily: "Open Sans, sans-serif",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 6,
          }}
        >
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: NAVY }}>
            Forest Analytics
          </h3>
          <RiskBadge level={metrics.risk_level} />
        </div>
        <p style={{ margin: "3px 0 0", fontSize: 11, color: "#6b7280" }}>
          Area: <b>{metrics.area_km2.toFixed(1)} km²</b> · Dang District,
          Gujarat
        </p>
        {error && (
          <p style={{ margin: "4px 0 0", fontSize: 11, color: "#f59e0b" }}>
            ⚠️ {error}
          </p>
        )}
      </div>

      {/* Key metrics grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
          marginBottom: 14,
        }}
      >
        <Stat
          icon="🌳"
          value={metrics.tree_count.toLocaleString("en-IN")}
          label="Estimated Trees"
          color={PURPLE}
        />
        <Stat
          icon="📐"
          value={`${metrics.tree_density}`}
          label="Trees / Ha"
          color={NAVY}
        />
        <Stat
          icon="🌿"
          value={ndvi.toFixed(2)}
          label="NDVI Index"
          color="#22c55e"
        />
        <Stat
          icon="💧"
          value={ndmi.toFixed(2)}
          label="NDMI Index"
          color="#0693e3"
        />
      </div>

      {/* Health bar */}
      <div
        style={{
          background: "#fff",
          borderRadius: 9,
          padding: "12px 14px",
          marginBottom: 12,
          border: "1px solid #e5e7eb",
        }}
      >
        <HealthBar score={displayHealth} />
      </div>

      {/* NDVI / NDMI detail */}
      <div
        style={{
          background: "#f0f9ff",
          borderRadius: 9,
          padding: "12px 14px",
          marginBottom: 12,
          border: "1px solid #bae6fd",
        }}
      >
        <p
          style={{
            fontWeight: 700,
            fontSize: 12,
            color: NAVY,
            margin: "0 0 8px",
          }}
        >
          Satellite Indices
        </p>
        {[
          {
            label: "NDVI (Vegetation)",
            value: ndvi,
            max: 1,
            color: "#22c55e",
            hint:
              ndvi >= 0.6
                ? "Dense vegetation"
                : ndvi >= 0.3
                  ? "Moderate greenness"
                  : "Sparse/stressed",
          },
          {
            label: "NDMI (Moisture)",
            value: ndmi,
            max: 1,
            color: "#0693e3",
            hint:
              ndmi >= 0.5
                ? "Well hydrated"
                : ndmi >= 0.3
                  ? "Moderate moisture"
                  : "Dry — fire risk",
          },
        ].map(({ label, value, color, hint }) => (
          <div key={label} style={{ marginBottom: 8 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 11,
                marginBottom: 3,
              }}
            >
              <span style={{ color: "#374151" }}>{label}</span>
              <span style={{ fontWeight: 700, color }}>
                {value.toFixed(2)} —{" "}
                <span style={{ fontWeight: 400, color: "#6b7280" }}>
                  {hint}
                </span>
              </span>
            </div>
            <div style={{ background: "#e0f2fe", borderRadius: 4, height: 6 }}>
              <div
                style={{
                  width: `${value * 100}%`,
                  background: color,
                  borderRadius: 4,
                  height: "100%",
                  transition: "width 0.6s",
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Species composition */}
      <div
        style={{
          background: "#fff",
          borderRadius: 9,
          padding: "12px 14px",
          marginBottom: 12,
          border: "1px solid #e5e7eb",
        }}
      >
        <p
          style={{
            fontWeight: 700,
            fontSize: 12,
            color: NAVY,
            margin: "0 0 8px",
          }}
        >
          Species Distribution
        </p>
        {speciesEntries.map(([key, pct]) => {
          const color = SPECIES_COLORS[key] ?? "#8b5cf6";
          return (
            <div key={key} style={{ marginBottom: 7 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 11,
                  marginBottom: 2,
                }}
              >
                <span style={{ color: "#374151" }}>
                  {key
                    .replace(/_/g, " ")
                    .replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
                <strong style={{ color }}>{pct}%</strong>
              </div>
              <div
                style={{ background: "#f3f4f6", borderRadius: 4, height: 6 }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    background: color,
                    borderRadius: 4,
                    height: "100%",
                    transition: "width 0.6s ease",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* 6-month forecast */}
      {chartData && (
        <div
          style={{
            background: "#fff",
            borderRadius: 9,
            padding: "12px 14px",
            border: "1px solid #e5e7eb",
            marginBottom: 12,
          }}
        >
          <p
            style={{
              fontWeight: 700,
              fontSize: 12,
              color: NAVY,
              margin: "0 0 8px",
            }}
          >
            6-Month Health Forecast
          </p>
          <Line
            data={chartData}
            options={{
              responsive: true,
              plugins: {
                legend: { display: false },
                tooltip: { mode: "index" },
              },
              scales: {
                y: { min: 0, max: 100, ticks: { font: { size: 9 } } },
                x: { ticks: { font: { size: 9 } } },
              },
            }}
          />
        </div>
      )}

      {/* Fire risk quick summary */}
      <div
        style={{
          borderRadius: 9,
          padding: "10px 14px",
          background:
            metrics.risk_level === "High"
              ? "#fef2f2"
              : metrics.risk_level === "Moderate"
                ? "#fffbeb"
                : "#f0fdf4",
          border: `1px solid ${metrics.risk_level === "High" ? "#fecaca" : metrics.risk_level === "Moderate" ? "#fde68a" : "#bbf7d0"}`,
        }}
      >
        <p
          style={{
            fontWeight: 700,
            fontSize: 12,
            color: NAVY,
            margin: "0 0 4px",
          }}
        >
          🔥 Forest Fire Risk
        </p>
        <p
          style={{ margin: 0, fontSize: 11, color: "#4b5563", lineHeight: 1.6 }}
        >
          {metrics.risk_level === "High"
            ? "HIGH risk — dry biomass and NDVI drop indicate active fire conditions. Immediate patrol required."
            : metrics.risk_level === "Moderate"
              ? "MODERATE risk — monitor moisture levels. Deploy patrols during dry season."
              : "LOW risk — vegetation moisture is adequate. Maintain routine fire watch schedules."}
        </p>
      </div>
    </div>
  );
}
