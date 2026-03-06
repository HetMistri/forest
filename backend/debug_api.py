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

endpoints = [
    "/forest-metrics",
    "/tree-density",
    "/health-score",
    "/risk-alerts",
    "/health-forecast",
    "/demo-metrics",
    "/system-status"
]

for endpoint in endpoints:
    if "metrics" in endpoint or "status" in endpoint:
        try:
            resp = client.get(endpoint) if endpoint in ["/demo-metrics", "/system-status"] else client.post(endpoint, json=polygon)
            print(f"{endpoint} response: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Error: {resp.json()}")
        except Exception as e:
            print(f"Crash on {endpoint}: {e}")
    else:
        try:
            resp = client.post(endpoint, json=polygon)
            print(f"{endpoint} response: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Error: {resp.json()}")
        except Exception as e:
            print(f"Crash on {endpoint}: {e}")
