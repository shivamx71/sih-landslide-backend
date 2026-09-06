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