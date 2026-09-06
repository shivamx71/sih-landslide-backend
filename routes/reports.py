from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from services.data_service import get_db_connection

router = APIRouter()

class ReportInput(BaseModel):
    latitude: float = Field(..., example=27.3389)
    longitude: float = Field(..., example=88.6065)
    report_type: str = Field(..., example="Road Blockage / Landslide")
    description: str = Field(..., example="Rockfall and soil slippage observed near state highway.")
    photo: Optional[str] = Field(None, example="https://example.com/photo.jpg")

# API 4: Citizen / Field Officer Report Submission
@router.post("/reports")
def create_report(report: ReportInput):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reports (latitude, longitude, report_type, description, photo)
            VALUES (?, ?, ?, ?, ?)
        ''', (report.latitude, report.longitude, report.report_type, report.description, report.photo))
        conn.commit()
        report_id = cursor.lastrowid

        return {
            "message": "Field report submitted successfully!",
            "report_id": report_id,
            "status": "Logged for Field Officer Review"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit report: {str(e)}")
    finally:
        conn.close()

# API 5: Get All Submitted Reports (Dashboard Map pins ke liye)
@router.get("/reports")
def get_reports():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()