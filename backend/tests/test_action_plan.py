from fastapi.testclient import TestClient
from api.main import app
import os

client = TestClient(app)

def test_action_plan_no_api_key():
    # Temporarily remove API key if present
    original_key = os.environ.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]

    payload = {
        "tree_count": 500,
        "tree_density": 100,
        "health_score": 50,
        "risk_level": "High",
        "species_distribution": {"teak": 50, "bamboo": 50}
    }
    response = client.post("/action-plan", json=payload)
    
    # Should throw a 500 if key is missing or not installed
    assert response.status_code == 500
    assert "GEMINI_API_KEY" in response.json()["detail"] or "google-generativeai" in response.json()["detail"]

    # Restore key
    if original_key is not None:
        os.environ["GEMINI_API_KEY"] = original_key
