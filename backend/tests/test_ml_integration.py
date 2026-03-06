"""Integration tests verifying the ML bridge works within the backend."""
from __future__ import annotations

import sys
import os
os.environ["STRICT_PROD_MODE"] = "false"
from pathlib import Path

import pytest

# Ensure backend root is in sys.path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.ml_bridge import MLBridge

MODEL_PATH = BACKEND_ROOT / "services" / "ml" / "density_model.pkl"


@pytest.fixture(scope="module")
def ml():
    bridge = MLBridge()
    bridge.load_model(MODEL_PATH)
    return bridge


# ── Model Loading ────────────────────────────────────────────────────────────

def test_ml_bridge_loads_model(ml: MLBridge) -> None:
    assert ml.model_loaded is True


# ── Density Prediction ───────────────────────────────────────────────────────

def test_ml_bridge_density_prediction(ml: MLBridge) -> None:
    density = ml.predict_density(ndvi=0.65, ndmi=0.40, vv=-7.5, vh=-14.2, sar_ratio=0.52)
    assert isinstance(density, float)
    assert 0.0 <= density <= 600.0, f"Density {density} out of realistic range"


def test_ml_bridge_total_trees(ml: MLBridge) -> None:
    density = ml.predict_density()
    total = ml.calculate_total_trees(density, area_km2=5.1)
    assert total > 0
    assert isinstance(total, int)


# ── Health Score ─────────────────────────────────────────────────────────────

def test_ml_bridge_health_score(ml: MLBridge) -> None:
    score = ml.compute_health(0.72, 0.41)
    assert isinstance(score, int)
    assert 0 <= score <= 100, f"Health score {score} out of range"


# ── Risk Detection ───────────────────────────────────────────────────────────

def test_ml_bridge_risk_detection_high(ml: MLBridge) -> None:
    # Sharp NDVI drop should flag HIGH risk
    risk = ml.detect_risk([0.75, 0.72, 0.70, 0.68, 0.35])
    assert "HIGH" in risk.upper()


def test_ml_bridge_risk_detection_low(ml: MLBridge) -> None:
    # Stable NDVI should flag LOW risk
    risk = ml.detect_risk([0.70, 0.69, 0.68, 0.67, 0.66])
    assert "LOW" in risk.upper()


def test_ml_bridge_classify_risk_level(ml: MLBridge) -> None:
    assert ml.classify_risk_level("Risk: HIGH (Potential Logging/Fire)") == "High"
    assert ml.classify_risk_level("Risk: LOW") == "Low"


# ── Forecast ─────────────────────────────────────────────────────────────────

def test_ml_bridge_forecast(ml: MLBridge) -> None:
    scores = ml.forecast_health()
    assert isinstance(scores, list)
    assert len(scores) == 6
    for s in scores:
        assert isinstance(s, int)


def test_ml_bridge_forecast_monthly_points(ml: MLBridge) -> None:
    points = ml.forecast_as_monthly_points()
    assert len(points) == 6
    for p in points:
        assert "month" in p
        assert "health_score" in p


# ── API Endpoint Integration ────────────────────────────────────────────────

def test_api_endpoints_use_ml() -> None:
    """Hit all POST endpoints via TestClient and verify ML-computed responses."""
    import os
    os.environ["STRICT_PROD_MODE"] = "false"
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    polygon = {
        "polygon": [
            [73.90, 20.20],
            [73.91, 20.20],
            [73.91, 20.21],
            [73.90, 20.20],
        ]
    }

    # /forest-metrics
    resp = client.post("/forest-metrics", json=polygon)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tree_density"] >= 0
    assert data["health_score"] >= 0

    # /tree-density
    resp = client.post("/tree-density", json=polygon)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tree_density"] >= 0
    assert data["total_trees"] >= 0

    # /health-score
    resp = client.post("/health-score", json=polygon)
    assert resp.status_code == 200
    data = resp.json()
    assert data["health_score"] >= 0

    # /risk-alerts
    resp = client.post("/risk-alerts", json=polygon)
    assert resp.status_code == 200

    # /health-forecast
    resp = client.post("/health-forecast", json=polygon)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["forecast"]) == 6

    # /demo-metrics
    resp = client.get("/demo-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tree_count"] >= 0
    assert data["health_score"] >= 0

    # /system-status
    resp = client.get("/system-status")
    assert resp.status_code == 200
