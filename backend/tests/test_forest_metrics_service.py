from __future__ import annotations

from services.forest_metrics_service import ForestMetricsService


DANG_POLYGON = [
    [73.90, 20.20],
    [73.91, 20.20],
    [73.91, 20.21],
    [73.90, 20.20],
]


def test_get_forest_metrics_uses_db_aggregate_row(monkeypatch) -> None:
    service = ForestMetricsService()

    monkeypatch.setattr(service, "_prepare_region_data", lambda polygon: None)

    def fake_fetch_one(query: str, params=None):
        if "FROM get_forest_metrics" in query:
            return {
                "area_km2": 5.1,
                "tree_count": 84200,
                "tree_density": 162.0,
                "health_score": 68.0,
                "risk_level": "Moderate",
                "species_distribution": {
                    "teak": 58,
                    "bamboo": 27,
                    "mixed_deciduous": 15,
                },
                "forecast_health": 64,
            }
        return None

    monkeypatch.setattr(service, "_fetch_one", fake_fetch_one)

    result = service.get_forest_metrics(DANG_POLYGON)

    assert result.area_km2 == 5.1
    assert result.tree_count == 84200
    assert result.tree_density == 162.0
    assert result.health_score == 68.0
    assert result.risk_level == "Moderate"
    assert result.species_distribution == {
        "teak": 58.0,
        "bamboo": 27.0,
        "mixed_deciduous": 15.0,
    }
    assert result.forecast_health == 64.0


def test_get_forest_metrics_demo_cache_fast_path(monkeypatch) -> None:
    service = ForestMetricsService()
    service.demo_cache_enabled = True

    prepare_called = {"value": False}

    def fake_prepare_region_data(polygon):
        prepare_called["value"] = True

    def fake_fetch_one(query: str, params=None):
        if "FROM demo_polygon_cache" in query:
            return {
                "response": {
                    "area_km2": 5.1,
                    "tree_count": 84200,
                    "tree_density": 162,
                    "health_score": 68,
                    "risk_level": "Moderate",
                    "species_distribution": {
                        "teak": 58,
                        "bamboo": 27,
                        "mixed_deciduous": 15,
                    },
                    "forecast_health": 64,
                }
            }
        return None

    monkeypatch.setattr(service, "_prepare_region_data", fake_prepare_region_data)
    monkeypatch.setattr(service, "_fetch_one", fake_fetch_one)

    result = service.get_forest_metrics(DANG_POLYGON)

    assert result.tree_count == 84200
    assert result.forecast_health == 64.0
    assert result.species_distribution["mixed_deciduous"] == 15.0
    assert prepare_called["value"] is False
