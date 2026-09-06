import os
import joblib
import numpy as np
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "risk_model.pkl")

def get_risk_category(score: int) -> str:
    if score >= 75:
        return "CRITICAL"
    elif score >= 55:
        return "HIGH"
    elif score >= 35:
        return "MODERATE"
    else:
        return "LOW"

def predict_soil_risk(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Features expected:
    rainfall_24h, rainfall_7d, soil_moisture, slope, elevation, historical_landslides
    """
    r24 = float(features.get("rainfall_24h", 0))
    r7d = float(features.get("rainfall_7d", 0))
    sm = float(features.get("soil_moisture", 0))
    slope = float(features.get("slope", 0))
    elev = float(features.get("elevation", 0))
    hist = int(features.get("historical_landslides", 0))

    # 1. Agar Member 4 ne ML model diya hai (models/risk_model.pkl)
    if os.path.exists(MODEL_PATH):
        try:
            model = joblib.load(MODEL_PATH)
            feature_array = np.array([[r24, r7d, sm, slope, elev, hist]])
            
            # Prediction handling (classes or continuous score)
            pred = model.predict(feature_array)
            if hasattr(pred, "__iter__"):
                score = int(pred[0])
            else:
                score = int(pred)
            
            score = max(0, min(100, score))
            return {
                "risk_score": score,
                "risk_level": get_risk_category(score),
                "model_used": "Member 4 Trained ML Model"
            }
        except Exception as e:
            print(f">>> [Warning] Model load failed: {e}. Switching to heuristic logic.")

    # 2. Heuristic Soil Degradation & Landslide Risk Formula (NER Geospatial standard)
    # Weights: 35% 24h Rainfall, 20% 7-day cumulative, 20% Slope, 15% Soil moisture, 10% History
    score = (
        (min(r24, 250) / 250) * 35 +
        (min(r7d, 600) / 600) * 20 +
        (min(slope, 55) / 55) * 20 +
        (min(sm, 100) / 100) * 15 +
        (min(hist, 20) / 20) * 10
    )
    final_score = int(min(max(score, 5), 98))

    return {
        "risk_score": final_score,
        "risk_level": get_risk_category(final_score),
        "model_used": "Integrated NER Soil Hazard Algorithm (Fallback)"
    }