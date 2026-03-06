-- Forest backend bootstrap (PostgreSQL + PostGIS)
-- Idempotent script for hackathon scaffolding.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_level_t') THEN
        CREATE TYPE risk_level_t AS ENUM ('Low', 'Moderate', 'High');
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS forest_features (
    grid_id TEXT PRIMARY KEY,
    geometry GEOMETRY(POLYGON, 4326) NOT NULL,
    ndvi DOUBLE PRECISION NOT NULL,
    ndmi DOUBLE PRECISION NOT NULL,
    evi DOUBLE PRECISION,
    vv DOUBLE PRECISION,
    vh DOUBLE PRECISION,
    vv_vh_ratio DOUBLE PRECISION,
    ndvi_trend DOUBLE PRECISION,
    sar_ratio DOUBLE PRECISION,
    vegetation_variance DOUBLE PRECISION,
    source TEXT DEFAULT 'sentinel',
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_features_ndvi_range CHECK (ndvi BETWEEN -1.0 AND 1.0),
    CONSTRAINT chk_features_ndmi_range CHECK (ndmi BETWEEN -1.0 AND 1.0),
    CONSTRAINT chk_features_evi_range CHECK (evi IS NULL OR evi BETWEEN -1.0 AND 1.0)
);

ALTER TABLE forest_features ADD COLUMN IF NOT EXISTS evi DOUBLE PRECISION;
ALTER TABLE forest_features ADD COLUMN IF NOT EXISTS vv DOUBLE PRECISION;
ALTER TABLE forest_features ADD COLUMN IF NOT EXISTS vh DOUBLE PRECISION;
ALTER TABLE forest_features ADD COLUMN IF NOT EXISTS vv_vh_ratio DOUBLE PRECISION;
ALTER TABLE forest_features ADD COLUMN IF NOT EXISTS ndvi_trend DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS species_composition (
    grid_id TEXT PRIMARY KEY REFERENCES forest_features(grid_id) ON DELETE CASCADE,
    teak DOUBLE PRECISION NOT NULL DEFAULT 0,
    bamboo DOUBLE PRECISION NOT NULL DEFAULT 0,
    mixed_deciduous DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_species_teak CHECK (teak BETWEEN 0 AND 100),
    CONSTRAINT chk_species_bamboo CHECK (bamboo BETWEEN 0 AND 100),
    CONSTRAINT chk_species_mixed CHECK (mixed_deciduous BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS forest_metrics (
    grid_id TEXT PRIMARY KEY REFERENCES forest_features(grid_id) ON DELETE CASCADE,
    geometry GEOMETRY(POLYGON, 4326) NOT NULL,
    tree_density DOUBLE PRECISION NOT NULL,
    health_score DOUBLE PRECISION NOT NULL,
    risk_level risk_level_t NOT NULL,
    forecast_health DOUBLE PRECISION,
    species_distribution JSONB DEFAULT '{}'::jsonb,
    model_version TEXT DEFAULT 'v1',
    metric_timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_metrics_tree_density_non_negative CHECK (tree_density >= 0),
    CONSTRAINT chk_metrics_health_range CHECK (health_score BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS risk_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grid_id TEXT REFERENCES forest_metrics(grid_id) ON DELETE SET NULL,
    alert_type TEXT NOT NULL,
    severity risk_level_t NOT NULL,
    location GEOMETRY(POINT, 4326),
    metadata JSONB DEFAULT '{}'::jsonb,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS demo_polygon_cache (
    cache_key TEXT PRIMARY KEY,
    polygon GEOMETRY(POLYGON, 4326) NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forest_features_geom ON forest_features USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_forest_features_captured_at ON forest_features (captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_forest_metrics_geom ON forest_metrics USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_forest_metrics_risk_level ON forest_metrics (risk_level);
CREATE INDEX IF NOT EXISTS idx_forest_metrics_timestamp ON forest_metrics (metric_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_risk_alerts_location ON risk_alerts USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_detected_at ON risk_alerts (detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_demo_polygon_cache_geom ON demo_polygon_cache USING GIST (polygon);

DROP TRIGGER IF EXISTS trg_forest_features_updated_at ON forest_features;
CREATE TRIGGER trg_forest_features_updated_at
BEFORE UPDATE ON forest_features
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_species_composition_updated_at ON species_composition;
CREATE TRIGGER trg_species_composition_updated_at
BEFORE UPDATE ON species_composition
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_forest_metrics_updated_at ON forest_metrics;
CREATE TRIGGER trg_forest_metrics_updated_at
BEFORE UPDATE ON forest_metrics
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_demo_polygon_cache_updated_at ON demo_polygon_cache;
CREATE TRIGGER trg_demo_polygon_cache_updated_at
BEFORE UPDATE ON demo_polygon_cache
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION json_polygon_to_geom(p_polygon JSONB)
RETURNS GEOMETRY AS $$
DECLARE
    points GEOMETRY[];
    first_point GEOMETRY;
    last_point GEOMETRY;
    ring GEOMETRY;
BEGIN
    SELECT ARRAY_AGG(
        ST_SetSRID(ST_MakePoint((p->>0)::DOUBLE PRECISION, (p->>1)::DOUBLE PRECISION), 4326)
        ORDER BY ord
    )
    INTO points
    FROM jsonb_array_elements(p_polygon) WITH ORDINALITY AS t(p, ord);

    IF points IS NULL OR array_length(points, 1) < 3 THEN
        RAISE EXCEPTION 'Polygon must contain at least 3 points';
    END IF;

    first_point := points[1];
    last_point := points[array_length(points, 1)];

    IF NOT ST_Equals(first_point, last_point) THEN
        points := array_append(points, first_point);
    END IF;

    ring := ST_MakeLine(points);
    RETURN ST_MakePolygon(ring);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION upsert_forest_feature(
    p_grid_id TEXT,
    p_geometry GEOMETRY,
    p_ndvi DOUBLE PRECISION,
    p_ndmi DOUBLE PRECISION,
    p_sar_ratio DOUBLE PRECISION DEFAULT NULL,
    p_vegetation_variance DOUBLE PRECISION DEFAULT NULL,
    p_source TEXT DEFAULT 'sentinel',
    p_captured_at TIMESTAMPTZ DEFAULT NOW(),
    p_evi DOUBLE PRECISION DEFAULT NULL,
    p_vv DOUBLE PRECISION DEFAULT NULL,
    p_vh DOUBLE PRECISION DEFAULT NULL,
    p_vv_vh_ratio DOUBLE PRECISION DEFAULT NULL,
    p_ndvi_trend DOUBLE PRECISION DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO forest_features (
        grid_id,
        geometry,
        ndvi,
        ndmi,
        evi,
        vv,
        vh,
        vv_vh_ratio,
        ndvi_trend,
        sar_ratio,
        vegetation_variance,
        source,
        captured_at
    )
    VALUES (
        p_grid_id,
        ST_SetSRID(p_geometry, 4326),
        p_ndvi,
        p_ndmi,
        p_evi,
        p_vv,
        p_vh,
        p_vv_vh_ratio,
        p_ndvi_trend,
        COALESCE(p_sar_ratio, p_vv_vh_ratio),
        p_vegetation_variance,
        p_source,
        p_captured_at
    )
    ON CONFLICT (grid_id)
    DO UPDATE SET
        geometry = EXCLUDED.geometry,
        ndvi = EXCLUDED.ndvi,
        ndmi = EXCLUDED.ndmi,
        evi = EXCLUDED.evi,
        vv = EXCLUDED.vv,
        vh = EXCLUDED.vh,
        vv_vh_ratio = EXCLUDED.vv_vh_ratio,
        ndvi_trend = EXCLUDED.ndvi_trend,
        sar_ratio = EXCLUDED.sar_ratio,
        vegetation_variance = EXCLUDED.vegetation_variance,
        source = EXCLUDED.source,
        captured_at = EXCLUDED.captured_at;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION upsert_forest_metric(
    p_grid_id TEXT,
    p_geometry GEOMETRY,
    p_tree_density DOUBLE PRECISION,
    p_health_score DOUBLE PRECISION,
    p_risk_level risk_level_t,
    p_forecast_health DOUBLE PRECISION DEFAULT NULL,
    p_species_distribution JSONB DEFAULT '{}'::jsonb,
    p_model_version TEXT DEFAULT 'v1',
    p_metric_timestamp TIMESTAMPTZ DEFAULT NOW()
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO forest_metrics (
        grid_id,
        geometry,
        tree_density,
        health_score,
        risk_level,
        forecast_health,
        species_distribution,
        model_version,
        metric_timestamp
    )
    VALUES (
        p_grid_id,
        ST_SetSRID(p_geometry, 4326),
        p_tree_density,
        p_health_score,
        p_risk_level,
        p_forecast_health,
        COALESCE(p_species_distribution, '{}'::jsonb),
        p_model_version,
        p_metric_timestamp
    )
    ON CONFLICT (grid_id)
    DO UPDATE SET
        geometry = EXCLUDED.geometry,
        tree_density = EXCLUDED.tree_density,
        health_score = EXCLUDED.health_score,
        risk_level = EXCLUDED.risk_level,
        forecast_health = EXCLUDED.forecast_health,
        species_distribution = EXCLUDED.species_distribution,
        model_version = EXCLUDED.model_version,
        metric_timestamp = EXCLUDED.metric_timestamp;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_forest_metrics(p_polygon JSONB)
RETURNS TABLE (
    area_km2 DOUBLE PRECISION,
    tree_count DOUBLE PRECISION,
    tree_density DOUBLE PRECISION,
    health_score DOUBLE PRECISION,
    risk_level TEXT,
    species_distribution JSONB,
    forecast_health DOUBLE PRECISION
) AS $$
DECLARE
    poly GEOMETRY;
BEGIN
    poly := json_polygon_to_geom(p_polygon);

    RETURN QUERY
    WITH inside_metrics AS (
        SELECT *
        FROM forest_metrics fm
        WHERE ST_Intersects(fm.geometry, poly)
    ),
    inside_features AS (
        SELECT *
        FROM forest_features ff
        WHERE ST_Intersects(ff.geometry, poly)
    ),
    agg AS (
        SELECT
            COALESCE(SUM((im.tree_density * ST_Area(im.geometry::GEOGRAPHY) / 10000.0)), 0) AS tree_count_v,
            COALESCE(AVG(im.tree_density), 0) AS tree_density_v,
            COALESCE(AVG(im.health_score), 0) AS health_score_v,
            COALESCE(AVG(im.forecast_health), 0) AS forecast_health_v,
            CASE
                WHEN SUM(CASE WHEN im.risk_level = 'High' THEN 1 ELSE 0 END) > 0 THEN 'High'
                WHEN SUM(CASE WHEN im.risk_level = 'Moderate' THEN 1 ELSE 0 END) > 0 THEN 'Moderate'
                ELSE 'Low'
            END AS risk_level_v
        FROM inside_metrics im
    ),
    species AS (
        SELECT jsonb_build_object(
            'teak', COALESCE(AVG(sc.teak), 0),
            'bamboo', COALESCE(AVG(sc.bamboo), 0),
            'mixed_deciduous', COALESCE(AVG(sc.mixed_deciduous), 0)
        ) AS species_v
        FROM inside_features ff
        LEFT JOIN species_composition sc ON sc.grid_id = ff.grid_id
    )
    SELECT
        COALESCE(ST_Area(poly::GEOGRAPHY) / 1000000.0, 0),
        agg.tree_count_v,
        agg.tree_density_v,
        agg.health_score_v,
        agg.risk_level_v,
        species.species_v,
        agg.forecast_health_v
    FROM agg CROSS JOIN species;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION get_tree_density(p_polygon JSONB)
RETURNS TABLE (
    tree_density DOUBLE PRECISION,
    total_trees DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT m.tree_density, m.tree_count
    FROM get_forest_metrics(p_polygon) m;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION get_health_score(p_polygon JSONB)
RETURNS TABLE (
    health_score DOUBLE PRECISION,
    ndvi_avg DOUBLE PRECISION,
    ndmi_avg DOUBLE PRECISION
) AS $$
DECLARE
    poly GEOMETRY;
BEGIN
    poly := json_polygon_to_geom(p_polygon);

    RETURN QUERY
    WITH f AS (
        SELECT ff.ndvi, ff.ndmi
        FROM forest_features ff
        WHERE ST_Intersects(ff.geometry, poly)
    ),
    m AS (
        SELECT fm.health_score
        FROM forest_metrics fm
        WHERE ST_Intersects(fm.geometry, poly)
    )
    SELECT
        COALESCE((SELECT AVG(m.health_score) FROM m), 0),
        COALESCE((SELECT AVG(ndvi) FROM f), 0),
        COALESCE((SELECT AVG(ndmi) FROM f), 0);
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION get_species_composition(p_polygon JSONB)
RETURNS JSONB AS $$
DECLARE
    poly GEOMETRY;
    result JSONB;
BEGIN
    poly := json_polygon_to_geom(p_polygon);

    SELECT jsonb_build_object(
        'teak', COALESCE(AVG(sc.teak), 0),
        'bamboo', COALESCE(AVG(sc.bamboo), 0),
        'mixed_deciduous', COALESCE(AVG(sc.mixed_deciduous), 0)
    )
    INTO result
    FROM forest_features ff
    LEFT JOIN species_composition sc ON sc.grid_id = ff.grid_id
    WHERE ST_Intersects(ff.geometry, poly);

    RETURN COALESCE(result, jsonb_build_object('teak', 0, 'bamboo', 0, 'mixed_deciduous', 0));
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION get_risk_alerts(p_polygon JSONB)
RETURNS JSONB AS $$
DECLARE
    poly GEOMETRY;
    result JSONB;
BEGIN
    poly := json_polygon_to_geom(p_polygon);

    WITH alerts AS (
        SELECT
            ra.alert_type,
            ra.severity,
            ST_Y(ra.location) AS lat,
            ST_X(ra.location) AS lon,
            ra.detected_at
        FROM risk_alerts ra
        WHERE ra.location IS NOT NULL
          AND ST_Intersects(ra.location, poly)
        ORDER BY ra.detected_at DESC
        LIMIT 100
    )
    SELECT jsonb_build_object(
        'risk_level', CASE
            WHEN EXISTS (SELECT 1 FROM alerts WHERE severity = 'High') THEN 'High'
            WHEN EXISTS (SELECT 1 FROM alerts WHERE severity = 'Moderate') THEN 'Moderate'
            ELSE 'Low'
        END,
        'alerts', COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'type', alert_type,
                    'severity', severity,
                    'location', jsonb_build_array(lat, lon)
                )
            ),
            '[]'::jsonb
        )
    )
    INTO result
    FROM alerts;

    RETURN COALESCE(result, jsonb_build_object('risk_level', 'Low', 'alerts', '[]'::jsonb));
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION get_health_forecast(p_polygon JSONB, p_months INT DEFAULT 6)
RETURNS JSONB AS $$
DECLARE
    poly GEOMETRY;
    result JSONB;
BEGIN
    poly := json_polygon_to_geom(p_polygon);

    WITH monthly AS (
        SELECT
            to_char(date_trunc('month', fm.metric_timestamp), 'YYYY-MM') AS month,
            COALESCE(AVG(fm.forecast_health), AVG(fm.health_score), 0) AS health_score
        FROM forest_metrics fm
        WHERE ST_Intersects(fm.geometry, poly)
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT p_months
    )
    SELECT COALESCE(
        jsonb_agg(
            jsonb_build_object('month', month, 'health_score', ROUND(health_score::numeric, 2))
            ORDER BY month
        ),
        '[]'::jsonb
    )
    INTO result
    FROM monthly;

    RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION upsert_demo_polygon_cache(
    p_cache_key TEXT,
    p_polygon JSONB,
    p_response JSONB
)
RETURNS VOID AS $$
DECLARE
    poly GEOMETRY;
BEGIN
    poly := json_polygon_to_geom(p_polygon);

    INSERT INTO demo_polygon_cache (cache_key, polygon, response)
    VALUES (p_cache_key, poly, p_response)
    ON CONFLICT (cache_key)
    DO UPDATE SET
        polygon = EXCLUDED.polygon,
        response = EXCLUDED.response;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_demo_polygon_cache(p_cache_key TEXT)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT response INTO result
    FROM demo_polygon_cache
    WHERE cache_key = p_cache_key;

    RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE VIEW v_ndvi_latest AS
SELECT DISTINCT ON (ff.grid_id)
    ff.grid_id,
    ff.geometry,
    ff.ndvi,
    ff.ndmi,
    ff.captured_at
FROM forest_features ff
ORDER BY ff.grid_id, ff.captured_at DESC;

CREATE OR REPLACE VIEW v_risk_zones AS
SELECT
    fm.grid_id,
    fm.geometry,
    fm.risk_level,
    fm.health_score,
    fm.metric_timestamp
FROM forest_metrics fm
WHERE fm.risk_level IN ('Moderate', 'High');

CREATE OR REPLACE FUNCTION get_system_status()
RETURNS JSONB AS $$
DECLARE
    feature_count BIGINT;
    metric_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO feature_count FROM forest_features;
    SELECT COUNT(*) INTO metric_count FROM forest_metrics;

    RETURN jsonb_build_object(
        'satellite_data_loaded', (feature_count > 0),
        'feature_dataset_rows', feature_count,
        'model_status', CASE WHEN metric_count > 0 THEN 'ready' ELSE 'warming' END
    );
END;
$$ LANGUAGE plpgsql STABLE;
