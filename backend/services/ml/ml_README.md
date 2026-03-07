# Forest ML Module v0.1 Beta — Density, Health, Risk & Forecast

This module contains the ML and analytical core used by the backend for feature processing, density estimation, health/risk scoring, and forecast generation.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![scikit--learn](https://img.shields.io/badge/scikit--learn-ML-orange.svg)](https://scikit-learn.org/)
[![NumPy](https://img.shields.io/badge/NumPy-Scientific-blue.svg)](https://numpy.org/)
[![Pandas](https://img.shields.io/badge/Pandas-Data-black.svg)](https://pandas.pydata.org/)

---

## 📋 Table of Contents

- 🚀 What ML Module Does
- 🧠 How It Works (Simple Explanation)
- 📦 Files and Entry Points
- 🧭 Main Commands
- 🧪 Typical First-Time Usage
- ⚙️ Requirements
- 🛡️ Reliability Notes
- ✨ Features
- 🔒 Model & Logic Notes

---

# 🚀 What ML Module Does

ML module provides:

✅ Tree density prediction from NDVI/NDMI/SAR features

✅ Health score computation

✅ Deforestation risk labeling

✅ Forecast generation for future health trends

✅ Feature pipeline helpers for backend service integration

---

# 🧠 How It Works (Simple Explanation)

At a high level:

🛰️ Satellite features are prepared (optical + SAR)

🌲 A trained model estimates tree density per hectare

💚 Health score is derived from vegetation indicators

⚠️ Risk level is derived from trend/anomaly rules

📉 Forecast module outputs future health points

---

# 📦 Files and Entry Points

- `feature_pipeline.py` — feature transformations
- `health_and_risk.py` — health score and risk logic
- `forecast.py` — forecast generation
- `train_realistic_model.py` — model training utility
- `density_model.pkl` — trained model artifact

---

# 🧭 Main Commands

From `backend/`:

- `uv run python services/ml/train_realistic_model.py`

Project-level pipeline trigger:

- `python scripts/run_backend_pipeline.py`

Smoke pipeline:

- `uv run python scripts/run_smoke_pipeline.py`

---

# 🧪 Typical First-Time Usage

1. Ensure backend dependencies are installed (`uv sync`)
2. Run training script if retraining is needed
3. Execute smoke pipeline to produce features
4. Call backend endpoints (`/forest-metrics`, `/health-score`) to validate outputs

---

# ⚙️ Requirements

🐍 Python 3.11+

📦 scikit-learn, pandas, numpy

🛰️ Earth Engine access for full ingestion workflows

---

# 🛡️ Reliability Notes

- Density predictions are clamped to a realistic range in service logic.
- If model loading fails, fallback constants are used to keep API responsive.
- Outputs are estimates from model/feature inputs and should be validated against field data for accuracy claims.

---

# ✨ Features

🧮 RandomForest-based density estimation

💚 Health and risk scoring utilities

📈 Forecast point generation for API responses

🔌 Clean integration through backend `MLBridge`

---

# 🔒 Model & Logic Notes

- Tree count is derived from: `density_per_ha × area_ha`
- Health/risk values are computed from vegetation and trend indicators
- Model artifact loading is optional but recommended for realistic outputs
