"""
ML Bridge — single integration layer between FastAPI backend and ML pipeline.

Fallback chain: DB → ML inference → hardcoded defaults.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MLBridge:
    """Singleton-style bridge that holds the loaded model and exposes ML inference."""

    _instance: MLBridge | None = None

    def __init__(self) -> None:
        self._model: Any = None
        self.model_loaded: bool = False

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> MLBridge:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Model Loading ────────────────────────────────────────────────────

    def load_model(self, model_path: str | Path) -> bool:
        """Load the pre-trained RandomForestRegressor from a .pkl file."""
        try:
            import joblib

            resolved = Path(model_path).resolve()
            self._model = joblib.load(resolved)
            self.model_loaded = True
            logger.info("ML model loaded from %s", resolved)
            return True
        except Exception as exc:
            logger.warning("Failed to load ML model from %s: %s", model_path, exc)
            self.model_loaded = False
            return False

    # ── Density Prediction ───────────────────────────────────────────────

    def predict_density(
        self,
        ndvi: float = 0.65,
        ndmi: float = 0.40,
        vv: float | None = None,
        vh: float | None = None,
        sar_ratio: float = 0.52,
    ) -> float:
        """
        Predict tree density (trees/hectare) using the trained model.

        Falls back to 162.0 if model is not loaded.
        """
        if not self.model_loaded or self._model is None:
            logger.warning("Density prediction using fallback constant: model not loaded")
            return 162.0

        try:
            # Reconstruct missing VV/VH if only SAR ratio is provided (e.g. from DB)
            if vv is None or vh is None:
                vh_assumed = -14.2  # typical baseline
                vv_assumed = vh_assumed * sar_ratio
                vv = vv if vv is not None else vv_assumed
                vh = vh if vh is not None else vh_assumed

            features = pd.DataFrame(
                [{"NDVI": ndvi, "NDMI": ndmi, "VV": vv, "VH": vh, "SAR_Ratio": sar_ratio}]
            )
            prediction = float(self._model.predict(features)[0])
            # Clamp to realistic range
            clamped = max(0.0, min(500.0, round(prediction, 2)))
            logger.info(
                "Density prediction succeeded (ndvi=%.3f, ndmi=%.3f, vv=%.3f, vh=%.3f, sar_ratio=%.3f, density=%.2f)",
                ndvi,
                ndmi,
                vv,
                vh,
                sar_ratio,
                clamped,
            )
            return clamped
        except Exception as exc:
            logger.warning("Density prediction failed: %s", exc)
            return 162.0

    def calculate_total_trees(self, density_per_ha: float, area_km2: float) -> int:
        """Total trees = density × area (converted to hectares)."""
        area_ha = area_km2 * 100
        return int(density_per_ha * area_ha)

    # ── Health Score ─────────────────────────────────────────────────────

    def compute_health(self, ndvi: float = 0.72, ndmi: float = 0.41) -> int:
        """
        Compute forest health score (0-100) using ML health module.

        Falls back to 68 on error.
        """
        try:
            from .ml.health_and_risk import calculate_health_score

            score = calculate_health_score(ndvi, ndmi)
            logger.info("Health score computed (ndvi=%.3f, ndmi=%.3f, score=%s)", ndvi, ndmi, score)
            return score
        except Exception as exc:
            logger.warning("Health score computation failed: %s", exc)
            return 68

    # ── Risk Detection ───────────────────────────────────────────────────

    def detect_risk(self, historical_ndvi: list[float] | None = None) -> str:
        """
        Detect deforestation risk from NDVI time series.

        Falls back to "Risk: LOW" on error.
        """
        if historical_ndvi is None:
            historical_ndvi = [0.75, 0.72, 0.70, 0.68, 0.65]

        try:
            from .ml.health_and_risk import detect_deforestation_risk

            risk = detect_deforestation_risk(historical_ndvi)
            logger.info("Risk detection computed (samples=%d, risk=%s)", len(historical_ndvi), risk)
            return risk
        except Exception as exc:
            logger.warning("Risk detection failed: %s", exc)
            return "Risk: LOW"

    def classify_risk_level(self, risk_str: str) -> str:
        """Convert ML risk string to API-level severity."""
        if "HIGH" in risk_str.upper():
            return "High"
        elif "MODERATE" in risk_str.upper():
            return "Moderate"
        return "Low"

    # ── Forecast ─────────────────────────────────────────────────────────

    def forecast_health(self, historical_df: pd.DataFrame | None = None) -> list[int]:
        """
        Forecast 6-month health scores using Prophet/mock.

        Falls back to a static list on error.
        """
        try:
            from .ml.forecast import predict_future_health

            forecast = predict_future_health(historical_df)
            logger.info("Health forecast computed (points=%d)", len(forecast))
            return forecast
        except Exception as exc:
            logger.warning("Forecast failed: %s", exc)
            return [66, 65, 64, 63, 62, 61]

    def forecast_as_monthly_points(
        self, historical_df: pd.DataFrame | None = None
    ) -> list[dict[str, Any]]:
        """Return forecast as a list of {month, health_score} dicts for the API."""
        scores = self.forecast_health(historical_df)
        now = datetime.now()
        points = []
        for i, score in enumerate(scores):
            month_dt = now + timedelta(days=30 * (i + 1))
            points.append(
                {"month": month_dt.strftime("%Y-%m"), "health_score": float(score)}
            )
        return points

    # ── Feature Processing ───────────────────────────────────────────────

    def process_raw_features(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Process raw satellite bands into standardized indices.

        Falls back to empty DataFrame on error.
        """
        try:
            from .ml.feature_pipeline import process_features

            return process_features(raw_df)
        except Exception as exc:
            logger.warning("Feature processing failed: %s", exc)
            return pd.DataFrame()

    # ── System Status ────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return ML subsystem status for the /system-status endpoint."""
        status = {
            "model_loaded": self.model_loaded,
            "model_type": type(self._model).__name__ if self._model else "none",
        }
        logger.info("ML status requested: %s", status)
        return status
