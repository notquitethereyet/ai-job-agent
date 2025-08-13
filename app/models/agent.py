"""
Agent models for JobTrackAI
Defines data structures for agent interactions
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, timezone
from app.models.job import JobStatus

class IntentType(str, Enum):
    """Types of user intent"""
    NEW_JOB = "new_job"
    STATUS_UPDATE = "status_update"
    JOB_SEARCH = "job_search"
    JOB_DELETE = "job_delete"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"

class UserMessage(BaseModel):
    """User message input"""
    message: str = Field(..., description="User's message")
    user_id: UUID = Field(..., description="Unique user identifier (UUID)")
    conversation_id: Optional[str] = Field(None, description="Conversation thread identifier")
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

class JobExtraction(BaseModel):
    """Extracted job information from user message"""
    job_title: Optional[str] = Field(None, description="Job title/role")
    company_name: Optional[str] = Field(None, description="Company name")
    job_link: Optional[str] = Field(None, description="URL to job posting")
    job_description: Optional[str] = Field(None, description="Job description")
    status: Optional[JobStatus] = Field(None, description="Parsed status if determinable from message")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")

class AgentResponse(BaseModel):
    """Agent response to user message"""
    response: str = Field(..., description="Natural language response")
    action_taken: str = Field(..., description="What action was performed")
    intent: IntentType = Field(..., description="Classified intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in classification")
    job_id: Optional[str] = Field(None, description="ID of created/updated job")
    conversation_id: Optional[str] = Field(None, description="Conversation thread identifier")
    requires_clarification: bool = Field(False, description="Whether clarification is needed")
    clarification_prompt: Optional[str] = Field(None, description="What clarification is needed")
    suggested_actions: Optional[list[str]] = Field(None, description="Suggested next actions")
