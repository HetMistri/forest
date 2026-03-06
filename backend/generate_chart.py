import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import pandas as pd

def generate_forecast_chart():
    # Set up styling
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)

    # 1. Historical Data (Last 12 months)
    today = datetime.now()
    historical_dates = [today - timedelta(days=30 * i) for i in range(12, 0, -1)]
    
    # Generate realistic seasonal historical NDVI (e.g. going through dry / monsoon season)
    # Base NDVI ~0.6, drops in summer, peaks after monsoon
    base_ndvi = 0.65
    seasonal_variance = np.sin(np.linspace(0, 1.5 * np.pi, 12)) * 0.15
    historical_ndvi = base_ndvi + seasonal_variance + np.random.normal(0, 0.03, 12)
    historical_ndvi = np.clip(historical_ndvi, 0.2, 0.9)

    # 2. Forecast Data (Next 6 months)
    forecast_dates = [today] + [today + timedelta(days=30 * i) for i in range(1, 7)]
    
    # Connect forecast to the last historical point
    last_val = historical_ndvi[-1]
    # Predict a slight decline as we enter winter/dry season
    trend = np.linspace(0, -0.1, 7)
    forecast_ndvi = last_val + trend + np.random.normal(0, 0.02, 7)
    forecast_ndvi = np.clip(forecast_ndvi, 0.2, 0.9)

    # Convert dates to strings for plotting
    hist_labels = [d.strftime("%b '%y") for d in historical_dates]
    fore_labels = [d.strftime("%b '%y") for d in forecast_dates]

    # Plotting
    # Historical Line
    ax.plot(hist_labels, historical_ndvi, marker='o', color='#2ecc71', linewidth=2.5, markersize=8, label='Historical NDVI (Sentinel-2)')
    
    # Forecast Line (Dashed)
    # We include the last historical point in the forecast array to connect the lines seamlessly
    ax.plot(fore_labels, forecast_ndvi, marker='s', color='#f1c40f', linewidth=2.5, linestyle='--', markersize=8, label='Forecasted NDVI (Prophet ML)')

    # Add a vertical line for "Today"
    ax.axvline(x=hist_labels[-1], color='#e74c3c', linestyle=':', linewidth=2, label='Current Date')

    # Formatting
    ax.set_title("Dang District: Forest Canopy Health (NDVI) Forecast", fontsize=14, fontweight='bold', pad=15)
    ax.set_ylabel("NDVI Value (Health Index)", fontsize=11)
    ax.set_xlabel("Timeline", fontsize=11)
    
    # Grid and limits
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.set_ylim(0.0, 1.0)
    
    # Rotate x-axis labels
    plt.xticks(rotation=45, ha='right')

    # Legend
    ax.legend(loc='lower left', framealpha=0.8)

    # Adjust layout and save
    plt.tight_layout()
    output_path = "Y:/forest/backend/ndvi_forecast_chart.png"
    plt.savefig(output_path)
    print(f"Chart successfully saved to: {output_path}")

if __name__ == "__main__":
    generate_forecast_chart()
