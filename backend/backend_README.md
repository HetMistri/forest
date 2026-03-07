# ⚙️ Forest Platform - Backend API

This is the backend service for the Forest Intelligence Platform. It acts as the bridge between our Machine Learning pipeline and the Frontend dashboard, serving pre-computed metrics and handling geospatial queries.

## 🛠️ Tech Stack
* **Framework:** FastAPI (Python)
* **Data Handling:** Pandas, GeoPandas

## 📡 API Architecture

The backend receives polygon coordinates from the frontend and returns comprehensive forest metrics. 

### Core Endpoints

| Endpoint | Method | Input | Output / Description |
| :--- | :--- | :--- | :--- |
| `/forest-metrics` | `POST` | Polygon Coordinates | Aggregated summary of all metrics for the area. |
| `/tree-density` | `POST` | Polygon Coordinates | Returns `tree_count` and `density` (trees/hectare). |
| `/health-score` | `POST` | Polygon Coordinates | Returns a health score (0-100) based on NDVI/NDMI. |
| `/risk-alerts` | `POST` | Polygon Coordinates | Identifies risk zones based on recent anomaly detection. |
| `/species-composition` | `POST` | Polygon Coordinates | Returns regional ecosystem estimates (e.g., Teak: 58%, Bamboo: 27%). |

## ⚡ Caching & Demo Optimization
The backend is designed to support a highly stable pitch environment. 
When the primary Dang district demo polygon is queried, the backend intercepts the request and instantly serves **pre-cached, high-fidelity data**:
* **Area:** 5.1 km²
* **Estimated Trees:** 84,200
* **Density:** 162 trees/hectare
* **Health Score:** 68 (Moderate-to-Healthy)
* **Risk Zones:** 2

## 🚀 Setup Instructions
1. Navigate to the backend directory: `cd backend`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the FastAPI server: `uvicorn main:app --reload`
