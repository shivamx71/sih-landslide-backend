from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.data_service import init_db
from services.prediction import load_ml_model
from routes import risk, reports, alerts

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB & Model softly without blocking threads
    init_db()
    load_ml_model()
    print(">>> [Server] AI-Based Landslide Risk EWS (NER) is LIVE 24x7!")
    yield
    print(">>> [Server] Backend shutting down cleanly.")

app = FastAPI(
    title="AI-Based Early Warning and Landslide Risk Monitoring System in NER",
    description="Real-time Geospatial Risk Assessment, Satellite Tracking & Alert Engine.",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes registration
app.include_router(risk.router, tags=["Risk & Locations"])
app.include_router(reports.router, tags=["Field Reports"])
app.include_router(alerts.router, tags=["Alerts & Warnings"])

@app.get("/")
def home():
    return {
        "project": "AI-Based Early Warning and Landslide Risk Monitoring System in NER",
        "status": "Online & Synchronized",
        "region": "North Eastern Region (NER), India (Zone V)",
        "telemetry_source": "Open-Meteo High-Res Satellite Radar",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    }

@app.get("/health")
def health_check():
    return {
        "system_status": "OPERATIONAL_24x7",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    }