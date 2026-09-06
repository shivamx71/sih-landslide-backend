from fastapi import APIRouter
from services.data_service import get_db_connection
from services.prediction import predict_soil_risk

router = APIRouter()

# API 6: Active Warning/Alert Endpoint
@router.get("/alerts")
def get_alerts():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations")
        locations = cursor.fetchall()

        active_alerts = []
        for loc in locations:
            loc_data = dict(loc)
            prediction = predict_soil_risk(loc_data)

            # High/Critical Risk Trigger
            if prediction["risk_score"] >= 75:
                active_alerts.append({
                    "location": loc_data["name"],
                    "latitude": loc_data["latitude"],
                    "longitude": loc_data["longitude"],
                    "risk_score": prediction["risk_score"],
                    "severity": prediction["risk_level"],
                    "message": f"CRITICAL: Severe landslide & soil erosion risk in {loc_data['name']}. Immediate alert sent to District Disaster Management Authority (DDMA)."
                })

        return active_alerts
    finally:
        conn.close()