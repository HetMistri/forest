# 🌲 Forest Intelligence Platform for Dang District

[![GitHub Repo](https://img.shields.io/badge/GitHub-HetMistri%2Fforest-blue)](https://github.com/HetMistri/forest)

Welcome to the **Forest Intelligence Platform**, an all-weather satellite monitoring system designed to estimate tree density, assess forest health, analyze ecosystem composition, and predict future risk trends specifically for the Dang district.

## ⚠️ The Problem
Traditional forest monitoring heavily relies on optical satellites. While effective in clear skies, these systems fail completely during the monsoon season due to heavy cloud cover—precisely when monitoring is often most critical. 

## 💡 Our Solution
Our key technical differentiator is the **fusion of optical and radar satellite data**. By combining Sentinel-2 (optical) with Sentinel-1 (Synthetic Aperture Radar / SAR), our platform penetrates cloud cover to provide **uninterrupted, all-weather forest intelligence**.



## ✨ Key Features
* **Tree Density Estimation:** Quantitative modeling of trees per hectare using Random Forest.
* **Forest Health Monitoring:** Real-time health scoring based on vegetation indices (NDVI, NDMI).
* **Deforestation Risk Alerts:** Automated anomaly detection to flag rapid vegetation drops (>25%).
* **Predictive Forecasting:** 6-month forest health projections using time-series analysis (ARIMA/Prophet).
* **Ecosystem Composition:** Integration with Forest Survey of India (FSI) and Bhuvan data for scientifically defensible species distribution mapping.

## 🏗️ Project Structure
This project is divided into three core microservices. Check their respective READMEs for setup and architecture details:
1.  **[Machine Learning Pipeline](./ml/ml_README.md):** Google Earth Engine data ingestion, feature extraction, and predictive modeling.
2.  **[Backend API](./backend/backend_README.md):** FastAPI server handling metric calculations and serving data.
3.  **[Frontend Dashboard](./frontend/frontend_README.md):** Interactive React & Mapbox UI for geospatial visualization.

## 🚀 Live Demo Strategy
To ensure a flawless presentation, our live demo utilizes a pre-computed polygon inside the Dang district (5.1 km²). This guarantees instant, zero-latency responses without risking real-time satellite query timeouts during the pitch. 

---
*Built for the Dang District ecosystem.*

