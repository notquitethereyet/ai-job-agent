"""
JobTrackAI - Main FastAPI Application
AI-powered job application tracking agent
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from dotenv import load_dotenv
from .models.agent import UserMessage, AgentResponse
from .services.agent_service import AgentService
from .services.supabase_service import SupabaseService
from .models.job import JobCreate, JobUpdate, JobStatus

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="JobTrackAI",
    description="AI-powered job application tracking agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
agent_service = AgentService()
supabase_service = SupabaseService()

# Health check endpoint
@app.get("/")
async def root():
    return {"message": "JobTrackAI is running!", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "JobTrackAI"}

# Main agent endpoint
@app.post("/agent/message", response_model=AgentResponse)
async def process_message(user_message: UserMessage):
    """
    Process user message and determine intent (new job vs status update)
    """
    try:
        logger.info(f"Processing message from user {user_message.user_id}: {user_message.message}")
        
        # Process message through agent service
        response = await agent_service.process_message(user_message)
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Jobs endpoints
@app.get("/jobs")
async def get_jobs(user_id: str, status: str = None):
    """Get all jobs for a user, optionally filtered by status"""
    try:
        job_status = JobStatus(status) if status else None
        jobs = await supabase_service.get_user_jobs(user_id, job_status)
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as e:
        logger.error(f"Error retrieving jobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs")

@app.post("/jobs")
async def create_job(job_data: JobCreate, user_id: str):
    """Create a new job entry"""
    try:
        job = await supabase_service.create_job(job_data, user_id)
        if job:
            return {"message": "Job created successfully", "job": job}
        else:
            raise HTTPException(status_code=400, detail="Failed to create job")
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create job")

@app.get("/jobs/{job_id}")
async def get_job(job_id: str, user_id: str):
    """Get a specific job by ID"""
    try:
        job = await supabase_service.get_job_by_id(job_id, user_id)
        if job:
            return {"job": job}
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        logger.error(f"Error retrieving job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job")

@app.patch("/jobs/{job_id}")
async def update_job_status(job_id: str, status_update: JobUpdate, user_id: str):
    """Update job status"""
    try:
        job = await supabase_service.update_job_status(job_id, status_update.status, user_id)
        if job:
            return {"message": "Job updated successfully", "job": job}
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        logger.error(f"Error updating job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update job")

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user_id: str):
    """Delete a job"""
    try:
        success = await supabase_service.delete_job(job_id, user_id)
        if success:
            return {"message": "Job deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        logger.error(f"Error deleting job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete job")

@app.get("/jobs/stats/{user_id}")
async def get_job_stats(user_id: str):
    """Get job statistics for a user"""
    try:
        stats = await supabase_service.get_job_stats(user_id)
        return {"stats": stats}
    except Exception as e:
        logger.error(f"Error retrieving job stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job stats")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
