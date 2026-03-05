import pandas as pd

def process_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts raw bands to standardized indices according to the AMNEX protocol.
    
    Expected Input DataFrame columns:
    [block_id, date, B4_Red, B8_NIR, B11_SWIR, VV, VH]
    
    Output DataFrame columns:
    [NDVI, NDMI, VV, VH, SAR_Ratio]
    """
    # 1. NDVI (Vegetation Health): (B8_NIR - B4_Red) / (B8_NIR + B4_Red)
    # Using small epsilon to avoid division by zero
    eps = 1e-8
    ndvi = (df['B8_NIR'] - df['B4_Red']) / (df['B8_NIR'] + df['B4_Red'] + eps)
    
    # 2. NDMI (Moisture Index): (B8_NIR - B11_SWIR) / (B8_NIR + B11_SWIR)
    ndmi = (df['B8_NIR'] - df['B11_SWIR']) / (df['B8_NIR'] + df['B11_SWIR'] + eps)
    
    # 3. SAR Structural Ratio: VV / VH
    sar_ratio = df['VV'] / (df['VH'] + eps)
    
    # 4. Feature DataFrame
    processed_df = pd.DataFrame({
        'NDVI': ndvi,
        'NDMI': ndmi,
        'VV': df['VV'],
        'VH': df['VH'],
        'SAR_Ratio': sar_ratio
    })
    
    return processed_df
