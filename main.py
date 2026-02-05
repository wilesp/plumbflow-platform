"""
PlumbFlow Platform - Main Application
FastAPI backend serving frontend and API endpoints
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PlumbFlow API",
    description="Plumber Matching Platform API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class CustomerJob(BaseModel):
    title: str
    jobType: str
    description: str
    urgency: str
    customerName: str
    phone: str
    email: str | None = None
    postcode: str

class PlumberRegistration(BaseModel):
    businessName: str
    fullName: str
    email: str
    phone: str
    postcode: str
    gasSafe: bool = False
    gasSafeNumber: str | None = None
    skills: list[str] = []
    hourlyRate: int = 60

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "PlumbFlow"}

# API endpoints
@app.post("/api/jobs/submit")
async def submit_job(job: CustomerJob):
    """
    Submit a new customer job
    """
    try:
        logger.info(f"New job submitted: {job.title} in {job.postcode}")
        
        # In production: Save to database, trigger matching
        # For now: Return success
        
        return {
            "status": "success",
            "message": "Job submitted successfully",
            "job_id": "test_123",
            "estimated_response_time": "15 minutes"
        }
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/plumbers/register")
async def register_plumber(plumber: PlumberRegistration):
    """
    Register a new plumber
    """
    try:
        logger.info(f"New plumber registration: {plumber.businessName}")
        
        # In production: Save to database, create Stripe customer
        # For now: Return success
        
        return {
            "status": "success",
            "message": "Registration successful",
            "plumber_id": "test_456"
        }
    except Exception as e:
        logger.error(f"Error registering plumber: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """
    Get platform statistics
    """
    return {
        "total_plumbers": 247,
        "total_jobs": 189,
        "jobs_today": 34,
        "match_rate": 94
    }

@app.get("/api/jobs")
async def get_jobs():
    """
    Get all jobs (for admin panel)
    """
    # In production: Query database
    # For now: Return sample data
    return {
        "jobs": [
            {
                "id": 1,
                "title": "Leaking tap in kitchen",
                "postcode": "SW19",
                "status": "matched",
                "created": "2024-02-04T10:30:00"
            }
        ]
    }

# Mount static files (frontend)
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    
    @app.get("/")
    async def serve_frontend():
        return FileResponse(frontend_dir / "index.html")
    
    @app.get("/{path:path}")
    async def serve_frontend_paths(path: str):
        file_path = frontend_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # If file doesn't exist, serve index.html (SPA)
        return FileResponse(frontend_dir / "index.html")
else:
    @app.get("/")
    async def root():
        return {
            "message": "PlumbFlow API is running",
            "status": "frontend files not found",
            "note": "Upload frontend folder to enable web interface"
        }

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
