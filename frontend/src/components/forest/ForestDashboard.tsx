import { useState, useCallback, useEffect } from "react";
import { forestApi } from "../../utils/forestApi";
import type {
  ForestMetricsResponse,
  HealthForecastResponse,
  PipelineStatusResponse,
  RiskAlertsResponse,
  HealthScoreResponse,
  TreeDensityResponse,
  SpeciesCompositionResponse,
  SystemStatusResponse,
} from "../../utils/forestApi";
import ForestMap from "./ForestMap";
import AnalyticsPanel from "./AnalyticsPanel";
import KPISection from "./KPISection";
import amnexLogo from "../../assets/image.png";
import { createLogger } from "../../utils/logger";

const PURPLE = "#401c86";
const NAVY = "#020f50";
const ANALYSIS_RETRY_INTERVAL_MS = 3000;
const ANALYSIS_RETRY_WINDOW_MS = 90000;
const logger = createLogger("ForestDashboard");

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function isRetryableAnalysisError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return (
    message.includes("503") ||
    message.includes("502") ||
    message.includes("bad gateway") ||
    message.includes("failed to fetch") ||
    message.includes("network") ||
    message.includes("timed out") ||
    message.includes("service unavailable") ||
    message.includes("no real") ||
    message.includes("pipeline") ||
    message.includes("features")
  );
}

export interface DashboardState {
  metrics: ForestMetricsResponse | null;
  forecast: HealthForecastResponse | null;
  riskData: RiskAlertsResponse | null;
  healthScore: HealthScoreResponse | null;
  treeDensity: TreeDensityResponse | null;
  species: SpeciesCompositionResponse | null;
  systemStatus: SystemStatusResponse | null;
  polygon: [number, number][] | null;
  pipelineStatus: PipelineStatusResponse | null;
  loading: boolean;
  error: string | null;
}

