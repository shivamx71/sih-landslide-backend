import os
import joblib
import numpy as np
import warnings
from typing import Dict, Any, List, Optional

# Scikit-learn parallel warnings ko mute karo taaki Render CPU freeze na ho
warnings.filterwarnings('ignore', category=UserWarning)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "risk_model.pkl")

# In-Memory Global Model Cache
_CACHED_MODEL = None
_MODEL_ATTEMPTED = False

def load_ml_model():
    """Loads ML model and enforces single-thread execution (n_jobs=1) for ultra-fast instant inference."""
    global _CACHED_MODEL, _MODEL_ATTEMPTED
    if not _MODEL_ATTEMPTED:
        _MODEL_ATTEMPTED = True
        if os.path.exists(MODEL_PATH):
            try:
                model = joblib.load(MODEL_PATH)
                # CRITICAL: Free Render instance par joblib multiprocessing lock na ho isliye n_jobs=1
                if hasattr(model, 'n_jobs'):
                    model.n_jobs = 1
                _CACHED_MODEL = model
                print(">>> [ML Engine] risk_model.pkl loaded successfully with n_jobs=1!")
            except Exception as e:
                print(f">>> [ML Engine Warning] Fallback triggered: {e}")
    return _CACHED_MODEL

def get_risk_category(score: int) -> Dict[str, str]:
    if score >= 75:
        return {"level": "CRITICAL", "color": "#dc2626", "badge_class": "badge-danger"}
    elif score >= 55:
        return {"level": "HIGH", "color": "#ea580c", "badge_class": "badge-warning"}
    elif score >= 35:
        return {"level": "MODERATE", "color": "#ca8a04", "badge_class": "badge-info"}
    else:
        return {"level": "LOW", "color": "#16a34a", "badge_class": "badge-success"}

def _determine_primary_driver(r24: float, sm: float, slope: float, hist: int) -> str:
    if r24 >= 60.0 and sm >= 75.0:
        return "Heavy Precipitation + High Soil Saturation"
    elif r24 >= 50.0:
        return "Severe 24h Rainfall Intensity"
    elif sm >= 80.0:
        return "Critical Subsurface Soil Saturation"
    elif slope >= 35.0:
        return "Steep Topographical Slope Vulnerability"
    elif hist >= 10:
        return "High Historical Landslide Frequency Zone"
    else:
        return "Stable Terrain & Weather Equilibrium"

def predict_soil_risk(features: Dict[str, Any], seismic_active: bool = False) -> Dict[str, Any]:
    r24 = float(features.get("rainfall_24h", 0.0))
    r7d = float(features.get("rainfall_7d", 0.0))
    sm = float(features.get("soil_moisture", 0.0))
    slope = float(features.get("slope", 0.0))
    elev = float(features.get("elevation", 0.0))
    hist = int(features.get("historical_landslides", 0))

    model = load_ml_model()
    final_score = None
    model_name = "Integrated NER Soil Hazard Algorithm"

    # 1. Real-time ML Inference
    if model is not None:
        try:
            feature_array = np.array([[r24, r7d, sm, slope, elev, hist]])
            pred = model.predict(feature_array)
            raw = float(pred[0]) if hasattr(pred, "__iter__") else float(pred)
            
            if raw <= 3.0:
                score_map = {0: 20, 1: 45, 2: 68, 3: 88}
                final_score = score_map.get(int(raw), 25)
            else:
                final_score = int(raw)

            model_name = "Trained Random Forest Regressor (risk_model.pkl)"
        except Exception:
            final_score = None

    # 2. Geological Fallback Formula
    if final_score is None:
        score_val = (
            (min(r24, 200.0) / 200.0) * 35.0 +
            (min(r7d, 500.0) / 500.0) * 20.0 +
            (min(slope, 55.0) / 55.0) * 20.0 +
            (min(sm, 100.0) / 100.0) * 15.0 +
            (min(hist, 20.0) / 20.0) * 10.0
        )
        final_score = int(min(max(score_val, 5), 98))

    if seismic_active:
        final_score = min(100, int(final_score * 1.25))

    final_score = max(2, min(99, final_score))
    category_info = get_risk_category(final_score)

    return {
        "risk_score": final_score,
        "risk_level": category_info["level"],
        "color": category_info["color"],
        "badge_class": category_info["badge_class"],
        "primary_factor": _determine_primary_driver(r24, sm, slope, hist),
        "model_used": model_name,
        "seismic_trigger_applied": seismic_active
    }

def batch_predict_risk(locations_list: List[Dict[str, Any]], seismic_active: bool = False) -> List[Dict[str, Any]]:
    enriched = []
    for loc in locations_list:
        pred = predict_soil_risk(loc, seismic_active=seismic_active)
        loc_copy = dict(loc)
        loc_copy.update(pred)
        enriched.append(loc_copy)
    return enriched