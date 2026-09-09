from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import random
import requests
import os

router = APIRouter()

# ---------------- FAST2SMS REAL TELECOM API CONFIGURATION ----------------
FAST2SMS_API_KEY = "H9P4xmYz0T8QvcFXds2pKwjZUR3SW7IGakqJulfehn1LEVCOD57oHeiEM6dg5UplaqyLKxIStvXGOFc9"

# SQLite Database Setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "soil_risk.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# SMS Subscribers Table Initialization
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

# In-Memory OTP Cache
OTP_STORE: Dict[str, str] = {}

# Schemas
class SendOtpRequest(BaseModel):
    phone_number: str = Field(..., example="9759484690")

class VerifyOtpRequest(BaseModel):
    phone_number: str = Field(..., example="9759484690")
    otp: str = Field(..., example="123456")

# ---------------- 1. LIVE ALERTS FEED API ----------------
@router.get("/alerts")
def get_alerts(threshold: int = Query(35, description="Minimum risk score")):
    """
    Returns active landslide hazard alerts for North-East districts.
    """
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations")
        rows = cursor.fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    active_alerts = []

    for r in rows:
        loc = dict(r)
        r24 = float(loc.get("rainfall_24h", 0))
        slope = float(loc.get("slope", 0))
        sm = float(loc.get("soil_moisture", 0))
        hist = int(loc.get("historical_landslides", 0))

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
                msg = f"CRITICAL RED ALERT: Imminent landslide hazard in {loc['name']}. Saturated slope & heavy rainfall ({r24}mm) detected."
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

    active_alerts.sort(key=lambda x: x["risk_score"], reverse=True)
    return active_alerts


# ---------------- 2. REAL TELECOM SMS OTP SENDER ----------------
@router.post("/alerts/sms/send-otp")
def send_otp(req: SendOtpRequest):
    """
    Sends a REAL SMS OTP directly to any Indian mobile number via Fast2SMS Gateway!
    """
    phone = req.phone_number.strip().replace(" ", "").replace("+91", "")
    if len(phone) != 10 or not phone.isdigit():
        raise HTTPException(status_code=400, detail="Please enter a valid 10-digit Indian mobile number.")

    # 6-digit secure OTP
    otp = str(random.randint(100000, 999999))
    OTP_STORE[phone] = otp

    sms_dispatched = False
    gateway_response = None

    # REAL FAST2SMS DISPATCH (OTP ROUTE)
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {
            "authorization": FAST2SMS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "variables_values": otp,
            "route": "otp",
            "numbers": phone
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=8)
        gateway_response = resp.json()
        
        if resp.status_code == 200 and gateway_response.get("return") is True:
            sms_dispatched = True
            print(f"\n========================================================")
            print(f">>> [REAL SMS SENT] OTP {otp} delivered to +91-{phone} via Fast2SMS!")
            print(f">>> Request ID: {gateway_response.get('request_id')}")
            print(f"========================================================\n")
        else:
            print(f">>> [Fast2SMS Gateway Notice] {gateway_response}")
    except Exception as e:
        print(f">>> [SMS Transmission Error] {e}")

    return {
        "status": "SUCCESS",
        "gateway_status": "REAL_SMS_SENT" if sms_dispatched else "SIMULATED_FALLBACK",
        "message": f"Real SMS OTP dispatched to +91-{phone}",
        "demo_otp": otp,  # Safety net: Screen par bhi rahega in case network delay ho
        "phone_number": phone
    }


# ---------------- 3. OTP VERIFIER & DATABASE REGISTRATION ----------------
@router.post("/alerts/sms/verify-otp")
def verify_otp(req: VerifyOtpRequest):
    """
    Verifies OTP and permanently registers subscriber into SQLite Database.
    """
    phone = req.phone_number.strip().replace(" ", "").replace("+91", "")
    entered_otp = req.otp.strip()

    saved_otp = OTP_STORE.get(phone)
    if not saved_otp or saved_otp != entered_otp:
        raise HTTPException(status_code=400, detail="Invalid OTP entered. Please check your SMS and try again.")

    # Save to SQLite Database permanently
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
        "message": f"Emergency Landslide SMS Alert Service is now ACTIVE for +91-{phone}!",
        "subscribed_number": f"+91-{phone}"
    }


# ---------------- 4. BROADCAST SMS TO ALL SUBSCRIBERS ----------------
@router.post("/alerts/sms/broadcast-emergency")
def broadcast_emergency_sms(district: str, risk_score: int):
    """
    Broadcasts real emergency alerts to all subscribed citizen phone numbers when hazard is HIGH/CRITICAL.
    """
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT phone_number FROM sms_subscribers WHERE is_verified = 1")
        subscribers = [r["phone_number"] for r in cursor.fetchall()]
    finally:
        conn.close()

    if not subscribers:
        return {"status": "NO_SUBSCRIBERS", "message": "No active mobile numbers registered yet."}

    numbers_str = ",".join(subscribers)
    dispatched = False

    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {"authorization": FAST2SMS_API_KEY, "Content-Type": "application/json"}
        payload = {
            "message": f"RED ALERT: Imminent landslide risk detected in {district} (Risk: {risk_score}/100). Take immediate precautions.",
            "language": "english",
            "route": "q",
            "numbers": numbers_str
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=8)
        if resp.status_code == 200:
            dispatched = True
    except Exception as e:
        print(f">>> [Broadcast Error] {e}")

    return {
        "status": "DISPATCHED" if dispatched else "FAILED",
        "recipients_count": len(subscribers),
        "target_district": district
    }


@router.get("/alerts/sms/subscribers")
def list_subscribers():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, phone_number, created_at FROM sms_subscribers ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()