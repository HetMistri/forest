import { useState, useEffect } from "react";
import L from "leaflet";
import type { GeoJsonObject } from "geojson";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import {
  MapContainer,
  TileLayer,
  FeatureGroup,
  CircleMarker,
  Popup,
  GeoJSON,
} from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import { forestApi } from "../../utils/forestApi";
import type { NDVIMapResponse, RiskZonesResponse } from "../../utils/forestApi";
import { createLogger } from "../../utils/logger";

// Fix Leaflet's broken default icon paths when bundled with Vite
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)
  ._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Dang district, Gujarat — Leaflet uses [lat, lng]
const DANG_CENTER: [number, number] = [20.75, 73.7];
const DANG_ZOOM = 10;

const CARTO_URL =
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const CARTO_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';

interface Props {
  onPolygonDrawn: (coords: [number, number][]) => void;
  riskAlerts?: { location: [number, number]; severity: string }[];
}

type LayerMode = "default" | "ndvi" | "risk";
const logger = createLogger("ForestMap");

export default function ForestMap({ onPolygonDrawn, riskAlerts = [] }: Props) {
  const [activeLayer, setActiveLayer] = useState<LayerMode>("default");
  const [ndviData, setNdviData] = useState<NDVIMapResponse | null>(null);
  const [riskZones, setRiskZones] = useState<RiskZonesResponse | null>(null);
  const [layerLoading, setLayerLoading] = useState(false);

  useEffect(() => {
    logger.info("Map mounted", {
      center: DANG_CENTER,
      zoom: DANG_ZOOM,
    });
    return () => {
      logger.info("Map unmounted");
    };
  }, []);

  useEffect(() => {
    logger.debug("Risk alerts updated", { count: riskAlerts.length });
  }, [riskAlerts]);

  async function handleLayerChange(layer: LayerMode): Promise<void> {
    const startedAt = Date.now();
    logger.info("Layer change requested", {
      from: activeLayer,
      to: layer,
    });

    setActiveLayer(layer);

    if (layer === "ndvi" && !ndviData) {
      setLayerLoading(true);
      try {
        const data = await forestApi.getNDVIMap();
        setNdviData(data);
        logger.info("NDVI layer loaded", {
          durationMs: Date.now() - startedAt,
          hasTile: Boolean(data.tile_url),
          hasGeoJson: Boolean(data.geojson),
        });
      } catch {
        setNdviData(null);
        logger.error("NDVI layer load failed", {
          durationMs: Date.now() - startedAt,
        });
      } finally {
        setLayerLoading(false);
      }
      return;
    }

    if (layer === "risk" && !riskZones) {
      setLayerLoading(true);
      try {
        const data = await forestApi.getRiskZones();
        setRiskZones(data);
        logger.info("Risk zones layer loaded", {
          durationMs: Date.now() - startedAt,
          zoneCount: data.zones.length,
        });
      } catch {
        setRiskZones(null);
        logger.error("Risk zones layer load failed", {
          durationMs: Date.now() - startedAt,
        });
      } finally {
        setLayerLoading(false);
      }
      return;
    }

    logger.debug("Layer switched using cached data", {
      to: layer,
      durationMs: Date.now() - startedAt,
    });
  }

  function handleCreated(e: { layer: L.Layer }) {
    const layer = e.layer as L.Polygon;
    const rings = layer.getLatLngs();
    const ring = (Array.isArray(rings[0]) ? rings[0] : rings) as L.LatLng[];
    // Convert to [lon, lat] to match the existing API contract
    const coords: [number, number][] = ring.map((ll) => [ll.lng, ll.lat]);
    logger.info("Polygon created", {
      vertices: coords.length,
      coordinates: coords,
    });
    onPolygonDrawn(coords);
  }

  const PURPLE = "#401c86";

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <MapContainer
        center={DANG_CENTER}
        zoom={DANG_ZOOM}
        style={{ width: "100%", height: "100%" }}
      >
        <TileLayer
          url={CARTO_URL}
          attribution={CARTO_ATTRIBUTION}
          subdomains="abcd"
          maxZoom={20}
        />

        {/* NDVI tile overlay */}
        {activeLayer === "ndvi" && ndviData?.tile_url && (
          <TileLayer
            url={ndviData.tile_url}
            opacity={0.65}
            attribution="NDVI — Sentinel-2"
          />
        )}

        {/* Risk zone polygons */}
        {activeLayer === "risk" &&
          riskZones?.zones?.map((zone, i) => {
            const color =
              zone.risk === "High"
                ? "#ef4444"
                : zone.risk === "Moderate"
                  ? "#f59e0b"
                  : "#22c55e";
            return (
              <GeoJSON
                key={i}
                data={zone.geometry as GeoJsonObject}
                style={{
                  color,
                  fillColor: color,
                  fillOpacity: 0.25,
                  weight: 2,
                }}
              >
                <Popup>
                  <b>{zone.risk} Risk Zone</b>
                  <br />
                  Detected degradation hotspot
                </Popup>
              </GeoJSON>
            );
          })}

        <FeatureGroup>
          <EditControl
            position="topleft"
            onCreated={handleCreated}
            draw={{
              rectangle: false,
              circle: false,
              circlemarker: false,
              marker: false,
              polyline: false,
              polygon: {
                allowIntersection: false,
                shapeOptions: {
                  color: PURPLE,
                  fillColor: PURPLE,
                  fillOpacity: 0.15,
                  weight: 2,
                },
              },
            }}
            edit={{ featureGroup: new L.FeatureGroup() }}
          />
        </FeatureGroup>

        {riskAlerts.map(({ location, severity }, i) => {
          const color =
            severity === "High"
              ? "#ef4444"
              : severity === "Moderate"
                ? "#f59e0b"
                : "#22c55e";
          return (
            <CircleMarker
              key={i}
              center={[location[0], location[1]]}
              radius={8}
              pathOptions={{
                color: "#ffffff",
                fillColor: color,
                fillOpacity: 1,
                weight: 2,
              }}
            >
              <Popup>
                <b>{severity} Risk Alert</b>
                <br />
                Deforestation / fire anomaly detected
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* Layer toggle control */}
      <div
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          zIndex: 1000,
          background: "rgba(255,255,255,0.96)",
          borderRadius: 8,
          padding: "8px 10px",
          boxShadow: "0 2px 10px rgba(0,0,0,0.15)",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: "#6b7280",
            marginBottom: 2,
            textTransform: "uppercase",
          }}
        >
          Layers
        </div>
        {(
          [
            { key: "default", label: "🗺️ Base Map" },
            { key: "ndvi", label: "🌿 NDVI" },
            { key: "risk", label: "⚠️ Risk Zones" },
          ] as { key: LayerMode; label: string }[]
        ).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => {
              void handleLayerChange(key);
            }}
            style={{
              fontSize: 11,
              padding: "4px 10px",
              borderRadius: 5,
              cursor: "pointer",
              border: `1px solid ${activeLayer === key ? PURPLE : "#e5e7eb"}`,
              background: activeLayer === key ? PURPLE : "#fff",
              color: activeLayer === key ? "#fff" : "#374151",
              fontWeight: activeLayer === key ? 700 : 400,
              transition: "all 0.15s",
            }}
          >
            {label}
          </button>
        ))}
        {layerLoading && (
          <div
            style={{
              fontSize: 10,
              color: "#6b7280",
              textAlign: "center",
              paddingTop: 2,
            }}
          >
            Loading…
          </div>
        )}
      </div>

      {/* Instruction tooltip */}
      <div
        style={{
          position: "absolute",
          bottom: 12,
          left: 12,
          background: "rgba(255,255,255,0.95)",
          borderRadius: 6,
          padding: "7px 12px",
          fontSize: 11,
          color: "#020f50",
          boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          maxWidth: 200,
          zIndex: 1000,
        }}
      >
        <strong>Draw a polygon</strong> over the Dang district forest to run
        instant analysis.
      </div>
    </div>
  );
}
