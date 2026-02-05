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

# Debug endpoint to see directory structure
@app.get("/debug/files")
async def debug_files():
    """Debug endpoint to see what files are available"""
    current_dir = Path(__file__).parent
    frontend_dir = current_dir / "frontend"
    
    return {
        "current_dir": str(current_dir),
        "current_dir_exists": current_dir.exists(),
        "current_dir_contents": [str(p) for p in current_dir.iterdir()] if current_dir.exists() else [],
        "frontend_dir": str(frontend_dir),
        "frontend_dir_exists": frontend_dir.exists(),
        "frontend_contents": [str(p) for p in frontend_dir.iterdir()] if frontend_dir.exists() else [],
        "cwd": os.getcwd(),
        "env_port": os.getenv("PORT", "not set")
    }

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
logger.info(f"Looking for frontend at: {frontend_dir}")
logger.info(f"Frontend exists: {frontend_dir.exists()}")

if frontend_dir.exists():
    logger.info(f"Frontend files: {list(frontend_dir.iterdir())}")
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    
    @app.get("/")
    async def serve_frontend():
        index_path = frontend_dir / "index.html"
        logger.info(f"Serving index.html from: {index_path}")
        if not index_path.exists():
            raise HTTPException(status_code=404, detail=f"index.html not found at {index_path}")
        return FileResponse(index_path)
    
    @app.get("/{path:path}")
    async def serve_frontend_paths(path: str):
        # Skip API paths
        if path.startswith("api/") or path.startswith("debug/"):
            raise HTTPException(status_code=404)
            
        file_path = frontend_dir / path
        logger.info(f"Request for: {path}, checking: {file_path}")
        
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # For SPA routing, serve index.html
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
else:
    logger.error(f"Frontend directory not found at: {frontend_dir}")
    logger.error(f"Current directory: {Path(__file__).parent}")
    logger.error(f"Directory contents: {list(Path(__file__).parent.iterdir())}")
    
    @app.get("/")
    async def root():
        current_dir = Path(__file__).parent
        return {
            "message": "PlumbFlow API is running",
            "status": "frontend files not found",
            "note": "Upload frontend folder to enable web interface",
            "looking_for": str(frontend_dir),
            "current_dir": str(current_dir),
            "contents": [str(p.name) for p in current_dir.iterdir()]
        }

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