export default function ForestDashboard() {
  const [state, setState] = useState<DashboardState>({
    metrics: null,
    forecast: null,
    riskData: null,
    healthScore: null,
    treeDensity: null,
    species: null,
    systemStatus: null,
    polygon: null,
    pipelineStatus: null,
    loading: false,
    error: null,
  });

  useEffect(() => {
    logger.info("Dashboard mounted");
    return () => {
      logger.info("Dashboard unmounted");
    };
  }, []);

  const handlePolygon = useCallback(async (coords: [number, number][]) => {
    const analysisStartedAt = Date.now();
    logger.info("Polygon analysis started", {
      vertexCount: coords.length,
      polygon: coords,
    });

    setState((s) => ({
      ...s,
      loading: true,
      error: null,
      polygon: coords,
      pipelineStatus: {
        status: "processing",
        in_progress: true,
        has_feature_data: false,
        detail: "Starting analysis pipeline...",
      },
    }));
    try {
      const startedAt = Date.now();
      let lastRetryableError: unknown = null;
      let metrics: ForestMetricsResponse | null = null;
      let attempt = 0;
      let shouldPollPipelineStatus = false;

      while (Date.now() - startedAt < ANALYSIS_RETRY_WINDOW_MS) {
        if (!shouldPollPipelineStatus) {
          attempt += 1;
          logger.info("Requesting forest metrics", {
            attempt,
            elapsedMs: Date.now() - startedAt,
          });

          try {
            metrics = await forestApi.getForestMetrics(coords);
            logger.info("Forest metrics received", {
              attempt,
              areaKm2: metrics.area_km2,
              treeCount: metrics.tree_count,
              healthScore: metrics.health_score,
              riskLevel: metrics.risk_level,
            });
            break;
          } catch (error) {
            if (!isRetryableAnalysisError(error)) {
              logger.error("Non-retryable metrics error", { attempt, error });
              throw error;
            }

            lastRetryableError = error;
            shouldPollPipelineStatus = true;
            logger.warn(
              "Retryable metrics error; switching to pipeline polling",
              {
                attempt,
                error,
              },
            );
          }
        }

        let pipelineStatus: PipelineStatusResponse | null = null;
        try {
          pipelineStatus = await forestApi.getPipelineStatus(coords);
          logger.info("Pipeline status polled", pipelineStatus);
          setState((s) => ({ ...s, pipelineStatus }));
        } catch (statusError) {
          logger.warn("Pipeline status poll failed", { statusError });
          await wait(ANALYSIS_RETRY_INTERVAL_MS);
          continue;
        }

        if (pipelineStatus.status !== "processing") {
          attempt += 1;
          logger.info("Re-attempting forest metrics after pipeline status", {
            attempt,
            status: pipelineStatus.status,
            elapsedMs: Date.now() - startedAt,
          });

          try {
            metrics = await forestApi.getForestMetrics(coords);
            logger.info("Forest metrics received", {
              attempt,
              areaKm2: metrics.area_km2,
              treeCount: metrics.tree_count,
              healthScore: metrics.health_score,
              riskLevel: metrics.risk_level,
            });
            break;
          } catch (error) {
            if (!isRetryableAnalysisError(error)) {
              logger.error("Non-retryable metrics error", { attempt, error });
              throw error;
            }

            lastRetryableError = error;
            logger.warn("Retryable metrics error; retry scheduled", {
              attempt,
              retryInMs: ANALYSIS_RETRY_INTERVAL_MS,
              error,
            });
          }
        } else {
          logger.info(
            "Pipeline still processing; metrics request skipped this cycle",
            {
              attempt,
              elapsedMs: Date.now() - startedAt,
            },
          );
        }

        await wait(ANALYSIS_RETRY_INTERVAL_MS);
      }

      if (!metrics) {
        throw (
          lastRetryableError ??
          new Error(
            "Analysis timed out while waiting for backend pipeline. Please retry in a few moments.",
          )
        );
      }

      logger.info("Fetching secondary analytics in parallel", {
        endpoints: [
          "/health-forecast",
          "/risk-alerts",
          "/health-score",
          "/tree-density",
          "/species-composition",
          "/system-status",
        ],
      });

      const [f, r, hs, td, sp, sys] = await Promise.all([
        forestApi.getHealthForecast(coords),
        forestApi.getRiskAlerts(coords),
        forestApi.getHealthScore(coords),
        forestApi.getTreeDensity(coords),
        forestApi.getSpeciesComposition(coords),
        forestApi.getSystemStatus(),
      ]);

      logger.info("Secondary analytics received", {
        forecastPoints: f.forecast.length,
        alertCount: r.alerts.length,
        treeDensity: td.tree_density,
        speciesCount: Object.keys(sp).length,
        modelStatus: sys.model_status,
      });

      setState((s) => ({
        ...s,
        metrics,
        forecast: f,
        riskData: r,
        healthScore: hs,
        treeDensity: td,
        species: sp,
        systemStatus: sys,
        pipelineStatus: {
          status: "ready",
          in_progress: false,
          has_feature_data: true,
          detail: "Feature data is ready for this polygon.",
        },
        loading: false,
        error: null,
      }));

      logger.info("Polygon analysis completed", {
        durationMs: Date.now() - analysisStartedAt,
      });
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : "Analysis failed. Backend may be offline.";

      logger.error("Polygon analysis failed", {
        durationMs: Date.now() - analysisStartedAt,
        message: msg,
        error,
      });

      setState((s) => ({
        ...s,
        loading: false,
        error: msg,
      }));
    }
  }, []);

  const {
    metrics,
    forecast,
    riskData,
    healthScore,
    treeDensity,
    species,
    systemStatus,
    pipelineStatus,
    loading,
    error,
  } = state;

  const pipelineLabel = pipelineStatus
    ? pipelineStatus.status === "ready"
      ? "✅ Ready"
      : pipelineStatus.status === "processing"
        ? "⏳ Processing"
        : "⚠️ Unavailable"
    : "⏳ Waiting...";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#f0f2f8",
        fontFamily: "Open Sans, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          background: NAVY,
          padding: "36px 0 28px",
          textAlign: "center",
          color: "#fff",
        }}
      >
        <div style={{ maxWidth: 1400, margin: "0 auto", padding: "0 24px" }}>
          <img
            src={amnexLogo}
            alt="AMNEX"
            style={{ height: 44, display: "block", margin: "0 auto 14px" }}
          />
          <p
            style={{
              color: "#a78bff",
              fontSize: 13,
              fontWeight: 600,
              margin: "0 0 6px",
              letterSpacing: 1,
              textTransform: "uppercase",
            }}
          >
            EcoKeeper · Forest Intelligence Platform
          </p>
          <h1
            style={{
              margin: "0 0 10px",
              fontSize: "clamp(24px, 3.5vw, 40px)",
              fontWeight: 700,
              lineHeight: 1.2,
            }}
          >
            Dang District Forest Analytics Dashboard
          </h1>
          <p
            style={{
              margin: 0,
              color: "#b0b8d4",
              fontSize: 14,
              maxWidth: 640,
              marginLeft: "auto",
              marginRight: "auto",
              lineHeight: 1.7,
            }}
          >
            All-weather forest monitoring powered by Sentinel-1 SAR radar &amp;
            Sentinel-2 optical satellite fusion. Draw a polygon on the map to
            analyse tree count, health, species, risk alerts and 6-month
            forecast.
          </p>
        </div>
      </div>

      {/* Stats ribbon */}
      <div style={{ background: PURPLE, padding: "12px 24px" }}>
        <div
          style={{
            maxWidth: 1400,
            margin: "0 auto",
            display: "flex",
            flexWrap: "wrap",
            gap: "6px 28px",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          {[
            { label: "District", value: "Dang, Gujarat" },
            { label: "Forest Cover", value: "~1,764 km²" },
            { label: "Satellite Data", value: "Sentinel-1 + Sentinel-2" },
            { label: "Model", value: "RandomForest + Prophet" },
            {
              label: "System",
              value: systemStatus
                ? systemStatus.model_status === "ready"
                  ? "✅ Live"
                  : "⚠️ Limited"
                : "⏳ Checking…",
            },
            {
              label: "Pipeline",
              value: pipelineLabel,
            },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{ color: "#fff", fontSize: 12, textAlign: "center" }}
            >
              <span style={{ color: "#d4b8ff", marginRight: 5 }}>{label}:</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </div>

      {/* Main layout */}
      <div style={{ maxWidth: 1400, margin: "0 auto", padding: "22px 16px" }}>
        {/* Map + side panel */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0,1fr) 380px",
            gap: 18,
            height: 600,
            marginBottom: 22,
          }}
        >
          <div
            style={{
              borderRadius: 14,
              overflow: "hidden",
              boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
              border: "1px solid #e5e7eb",
            }}
          >
            <ForestMap
              onPolygonDrawn={handlePolygon}
              riskAlerts={
                riskData?.alerts?.map((a) => ({
                  location: a.location as [number, number],
                  severity: a.severity,
                })) ?? []
              }
            />
          </div>
          <div
            style={{
              background: "#fff",
              borderRadius: 14,
              boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
              border: "1px solid #e5e7eb",
              overflow: "hidden",
            }}
          >
            <AnalyticsPanel
              metrics={metrics}
              forecast={forecast}
              healthScore={healthScore}
              species={species}
              loading={loading}
              error={error}
            />
          </div>
        </div>

        {/* KPI section — full width below map */}
        <KPISection
          metrics={metrics}
          treeDensity={treeDensity}
          riskData={riskData}
          loading={loading}
        />

        {/* How it works */}
        <div style={{ marginTop: 36, marginBottom: 20 }}>
          <p
            style={{
              color: PURPLE,
              fontSize: 13,
              fontWeight: 600,
              margin: "0 0 4px",
              textTransform: "uppercase",
              letterSpacing: 0.8,
            }}
          >
            How It Works
          </p>
          <h2
            style={{
              color: NAVY,
              fontSize: "clamp(20px, 2.5vw, 30px)",
              fontWeight: 700,
              margin: "6px 0 20px",
              lineHeight: 1.25,
            }}
          >
            Satellite-Powered Forest Intelligence Pipeline
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
              gap: 14,
            }}
          >
            {[
              {
                step: "01",
                icon: "🛰️",
                title: "Satellite Ingestion",
                desc: "Sentinel-1 SAR (VV/VH) and Sentinel-2 optical imagery ingested via Google Earth Engine.",
              },
              {
                step: "02",
                icon: "🔬",
                title: "Feature Extraction",
                desc: "NDVI, NDMI, and SAR backscatter computed and aggregated into hectare-level grid cells.",
              },
              {
                step: "03",
                icon: "🤖",
                title: "ML Models",
                desc: "RandomForestRegressor predicts tree density; NDVI/NDMI drives health scoring; Prophet forecasts trends.",
              },
              {
                step: "04",
                icon: "⚠️",
                title: "Risk Detection",
                desc: "NDVI drop anomaly detection flags deforestation and forest fire hotspots for immediate response.",
              },
              {
                step: "05",
                icon: "📊",
                title: "Live Dashboard",
                desc: "Draw any polygon to get instant tree count, health score, risk zones, and 6-month projection.",
              },
            ].map(({ step, icon, title, desc }) => (
              <div
                key={step}
                style={{
                  background: "#fff",
                  borderRadius: 12,
                  padding: "18px 16px",
                  border: "1px solid #e5e7eb",
                  boxShadow: "0 1px 6px rgba(0,0,0,0.06)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: PURPLE,
                      background: "#f0ebff",
                      borderRadius: 4,
                      padding: "2px 6px",
                    }}
                  >
                    {step}
                  </span>
                  <span style={{ fontSize: 18 }}>{icon}</span>
                </div>
                <h4
                  style={{
                    margin: "0 0 5px",
                    color: NAVY,
                    fontSize: 13,
                    fontWeight: 700,
                  }}
                >
                  {title}
                </h4>
                <p
                  style={{
                    margin: 0,
                    color: "#6b7280",
                    fontSize: 12,
                    lineHeight: 1.6,
                  }}
                >
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Differentiator callout */}
        <div
          style={{
            background: `linear-gradient(135deg, ${NAVY} 0%, #0f497b 100%)`,
            borderRadius: 14,
            padding: "28px 32px",
            color: "#fff",
            marginBottom: 24,
            display: "flex",
            gap: 24,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: "1 1 260px" }}>
            <p
              style={{
                color: "#a78bff",
                fontSize: 12,
                fontWeight: 600,
                margin: "0 0 6px",
                textTransform: "uppercase",
              }}
            >
              Key Technical Differentiator
            </p>
            <h3
              style={{
                margin: "0 0 8px",
                fontSize: 20,
                fontWeight: 700,
                lineHeight: 1.3,
              }}
            >
              All-Weather Forest Monitoring
            </h3>
            <p
              style={{
                color: "#b0b8d4",
                fontSize: 13,
                lineHeight: 1.7,
                margin: 0,
              }}
            >
              Traditional optical satellites fail during monsoon cloud cover —
              the season when deforestation risk is highest. Our SAR + optical
              fusion provides reliable data year-round, giving forest officers
              actionable intelligence exactly when they need it most.
            </p>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 10,
              flex: "0 0 auto",
            }}
          >
            {[
              { icon: "📡", text: "Sentinel-1 SAR — cloud-penetrating radar" },
              { icon: "🌿", text: "Sentinel-2 optical — vegetation indices" },
              { icon: "🔀", text: "Data fusion for all-weather monitoring" },
              { icon: "🔥", text: "Fire risk detection via thermal anomalies" },
            ].map(({ icon, text }) => (
              <div
                key={text}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  color: "#e2e8f0",
                  fontSize: 13,
                }}
              >
                <span style={{ fontSize: 16 }}>{icon}</span> {text}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
