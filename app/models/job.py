"""
Job models for JobTrackAI
Defines data structures for job management
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class JobStatus(str, Enum):
    """Job application statuses"""
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    SCREENING = "screening"
    TECHNICAL = "technical"
    FINAL = "final"

class JobBase(BaseModel):
    """Base job model with common fields"""
    job_title: str = Field(..., description="Job title/role")
    company_name: str = Field(..., description="Company name")
    job_link: Optional[str] = Field(None, description="URL to job posting")
    job_description: Optional[str] = Field(None, description="Job description")
    status: JobStatus = Field(JobStatus.APPLIED, description="Current application status")

class JobCreate(JobBase):
    """Model for creating a new job"""
    user_id: str = Field(..., description="User who owns this job entry")

class JobUpdate(BaseModel):
    """Model for updating job information"""
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    job_link: Optional[str] = None
    job_description: Optional[str] = None
    status: Optional[JobStatus] = None

class Job(JobBase):
    """Complete job model"""
    id: str = Field(..., description="Unique job identifier")
    user_id: str = Field(..., description="User who owns this job entry")
    date_added: datetime = Field(..., description="When job was added")
    last_updated: datetime = Field(..., description="Last status change")
    
    class Config:
        from_attributes = True
