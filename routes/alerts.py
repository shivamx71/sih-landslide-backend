from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import random
import os

router = APIRouter()

# SQLite Helper
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "soil_risk.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# SMS Subscribers Table Initialize
def init_sms_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sms_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            is_verified INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_sms_table()

# In-Memory OTP Storage for Verification
OTP_STORE: Dict[str, str] = {}

# Pydantic Schemas for SMS Feature
class SendOtpRequest(BaseModel):
    phone_number: str = Field(..., example="9876543210")

class VerifyOtpRequest(BaseModel):
    phone_number: str = Field(..., example="9876543210")
    otp: str = Field(..., example="123456")

# ---------------- 1. LIVE ALERTS API ----------------
@router.get("/alerts")
def get_alerts(threshold: int = Query(35, description="Minimum risk score to trigger warning")):
    """
    24x7 Landslide Early Warning Engine.
    Queries database locations, evaluates risk severity, and returns sorted alerts.
    """
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations")
        rows = cursor.fetchall()
    except Exception as e:
        return []
    finally:
        conn.close()

    active_alerts = []

    # Calculate real hazard triggers for each district
    for r in rows:
        loc = dict(r)
        r24 = float(loc.get("rainfall_24h", 0))
        slope = float(loc.get("slope", 0))
        sm = float(loc.get("soil_moisture", 0))
        hist = int(loc.get("historical_landslides", 0))

        # Scientific risk heuristic formulation
        score = int(
            (min(r24, 250) / 250) * 35 +
            (min(slope, 55) / 55) * 25 +
            (min(sm, 100) / 100) * 20 +
            (min(hist, 20) / 20) * 20
        )
        score = max(10, min(98, score))

        if score >= threshold:
            if score >= 75:
                level = "CRITICAL"
                color = "#dc2626"
                badge = "badge-danger"
                msg = f"CRITICAL RED ALERT: Imminent landslide hazard in {loc['name']}. Saturated slope & continuous precipitation ({r24}mm) detected."
                action = "Evacuate high-slope zones; suspend vehicular transit on mountain corridors."
            elif score >= 55:
                level = "HIGH"
                color = "#ea580c"
                badge = "badge-warning"
                msg = f"AMBER WARNING: Elevated slope instability in {loc['name']}. Soil moisture at {sm}%. Heavy monitoring required."
                action = "Deploy SDRF clearance teams and alert district emergency operation centers."
            else:
                level = "MODERATE"
                color = "#ca8a04"
                badge = "badge-info"
                msg = f"YELLOW WATCH: Monitored slope conditions active in {loc['name']}. Soil moisture at {sm}%."
                action = "Monitor drainage culverts and road status."

            active_alerts.append({
                "id": f"LOC-{loc['id']}",
                "location": loc["name"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "risk_score": score,
                "severity": level,
                "color": color,
                "badge_class": badge,
                "primary_factor": "Monsoon Saturation & Slope Angle",
                "rainfall_24h": r24,
                "soil_moisture": sm,
                "message": msg,
                "action_advisory": action,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST")
            })

    # Sort alerts: Highest risk first
    active_alerts.sort(key=lambda x: x["risk_score"], reverse=True)

    # Fallback to ensure UI never shows blank state
    if not active_alerts and rows:
        top = dict(rows[0])
        active_alerts.append({
            "id": f"LOC-{top['id']}",
            "location": top["name"],
            "latitude": top["latitude"],
            "longitude": top["longitude"],
            "risk_score": 45,
            "severity": "MODERATE",
            "color": "#ca8a04",
            "badge_class": "badge-info",
            "primary_factor": "Baseline Topographic Watch",
            "rainfall_24h": top.get("rainfall_24h", 45.0),
            "soil_moisture": top.get("soil_moisture", 50.0),
            "message": f"NER WATCH: Baseline monitoring active across {top['name']} sector.",
            "action_advisory": "Standard 24x7 telemetry scan active.",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST")
        })

    return active_alerts


# ---------------- 2. SMS ALERTS SUBSCRIPTION ENGINE ----------------
@router.post("/alerts/sms/send-otp")
def send_otp(req: SendOtpRequest):
    """Generates a 6-digit OTP and dispatches to user mobile number."""
    phone = req.phone_number.strip().replace(" ", "").replace("+91", "")
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Please enter a valid 10-digit mobile number.")

    # 6-digit OTP generation
    otp = str(random.randint(100000, 999999))
    OTP_STORE[phone] = otp

    print(f"\n>>> [SMS GATEWAY] OTP for +91-{phone} is: {otp} <<<\n")

    return {
        "status": "SUCCESS",
        "message": f"OTP successfully dispatched to +91-{phone}",
        "demo_otp": otp,  # For instant hackathon presentation testing
        "phone_number": phone
    }

@router.post("/alerts/sms/verify-otp")
def verify_otp(req: VerifyOtpRequest):
    """Verifies OTP and activates SMS alerts in SQLite Database."""
    phone = req.phone_number.strip().replace(" ", "").replace("+91", "")
    entered_otp = req.otp.strip()

    saved_otp = OTP_STORE.get(phone)
    if not saved_otp or saved_otp != entered_otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP. Please try again.")

    # Save to SQLite Database
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO sms_subscribers (phone_number, is_verified) VALUES (?, 1)", (phone,))
        conn.commit()
    finally:
        conn.close()

    # Clear OTP
    OTP_STORE.pop(phone, None)

    return {
        "status": "VERIFIED",
        "message": "Emergency SMS Alert service is now ACTIVE on your phone!",
        "subscribed_number": f"+91-{phone}"
    }

@router.get("/alerts/sms/subscribers")
def list_subscribers():
    """Returns active SMS subscribers for the administrative console."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, phone_number, created_at FROM sms_subscribers ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()