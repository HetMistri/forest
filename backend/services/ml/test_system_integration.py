import sys
from pathlib import Path

# Add backend directory to sys.path to allow absolute imports
repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from services.ml_bridge import MLBridge
from services.ml.health_and_risk import calculate_health_score, detect_deforestation_risk
import json

def simulate_pipeline():
    print("--- Running ML Pipeline Simulation ---")
    mb = MLBridge.get_instance()
    
    model_path = Path(__file__).parent / "density_model.pkl"
    if model_path.exists():
        mb.load_model(model_path)
    
    # 1. Simulate an incoming feature extraction row (from data/processed/features.csv)
    mock_feature_row = {
        "grid_id": "cell_10_42",
        "lat": 20.75,
        "lon": 73.80,
        "ndvi": 0.68,
        "ndmi": 0.45,
        "evi": 0.55,
        "vv": -8.1,
        "vh": -15.3,
        "sar_ratio": 0.53
    }
    
    historical_ndvi = [0.72, 0.70, 0.69, mock_feature_row["ndvi"] + 0.1, mock_feature_row["ndvi"]]

    # 2. Run Tree Density Model
    density = mb.predict_density(
        ndvi=mock_feature_row["ndvi"],
        ndmi=mock_feature_row["ndmi"],
        vv=mock_feature_row["vv"],
        vh=mock_feature_row["vh"],
        sar_ratio=mock_feature_row["sar_ratio"]
    )

    # 3. Run Forest Health Model
    health = calculate_health_score(mock_feature_row["ndvi"], mock_feature_row["ndmi"])

    # 4. Run Risk Detection (>25% drop)
    risk_string = detect_deforestation_risk(historical_ndvi)
    risk_level = mb.classify_risk_level(risk_string)

    # 5. Output Delivered to Backend
    # Specifications require: { grid_id, tree_density, health_score, risk_level }
    
    final_output = {
        "grid_id": mock_feature_row["grid_id"],
        "tree_density": round(float(density), 2),
        "health_score": health,
        "risk_level": risk_level
    }
    
    print("\n[SUCCESS] Final Output delivered to Backend:")
    print(json.dumps(final_output, indent=2))

if __name__ == "__main__":
    simulate_pipeline()
