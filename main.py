from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.data_service import init_db
from routes import risk, reports, alerts

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(">>> [Server] AI-Based Early Warning & Landslide Risk Monitoring System (NER) is LIVE!")
    yield
    print(">>> [Server] Backend shutting down cleanly.")

# Exact official title aur description
app = FastAPI(
    title="AI-Based Early Warning and Landslide Risk Monitoring System in NER",
    description="Smart India Hackathon (SIH) - Real-time Geospatial Risk Assessment, IMD Weather Tracking & Community Alert Engine for North Eastern Region.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware for Frontend Connection
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
        "status": "Online",
        "documentation": "/docs",
        "target_region": "North East Region (NER), India",
        "developer_role": "Backend Engineer (FastAPI + SQLite)"
    }