from services.live_weather_service import get_live_environmental_telemetry
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import json
import os
from services.data_service import get_db_connection, fetch_imd_rainfall
from services.prediction import predict_soil_risk

router = APIRouter()

# Base Directory path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON_PATH = os.path.join(BASE_DIR, "data", "ner_districts.geojson")

class PredictionInput(BaseModel):
    rainfall_24h: float = Field(..., example=182.5)
    rainfall_7d: float = Field(..., example=486.0)
    soil_moisture: float = Field(..., example=78.2)
    slope: float = Field(..., example=36.5)
    elevation: float = Field(..., example=1850.0)
    historical_landslides: int = Field(..., example=12)

def model_to_dict(model_instance: BaseModel) -> dict:
    if hasattr(model_instance, "model_dump"):
        return model_instance.model_dump()
    return model_instance.dict()

# 1. Map Coordinates Feed
@router.get("/locations")
def get_locations():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, latitude, longitude FROM locations ORDER BY id ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

# 2. District Terrain & Environmental Intelligence
@router.get("/risk/{location_id}")
def get_risk_by_location(location_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")

        loc_data = dict(row)
        prediction = predict_soil_risk(loc_data)
        weather_info = fetch_imd_rainfall(loc_data["name"])

        return {
            "location": loc_data["name"],
            "latitude": loc_data["latitude"],
            "longitude": loc_data["longitude"],
            "rainfall_24h": loc_data["rainfall_24h"],
            "rainfall_7d": loc_data["rainfall_7d"],
            "soil_moisture": loc_data["soil_moisture"],
            "slope": loc_data["slope"],
            "elevation": loc_data["elevation"],
            "historical_landslides": loc_data["historical_landslides"],
            "risk_score": prediction["risk_score"],
            "risk_level": prediction["risk_level"],
            "imd_weather_summary": weather_info
        }
    finally:
        conn.close()

# 3. Real-Time AI Prediction Engine
@router.post("/predict")
def predict(data: PredictionInput):
    payload = model_to_dict(data)
    result = predict_soil_risk(payload)
    return {
        "risk_score": result["risk_score"],
        "risk_level": result["risk_level"]
    }

# 4. [NAYA GIS ENDPOINT] Official North-East District Boundary Polygons
@router.get("/geojson")
def get_ner_geojson():
    """OGC Standard GeoJSON for Leaflet Choropleth Map Layer"""
    if os.path.exists(GEOJSON_PATH):
        with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Response(content=json.dumps(data), media_type="application/geo+json")
    return Response(content=json.dumps({"type": "FeatureCollection", "features": []}), media_type="application/geo+json")
    # ---------------- 5. 100% REAL LIVE RISK API (DYNAMIC SATELLITE TELEMETRY) ----------------
@router.get("/live-risk/{location_id}")
def get_live_risk_for_district(location_id: int):
    """
    100% Real Live API: Fetches current live rainfall and soil moisture 
    from live satellites for this district, runs ML model, and outputs real risk!
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="District not found")
        loc = dict(row)
    finally:
        conn.close()

    # 1. Call Real-time Satellite Weather API for this district's GPS
    live_weather = get_live_environmental_telemetry(loc["latitude"], loc["longitude"])

    # 2. Feed Live Satellite parameters directly to ML Model
    ml_payload = {
        "rainfall_24h": live_weather["rainfall_24h"],
        "rainfall_7d": live_weather["rainfall_7d"],
        "soil_moisture": live_weather["soil_moisture"],
        "slope": loc["slope"],
        "elevation": loc["elevation"],
        "historical_landslides": loc["historical_landslides"]
    }
    prediction = predict_soil_risk(ml_payload)

    return {
        "district": loc["name"],
        "status": "LIVE_SATELLITE_FEED",
        "fetch_timestamp": live_weather["timestamp"],
        "live_telemetry": {
            "rainfall_24h_mm": live_weather["rainfall_24h"],
            "rainfall_7d_cumulative_mm": live_weather["rainfall_7d"],
            "soil_moisture_percent": live_weather["soil_moisture"],
            "temperature_c": live_weather["temperature"],
            "data_source": live_weather["source"]
        },
        "geotechnical_baseline": {
            "slope_degrees": loc["slope"],
            "elevation_meters": loc["elevation"],
            "isro_past_incidents": loc["historical_landslides"]
        },
        "realtime_ai_risk_assessment": {
            "risk_score": prediction["risk_score"],
            "risk_level": prediction["risk_level"],
            "advisory": "Critical monitoring required due to heavy active saturation" if prediction["risk_score"] >= 75 else "Current weather conditions within manageable stability limits"
        }
    }

# Dynamic Live Risk for ANY GPS Coordinate in India (Citizen / Field Officer GPS)
@router.get("/live-risk-by-coords")
def get_live_risk_by_coords(lat: float, lon: float, slope: float = 28.0, elevation: float = 1200.0):
    """
    Calculates live landslide risk for ANY arbitrary GPS coordinate in real-time!
    """
    live_weather = get_live_environmental_telemetry(lat, lon)
    
    ml_payload = {
        "rainfall_24h": live_weather["rainfall_24h"],
        "rainfall_7d": live_weather["rainfall_7d"],
        "soil_moisture": live_weather["soil_moisture"],
        "slope": slope,
        "elevation": elevation,
        "historical_landslides": 6
    }
    prediction = predict_soil_risk(ml_payload)

    return {
        "coordinates": {"latitude": lat, "longitude": lon},
        "timestamp": live_weather["timestamp"],
        "live_telemetry": live_weather,
        "predicted_risk": prediction
    }