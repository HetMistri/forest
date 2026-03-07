# 🧠 Forest Platform - Machine Learning & Data Pipeline

This module is the scientific core of the platform. It handles satellite data ingestion, feature fusion, tree density estimation, and predictive forecasting. By fusing optical and radar data, we achieve true all-weather monitoring.

## 🛰️ Data Sources
1.  **Sentinel-2 (Optical):** Used for vegetation health indices (NDVI, NDMI, EVI).
2.  **Sentinel-1 (SAR / Radar):** Used for structural biomass estimation (VV backscatter, VH backscatter, VV/VH ratio). Penetrates clouds during the monsoon.
3.  **FSI & Bhuvan Data:** Ground-truth and regional data used to estimate species composition (Teak, Bamboo, etc.) without relying on unreliable satellite species-detection.

## 🔄 Technical Pipeline

### 1. Data Ingestion & Processing
* Powered by **Google Earth Engine (GEE)**.
* We extract features from both satellites and aggregate pixels into standard **hectare blocks**.
* Calculate block-level features: NDVI mean, NDVI trend, moisture index, and SAR backscatter.

### 2. Density Estimation
* **Model:** `RandomForestRegressor`
* **Approach:** We calculate density per hectare rather than attempting individual tree counting (which is error-prone at satellite resolutions).
* **Output:** `tree_density_per_hectare` (Total trees = density × area).

### 3. Health & Anomaly Detection
* **Health Score:** A weighted index combining NDVI and NDMI (0-100 scale).
* **Risk Detection:** Rule-based anomaly detection. Any NDVI drop > 25% within a short time-frame immediately flags a hotspot.

### 4. Time-Series Forecasting
* **Model:** ARIMA / Prophet
* **Input:** Historical NDVI/health time-series data.
* **Output:** A 6-month projection of forest health trends.

## 🚀 Execution Note
This pipeline is designed to pre-compute the necessary metrics and push them to the backend, ensuring zero-latency data delivery during live interactions.
