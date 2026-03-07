# 🗺️ Forest Platform - Frontend Dashboard

This directory contains the interactive mapping dashboard for the Forest Intelligence Platform. It allows users to visualize satellite data, draw polygons, and instantly view ecosystem metrics.



## 🛠️ Tech Stack
* **Framework:** React
* **Mapping Engine:** Mapbox GL JS

## 🎨 UI/UX Features

### 1. Interactive Map Layers
* **Tree Density Heatmap:** Visual representation of forest thickness.
* **Forest Health Map:** Color-coded zones based on health scores (0–40 Degraded, 40–70 Moderate, 70–100 Healthy).
* **Risk Hotspots:** Highlighted markers for rapid deforestation anomalies.
* **Satellite Overlay:** High-resolution optical base map.

### 2. Analytical Side Panel
When a user selects a polygon (or our pre-computed Dang district demo zone), the side panel updates instantly with:
* Total Estimated Trees
* Forest Health Score
* Active Risk Alerts
* Species Composition Breakdown (Teak, Bamboo, Mixed)
* 6-Month Health Forecast chart

## 🚀 Setup Instructions
1. Navigate to the frontend directory: `cd frontend`
2. Install dependencies: `npm install`
3. Add your Mapbox Access Token to `.env`: `REACT_APP_MAPBOX_TOKEN=your_token_here`
4. Start the development server: `npm start`
