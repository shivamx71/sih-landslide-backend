from fastapi import APIRouter, Query
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.data_service import (
    get_all_locations_live, 
    get_recent_alerts, 
    add_alert,
    get_db_connection
)
from services.live_weather_service import get_live_seismic_activity
from services.prediction import batch_predict_risk

router = APIRouter()

@router.get("/alerts")
def get_alerts(threshold: int = Query(45, description="Minimum risk score to trigger warning")):
    """
    24x7 Real-time Landslide Early Warning Feed (NER-EWS).
    Monitors live satellite rainfall, soil saturation, and USGS tectonic tremors.
    Returns a sorted list of active alerts with highest risk first.
    """
    # 1. Fetch live telemetry for all 43 districts concurrently
    live_locations = get_all_locations_live()
    
    # 2. Check live seismic tremors in NER (Zone V)
    seismic_info = get_live_seismic_activity()
    seismic_active = seismic_info.get("seismic_trigger_active", False)

    # 3. Vectorized AI risk calculation
    predictions = batch_predict_risk(live_locations, seismic_active=seismic_active)

    active_alerts: List[Dict[str, Any]] = []

    # 4. Check for active earthquakes in NER to generate seismic emergency alert
    if seismic_info.get("active_seismic_count", 0) > 0:
        for eq in seismic_info.get("events", [])[:1]:
            active_alerts.append({
                "id": "SEIS-01",
                "location": eq.get("place", "NER Tectonic Fault Zone"),
                "latitude": 25.5,
                "longitude": 92.5,
                "risk_score": 85,
                "severity": "CRITICAL SEISMIC TRIGGER",
                "color": "#dc2626",
                "badge_class": "badge-danger",
                "primary_factor": f"M{eq.get('magnitude')} Tectonic Tremor Detected",
                "rainfall_24h": 0.0,
                "soil_moisture": 60.0,
                "message": f"EARTHQUAKE ALERT: Magnitude {eq.get('magnitude')} tremor recorded. Slopes with high soil moisture are at immediate risk of co-seismic landslides.",
                "action_advisory": "Trigger immediate geotechnical inspection on NH-29 & mountain corridors.",
                "timestamp": eq.get("time", datetime.now().strftime("%Y-%m-%d %H:%M"))
            })

    # 5. Process real-time satellite telemetry risk triggers
    for loc in predictions:
        score = loc.get("risk_score", 0)
        level = loc.get("risk_level", "LOW")
        r24 = loc.get("rainfall_24h", 0.0)
        sm = loc.get("soil_moisture", 0.0)
        driver = loc.get("primary_factor", "Weather Equilibrium")

        if score >= threshold:
            if score >= 75:
                msg = (
                    f"CRITICAL RED ALERT: Extreme landslide hazard in {loc['name']} driven by {driver}. "
                    f"Live 24h Rain: {r24}mm, Soil Saturation: {sm}%. Immediate DDMA dispatch advised."
                )
                action = "Evacuate high-slope habitations; halt heavy vehicular traffic on cut slopes."
            elif score >= 55:
                msg = (
                    f"AMBER WARNING: High slope vulnerability in {loc['name']}. "
                    f"Persistent rainfall ({r24}mm/24h) is approaching critical pore-pressure threshold ({sm}%)."
                )
                action = "Deploy SDRF road-clearing units and alert district emergency operation centers."
            else:
                msg = (
                    f"YELLOW WATCH: Elevated saturation in {loc['name']}. "
                    f"Soil moisture at {sm}%. Keep continuous radar monitoring active."
                )
                action = "Monitor drainage culverts and watch for preliminary soil seepage."

            active_alerts.append({
                "id": f"LOC-{loc['id']}",
                "location": loc["name"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "risk_score": score,
                "severity": level,
                "color": loc.get("color", "#ea580c"),
                "badge_class": loc.get("badge_class", "badge-warning"),
                "primary_factor": driver,
                "rainfall_24h": r24,
                "soil_moisture": sm,
                "message": msg,
                "action_advisory": action,
                "timestamp": loc.get("last_sync", datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"))
            })

    # Sort alerts: Highest risk score at the top
    active_alerts.sort(key=lambda x: x["risk_score"], reverse=True)

    # If weather across NER is completely calm and no district crosses threshold,
    # show the top vulnerable monitored zone as an active watch so UI is never blank
    if not active_alerts and predictions:
        top_zone = max(predictions, key=lambda x: x["risk_score"])
        active_alerts.append({
            "id": f"LOC-{top_zone['id']}",
            "location": top_zone["name"],
            "latitude": top_zone["latitude"],
            "longitude": top_zone["longitude"],
            "risk_score": top_zone["risk_score"],
            "severity": "ALL-CLEAR / MONITORING",
            "color": "#16a34a",
            "badge_class": "badge-success",
            "primary_factor": "Atmospheric Conditions Stable",
            "rainfall_24h": top_zone.get("rainfall_24h", 0.0),
            "soil_moisture": top_zone.get("soil_moisture", 35.0),
            "message": f"NER REGION STABLE: All monitored sectors operating within safety envelope. Highest watch zone is {top_zone['name']}.",
            "action_advisory": "Standard 24x7 automated telemetry active.",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        })

    return active_alerts


@router.get("/alerts/summary")
def get_alerts_summary():
    """Returns quick counts for alert badges on the navbar."""
    alerts = get_alerts(threshold=35)
    critical_count = sum(1 for a in alerts if "CRITICAL" in a["severity"])
    high_count = sum(1 for a in alerts if a["severity"] == "HIGH")
    
    return {
        "total_active_alerts": len(alerts),
        "critical_count": critical_count,
        "high_count": high_count,
        "system_status": "RED" if critical_count > 0 else "AMBER" if high_count > 0 else "GREEN",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    }