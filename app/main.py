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

# Jobs endpoints (placeholder)
@app.get("/jobs")
async def get_jobs():
    """Get all jobs for a user"""
    # TODO: Implement Supabase integration
    return {"jobs": [], "message": "Jobs endpoint under development"}

@app.post("/jobs")
async def create_job():
    """Create a new job entry"""
    # TODO: Implement job creation
    return {"message": "Job creation endpoint under development"}

@app.patch("/jobs/{job_id}")
async def update_job_status():
    """Update job status"""
    # TODO: Implement job status update
    return {"message": "Job update endpoint under development"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
