from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

POLYGON = {
    "polygon": [
        [73.90, 20.20],
        [73.91, 20.20],
        [73.91, 20.21],
        [73.90, 20.20],
    ]
}


def test_forest_metrics_contract_shape() -> None:
    response = client.post("/forest-metrics", json=POLYGON)
    assert response.status_code == 200

    payload = response.json()
    assert set(payload.keys()) == {
        "area_km2",
        "tree_count",
        "tree_density",
        "health_score",
        "risk_level",
        "species_distribution",
        "forecast_health",
    }
    assert set(payload["species_distribution"].keys()) == {
        "teak",
        "bamboo",
        "mixed_deciduous",
    }


def test_forest_metrics_rejects_invalid_polygon_point_shape() -> None:
    invalid_payload = {"polygon": [[73.90, 20.20, 10.0], [73.91, 20.20], [73.91, 20.21], [73.90, 20.20]]}
    response = client.post("/forest-metrics", json=invalid_payload)
    assert response.status_code == 422


def test_supporting_post_endpoints() -> None:
    post_endpoints = [
        "/tree-density",
        "/health-score",
        "/risk-alerts",
        "/species-composition",
        "/health-forecast",
    ]

    for endpoint in post_endpoints:
        response = client.post(endpoint, json=POLYGON)
        assert response.status_code == 200, f"{endpoint} failed with {response.text}"


def test_supporting_get_endpoints() -> None:
    get_endpoints = ["/ndvi-map", "/risk-zones", "/system-status", "/demo-metrics"]

    for endpoint in get_endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint} failed with {response.text}"


def test_docs_and_openapi_available() -> None:
    docs = client.get("/docs")
    openapi = client.get("/openapi.json")

    assert docs.status_code == 200
    assert openapi.status_code == 200
