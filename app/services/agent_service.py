"""
Agent service for JobTrackAI
Orchestrates AI agent logic and coordinates between services
"""

import logging
from typing import Optional
from ..models.agent import UserMessage, AgentResponse, IntentType, JobExtraction
from ..models.job import JobCreate, JobStatus
from .openai_service import OpenAIService
from .job_service import JobService

logger = logging.getLogger(__name__)

class AgentService:
    """Main agent service that processes user messages"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
        self.job_service = JobService()
    
    async def process_message(self, user_message: UserMessage) -> AgentResponse:
        """
        Main method to process user message and determine appropriate action
        """
        try:
            logger.info(f"Processing message: {user_message.message[:100]}...")
            
            # Step 1: Classify intent
            intent, confidence = await self.openai_service.classify_intent(user_message.message)
            logger.info(f"Classified intent: {intent} (confidence: {confidence})")
            
            # Step 2: Process based on intent
            if intent == IntentType.NEW_JOB:
                return await self._handle_new_job(user_message, confidence)
            elif intent == IntentType.STATUS_UPDATE:
                return await self._handle_status_update(user_message, confidence)
            elif intent == IntentType.JOB_SEARCH:
                return await self._handle_job_search(user_message, confidence)
            elif intent == IntentType.AMBIGUOUS:
                return await self._handle_ambiguous_message(user_message, confidence)
            else:
                return await self._handle_unknown_intent(user_message, confidence)
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return AgentResponse(
                response="I'm experiencing technical difficulties. Please try again.",
                action_taken="error",
                intent=IntentType.UNKNOWN,
                confidence=0.0
            )
    
    async def _handle_new_job(self, user_message: UserMessage, confidence: float) -> AgentResponse:
        """Handle new job application intent"""
        try:
            # Extract job details from message
            job_extraction = await self.openai_service.extract_job_details(user_message.message)
            
            if job_extraction.confidence > 0.7:
                # Create new job
                job_data = JobCreate(
                    user_id=user_message.user_id,
                    job_title=job_extraction.job_title or "Unknown Title",
                    company_name=job_extraction.company_name or "Unknown Company",
                    job_link=job_extraction.job_link,
                    job_description=job_extraction.job_description,
                    status=JobStatus.APPLIED
                )
                
                job = await self.job_service.create_job(job_data)
                
                return AgentResponse(
                    response=f"I've added your application for {job.job_title} at {job.company_name} to your tracking list.",
                    action_taken="job_created",
                    intent=IntentType.NEW_JOB,
                    job_id=job.id,
                    confidence=confidence
                )
            else:
                # Ask for clarification
                return AgentResponse(
                    response="I'd like to add this job to your tracking list, but I need more details. Could you please provide the job title and company name?",
                    action_taken="clarification_needed",
                    intent=IntentType.NEW_JOB,
                    confidence=confidence,
                    requires_clarification=True,
                    clarification_prompt="Please provide: Job Title, Company Name"
                )
                
        except Exception as e:
            logger.error(f"Error handling new job: {str(e)}")
            return AgentResponse(
                response="I encountered an issue while adding your job. Please try again.",
                action_taken="error",
                intent=IntentType.NEW_JOB,
                confidence=confidence
            )
    
    async def _handle_status_update(self, user_message: UserMessage, confidence: float) -> AgentResponse:
        """Handle job status update intent"""
        try:
            # TODO: Implement job status update logic
            # For now, return a placeholder response
            return AgentResponse(
                response="I understand you want to update a job status. This feature is coming soon!",
                action_taken="status_update_placeholder",
                intent=IntentType.STATUS_UPDATE,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error handling status update: {str(e)}")
            return AgentResponse(
                response="I encountered an issue while processing your status update. Please try again.",
                action_taken="error",
                intent=IntentType.STATUS_UPDATE,
                confidence=confidence
            )
    
    async def _handle_job_search(self, user_message: UserMessage, confidence: float) -> AgentResponse:
        """Handle job search/query intent"""
        try:
            # TODO: Implement job search logic
            # For now, return a placeholder response
            return AgentResponse(
                response="I understand you want to search your job applications. This feature is coming soon!",
                action_taken="job_search_placeholder",
                intent=IntentType.JOB_SEARCH,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error handling job search: {str(e)}")
            return AgentResponse(
                response="I encountered an issue while searching your jobs. Please try again.",
                action_taken="error",
                intent=IntentType.JOB_SEARCH,
                confidence=confidence
            )
    
    async def _handle_ambiguous_message(self, user_message: UserMessage, confidence: float) -> AgentResponse:
        """Handle ambiguous messages that need clarification"""
        return AgentResponse(
            response="I'm not sure what you'd like me to do. Could you please clarify? Are you adding a new job, updating a status, or looking for something else?",
            action_taken="clarification_needed",
            intent=IntentType.AMBIGUOUS,
            confidence=confidence,
            requires_clarification=True,
            clarification_prompt="Please clarify your request"
        )
    
    async def _handle_unknown_intent(self, user_message: UserMessage, confidence: float) -> AgentResponse:
        """Handle unknown intent messages"""
        return AgentResponse(
            response="I'm not sure how to help with that request. I can help you track job applications, update job statuses, or search your job list. What would you like to do?",
            action_taken="unknown_intent",
            intent=IntentType.UNKNOWN,
            confidence=confidence
        )
