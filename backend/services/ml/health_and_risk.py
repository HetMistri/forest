def calculate_health_score(ndvi: float, ndmi: float) -> int:
    """
    Calculates a weighted index for forest health.
    Score = (NDVI * 0.6) + (NDMI * 0.4)
    Output is normalized to a 0-100 scale.
    """
    # Assuming standard NDVI/NDMI valid range is -1 to 1, but for terrestrial forests it's 0 to 1
    # Scale both to 100 max
    ndvi_scaled = max(0, min(1, ndvi)) * 100
    ndmi_scaled = max(0, min(1, ndmi)) * 100
    
    score = (ndvi_scaled * 0.6) + (ndmi_scaled * 0.4)
    return int(round(score))

def detect_deforestation_risk(historical_ndvi_list: list) -> str:
    """
    Evaluates risk based on short term NDVI drop.
    If NDVI drops > 25% over a 2-week window (last two distinct periods).
    """
    if not historical_ndvi_list or len(historical_ndvi_list) < 2:
        return "Risk: LOW"
        
    # Compare the most recent distinct periods
    # e.g [-1] is current (latest), [-2] is 2 weeks ago
    current_ndvi = historical_ndvi_list[-1]
    previous_ndvi = historical_ndvi_list[-2]
    
    if previous_ndvi <= 0:
        return "Risk: LOW"
        
    drop_percentage = (previous_ndvi - current_ndvi) / previous_ndvi
    
    if drop_percentage > 0.25:
        return "Risk: HIGH (Potential Logging/Fire)"
        
    return "Risk: LOW"
