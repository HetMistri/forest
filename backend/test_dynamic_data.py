import pandas as pd
import sys
from pathlib import Path

# Provide access to the ML Bridge
BACKEND_ROOT = Path("Y:/forest/backend").resolve()
sys.path.insert(0, str(BACKEND_ROOT))

from services.ml_bridge import MLBridge

def test_dynamic_data():
    print("--- Testing Model on True Dynamic Earth Engine Features ---")
    data_path = Path("Y:/forest/data/processed/features.csv")
    
    if not data_path.exists():
        print(f"ERROR: Cannot find live feature data at {data_path}")
        return

    print("Loading live satellite features...")
    # Load just a random sample to test
    df = pd.read_csv(data_path).sample(20, random_state=42)
    
    ml = MLBridge()
    model_path = BACKEND_ROOT / "services" / "ml" / "density_model.pkl"
    ml.load_model(model_path)
    
    print("\n[Results]")
    print(f"{'NDVI':<6} | {'NDMI':<6} | {'VV':<7} | {'VH':<7} | {'TREES/HA':<8} | {'HLTH':<4} | {'RISK':<8} | {'SPECIES (Spatial DB Mock)'}")
    print("-" * 90)
    
    for _, row in df.iterrows():
        # Extrapolate missing SAR metrics dynamically based on standard ranges
        # because the raw GEE output only dumps NDVI/NDMI into the current CSV
        ndvi = float(row.get('ndvi', 0.5))
        ndmi = float(row.get('ndmi', 0.3))
        vv = float(row.get('vv', -12.0 + (ndvi * 5)))
        vh = float(row.get('vh', -18.0 + (ndvi * 8)))
        sar_ratio = float(row.get('sar_ratio', vv / (vh if vh != 0 else -1e-5)))

        density = ml.predict_density(
            ndvi=ndvi,
            ndmi=ndmi,
            vv=vv,
            vh=vh,
            sar_ratio=sar_ratio
        )
        
        health = ml.compute_health(ndvi, ndmi)
        # We mock 5 months of stable NDVI to generate baseline risk
        risk_status = ml.detect_risk([ndvi, ndvi, ndvi, ndvi, ndvi])
        risk_level = ml.classify_risk_level(risk_status)
        
        # The true architecture uses a PostGIS spatial join for species. 
        # For this terminal demo, we infer it geographically from density.
        if density > 180:
            species = "Teak Dominant"
        elif density > 100:
            species = "Mixed Deciduous"
        else:
            species = "Bamboo/Scrub"
        
        print(f"{ndvi:<6.3f} | {ndmi:<6.3f} | {vv:<7.2f} | {vh:<7.2f} | {density:<8.1f} | {health:<4} | {risk_level:<8} | {species}")

if __name__ == "__main__":
    test_dynamic_data()
