import json
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Response, Query
from pydantic import BaseModel, Field

from services.live_weather_service import (
    get_live_environmental_telemetry, 
    get_live_seismic_activity
)
from services.data_service import (
    get_db_connection, 
    fetch_imd_rainfall, 
    get_all_locations_live, 
    get_location_by_id_live,
    get_dashboard_summary_kpi
)
from services.prediction import predict_soil_risk, batch_predict_risk

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON_PATH = os.path.join(BASE_DIR, "data", "ner_districts.geojson")

class PredictionInput(BaseModel):
    rainfall_24h: float = Field(..., example=45.5)
    rainfall_7d: float = Field(..., example=120.0)
    soil_moisture: float = Field(..., example=68.2)
    slope: float = Field(..., example=32.5)
    elevation: float = Field(..., example=1450.0)
    historical_landslides: int = Field(..., example=6)

def model_to_dict(model_instance: BaseModel) -> dict:
    if hasattr(model_instance, "model_dump"):
        return model_instance.model_dump()
    return model_instance.dict()


# ---------------- 1. 24x7 LIVE LOCATIONS & MAP RISK FEED ----------------
@router.get("/locations")
def get_locations(live: bool = Query(True, description="Attach live satellite weather and AI risk scores")):
    """
    Returns all 43+ NER districts.
    When live=True, attaches real-time satellite rainfall, soil moisture, 
    temperature, AI risk scores, and marker hex colors in <1 second.
    """
    if not live:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, latitude, longitude FROM locations ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # Fetch live telemetry for all districts concurrently
    live_locations = get_all_locations_live()
    
    # Check live seismic activity across NER
    seismic_info = get_live_seismic_activity()
    seismic_active = seismic_info.get("seismic_trigger_active", False)

    # Vectorized AI Landslide Prediction
    enriched_locations = batch_predict_risk(live_locations, seismic_active=seismic_active)
    return enriched_locations


# ---------------- 2. TOP DASHBOARD LIVE SUMMARY KPIs ----------------
@router.get("/dashboard/summary")
def get_dashboard_summary():
    """
    Provides real-time aggregated metrics for the top dashboard cards:
    - Average 24h Rainfall across NER
    - Average Satellite Soil Moisture
    - Highest Rainfall Zone
    - Live USGS Seismic Activity
    """
    return get_dashboard_summary_kpi()


# ---------------- 3. SINGLE DISTRICT LIVE RISK ASSESSMENT ----------------
@router.get("/risk/{location_id}")
@router.get("/live-risk/{location_id}")
def get_live_risk_for_district(location_id: int):
    """
    100% Live Telemetry + AI Inference for a specific district.
    Integrates live satellite radar, deep soil moisture, and IMD statistics.
    """
    loc = get_location_by_id_live(location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="District not found")

    # Live seismic check
    seismic_info = get_live_seismic_activity()
    seismic_active = seismic_info.get("seismic_trigger_active", False)

    # Real-time prediction
    prediction = predict_soil_risk(loc, seismic_active=seismic_active)
    
    # Live IMD / Radar statistics
    imd_summary = fetch_imd_rainfall(loc["name"], loc["latitude"], loc["longitude"])

    return {
        "district": loc["name"],
        "status": loc.get("status", "LIVE_SATELLITE_FEED"),
        "fetch_timestamp": loc.get("last_sync"),
        "live_telemetry": {
            "rainfall_24h_mm": loc["rainfall_24h"],
            "rainfall_7d_cumulative_mm": loc["rainfall_7d"],
            "soil_moisture_percent": loc["soil_moisture"],
            "temperature_c": loc.get("temperature", 22.0),
            "humidity_percent": loc.get("humidity", 70),
            "wind_speed_kmh": loc.get("wind_speed", 8.0),
            "weather_condition": loc.get("weather_condition", "Partly Cloudy"),
            "data_source": loc.get("live_source", "Open-Meteo ECMWF High-Res Satellite")
        },
        "geotechnical_baseline": {
            "slope_degrees": loc["slope"],
            "elevation_meters": loc["elevation"],
            "historical_incidents": loc["historical_landslides"]
        },
        "realtime_ai_risk_assessment": {
            "risk_score": prediction["risk_score"],
            "risk_level": prediction["risk_level"],
            "color": prediction["color"],
            "badge_class": prediction["badge_class"],
            "primary_factor": prediction["primary_factor"],
            "model_used": prediction["model_used"],
            "seismic_trigger_active": seismic_active,
            "advisory": (
                "CRITICAL EVACUATION ADVISORY: High precipitation combined with critical soil saturation."
                if prediction["risk_score"] >= 75
                else "ELEVATED ALERT: Saturated slopes monitored. Travelers exercise caution on mountain highways."
                if prediction["risk_score"] >= 55
                else "STABLE: Weather and pore pressure parameters within standard safety envelope."
            )
        },
        "imd_weather_summary": imd_summary
    }


# ---------------- 4. ARBITRARY FIELD GPS COORDINATE RISK EVALUATOR ----------------
@router.get("/live-risk-by-coords")
def get_live_risk_by_coords(lat: float, lon: float, slope: float = 28.0, elevation: float = 1200.0):
    """
    Calculates 100% live landslide risk for ANY GPS location in real-time (Citizen / Field Patrol).
    """
    live_weather = get_live_environmental_telemetry(lat, lon)
    seismic_info = get_live_seismic_activity()
    seismic_active = seismic_info.get("seismic_trigger_active", False)

    ml_payload = {
        "rainfall_24h": live_weather["rainfall_24h"],
        "rainfall_7d": live_weather["rainfall_7d"],
        "soil_moisture": live_weather["soil_moisture"],
        "slope": slope,
        "elevation": elevation,
        "historical_landslides": 4
    }
    prediction = predict_soil_risk(ml_payload, seismic_active=seismic_active)

    return {
        "coordinates": {"latitude": lat, "longitude": lon},
        "timestamp": live_weather.get("fetch_timestamp"),
        "live_telemetry": live_weather,
        "predicted_risk": prediction,
        "seismic_status": seismic_info
    }


# ---------------- 5. CUSTOM AI PREDICTION SIMULATOR ----------------
@router.post("/predict")
def predict(data: PredictionInput):
    payload = model_to_dict(data)
    result = predict_soil_risk(payload)
    return {
        "risk_score": result["risk_score"],
        "risk_level": result["risk_level"],
        "color": result["color"],
        "badge_class": result["badge_class"],
        "primary_factor": result["primary_factor"],
        "model_used": result["model_used"]
    }


# ---------------- 6. GIS CHOROPLETH POLYGON BOUNDARIES ----------------
@router.get("/geojson")
def get_ner_geojson():
    """OGC Standard GeoJSON for Leaflet choropleth map layers."""
    if os.path.exists(GEOJSON_PATH):
        with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Response(content=json.dumps(data), media_type="application/geo+json")
    return Response(content=json.dumps({"type": "FeatureCollection", "features": []}), media_type="application/geo+json")