from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from services.data_service import get_db_connection
from services.live_weather_service import get_live_environmental_telemetry

router = APIRouter()

class ReportInput(BaseModel):
    latitude: float = Field(..., example=27.3389)
    longitude: float = Field(..., example=88.6065)
    report_type: str = Field(..., example="Road Blockage / Landslide")
    description: str = Field(..., example="Rockfall and active debris flow observed on highway.")
    photo: Optional[str] = Field(None, description="Base64 encoded JPEG or image URL")


# ---------------- 1. SUBMIT FIELD INCIDENT REPORT ----------------
@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(report: ReportInput):
    """
    Submits a geotagged citizen/officer field report to SQLite DB.
    Automatically enriches the submission with live satellite radar telemetry.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reports (latitude, longitude, report_type, description, photo)
            VALUES (?, ?, ?, ?, ?)
        ''', (report.latitude, report.longitude, report.report_type, report.description, report.photo))
        conn.commit()
        report_id = cursor.lastrowid

        # Real-time satellite telemetry check for the reported coordinates
        telemetry = get_live_environmental_telemetry(report.latitude, report.longitude)

        print(f">>> [REPORT LOGGED] ID: {report_id} | Type: {report.report_type} | Lat: {report.latitude}, Lon: {report.longitude}")

        return {
            "message": "Field incident report registered successfully!",
            "report_id": report_id,
            "status": "Logged in SQLite Database for DDMA Inspection",
            "satellite_context": {
                "rainfall_24h_mm": telemetry.get("rainfall_24h", 0.0),
                "soil_moisture_percent": telemetry.get("soil_moisture", 50.0),
                "weather_condition": telemetry.get("weather_condition", "Partly Cloudy")
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }

    except Exception as e:
        conn.rollback()
        print(f">>> [Report Error] Database write failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write report to database: {str(e)}")
    finally:
        conn.close()


# ---------------- 2. FETCH ALL HISTORICAL & LIVE FIELD REPORTS ----------------
@router.get("/reports")
def get_reports():
    """
    Returns all field reports ordered by most recent first for GIS Map pins & Field Ops table.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f">>> [Reports Query Error] {e}")
        return []
    finally:
        conn.close()