"""
Simple working agent - immediate fix for the broken unified agent
Uses fewer API calls than the original but is guaranteed to work
"""

import logging
from typing import Optional
from app.models.agent import UserMessage, AgentResponse, IntentType
from app.models.job import JobStatus, JobCreate
from app.services.openai_service import OpenAIService
from app.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

class AgentService:
    """Simple, working agent service that reduces API calls while ensuring functionality"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
        self.supabase_service = SupabaseService()
    
    async def process_message(self, user_message: UserMessage) -> AgentResponse:
        """Process user message with simplified but working logic"""
        try:
            logger.info(f"Processing message (simple): {user_message.message[:100]}...")
            
            # Get or create conversation
            conversation_id = await self._ensure_conversation_id(user_message)
            
            # Persist user message
            if conversation_id:
                await self.supabase_service.add_message(
                    conversation_id=conversation_id,
                    user_id=str(user_message.user_id),
                    role="user",
                    content=user_message.message
                )
            
            # Smart intent detection with AI fallback for ambiguous cases
            intent, confidence = self._classify_intent_simple(user_message.message)
            
            # If confidence is low, use AI to classify properly
            if confidence < 0.5:
                try:
                    ai_intent, ai_confidence = await self._classify_with_ai(user_message.message)
                    if ai_confidence > confidence:
                        intent, confidence = ai_intent, ai_confidence
                except Exception as e:
                    logger.warning(f"AI classification failed, using rule-based: {e}")
            
            # Handle based on intent
            if intent == IntentType.JOB_SEARCH:
                return await self._handle_job_search(user_message, conversation_id)
            elif intent == IntentType.NEW_JOB:
                return await self._handle_new_job(user_message, conversation_id)
            elif intent == IntentType.STATUS_UPDATE:
                return await self._handle_status_update(user_message, conversation_id)
            elif intent == IntentType.JOB_DELETE:
                return await self._handle_job_deletion(user_message, conversation_id)
            else:
                # For other intents, use single AI call for response
                response_text = await self._generate_helpful_response(user_message.message)
                return AgentResponse(
                    response=response_text,
                    action_taken="information_provided",
                    intent=intent,
                    confidence=confidence,
                    conversation_id=conversation_id,
                    suggested_actions=["Add job", "Update status", "View jobs"]
                )
                
        except Exception as e:
            logger.error(f"Simple agent error: {e}")
            return self._emergency_fallback()
    
    def _classify_intent_simple(self, message: str) -> tuple[IntentType, float]:
        """Minimal rule-based classification - let AI handle the real work"""
        # Only catch the most obvious cases to avoid unnecessary API calls
        message_lower = message.lower().strip()
        
        # Only keep ultra-obvious patterns that would be wasteful to send to AI
        if message_lower in ["show my jobs", "list my jobs", "my jobs", "show jobs"]:
            return IntentType.JOB_SEARCH, 0.99
        
        # Everything else goes to AI for intelligent classification
        return IntentType.UNKNOWN, 0.1  # Low confidence triggers AI classification
    
    async def _classify_with_ai(self, message: str) -> tuple[IntentType, float]:
        """Use AI for edge cases that rules can't handle"""
        try:
            prompt = f"""
            You are JobTrackAI, an intelligent job application tracker. Analyze the user's intent based on CONTEXT and MEANING, not just keywords.
            
            Understand what the user wants to DO with their personal job tracker:
            
            INTENT OPTIONS:
            - job_search: User wants to VIEW their tracked applications
            - new_job: User wants to ADD a new application to track
            - status_update: User wants to CHANGE the status of an existing application  
            - job_delete: User wants to REMOVE an application from tracking
            - unknown: Not related to tracking job applications
            
            UNDERSTAND CONTEXT:
            - When someone mentions applying, submitting, or putting in applications → they want to ADD to tracker
            - When someone mentions outcomes (rejected, interview, offer) → they want to UPDATE status
            - When someone mentions wanting to see or check applications → they want to VIEW tracker
            - When someone mentions removing or deleting → they want to DELETE from tracker
            
            Use natural language understanding, not keyword matching. Consider:
            - The user's intent and goal
            - What action they're trying to accomplish
            - The context of their message
            
            Respond ONLY with: INTENT|CONFIDENCE (0.0-1.0)
            
            Message: "{message}"
            
            Think about what the user is trying to accomplish, then classify accordingly.
            """
            
            response = await self.openai_service._get_chat_completion(
                system_prompt="You are an intelligent intent classifier. Understand context and meaning, not just keywords. Be precise and confident.",
                user_message=prompt
            )
            
            if response and "|" in response:
                intent_str, conf_str = response.strip().split("|")
                intent_map = {
                    "job_search": IntentType.JOB_SEARCH,
                    "new_job": IntentType.NEW_JOB, 
                    "status_update": IntentType.STATUS_UPDATE,
                    "job_delete": IntentType.JOB_DELETE,
                    "unknown": IntentType.UNKNOWN
                }
                intent = intent_map.get(intent_str.lower(), IntentType.UNKNOWN)
                confidence = float(conf_str)
                return intent, confidence
                
        except Exception as e:
            logger.error(f"AI classification error: {e}")
        
        return IntentType.UNKNOWN, 0.3
    
    async def _handle_job_search(self, user_message: UserMessage, conversation_id: Optional[str]) -> AgentResponse:
        """Handle job listing - minimal API usage"""
        try:
            # Get user's jobs
            jobs = await self.supabase_service.get_user_jobs(
                user_id=str(user_message.user_id),
                limit=10
            )
            
            if not jobs:
                response_text = "You haven't added any job applications yet! Ready to add your first one? 🎯"
                suggested_actions = ["Add first job", "Share job link"]
            else:
                # Format job list with status text and emoji
                job_list = []
                for i, job in enumerate(jobs, 1):
                    status = job.get("status", "applied")
                    emoji = {"applied": "📝", "interview": "🎤", "offer": "🎉", "rejected": "❌", "withdrawn": "🚫"}.get(status, "📝")
                    # Show both status text and emoji for clarity
                    job_list.append(f"{i}. {job.get('job_title', 'Unknown')} at {job.get('company_name', 'Unknown')} - {status} {emoji}")
                
                jobs_formatted = "\n".join(job_list)
                response_text = f"Here are your {len(jobs)} applications:\n\n{jobs_formatted}\n\nKeep pushing forward! ✨"
                suggested_actions = ["Update status", "Add job"]
            
            return AgentResponse(
                response=response_text,
                action_taken="job_search",
                intent=IntentType.JOB_SEARCH,
                confidence=0.95,
                conversation_id=conversation_id,
                suggested_actions=suggested_actions
            )
            
        except Exception as e:
            logger.error(f"Job search error: {e}")
            return self._emergency_fallback()
    
    async def _handle_new_job(self, user_message: UserMessage, conversation_id: Optional[str]) -> AgentResponse:
        """Handle new job creation with single AI call for extraction"""
        try:
            # Single AI call to extract job details
            extraction_prompt = f"""
            Extract job details from this message and respond with JSON:
            {{
                "job_title": "Software Engineer",
                "company_name": "Google",
                "status": "applied",
                "job_link": "https://..."
            }}
            
            Message: {user_message.message}
            
            Rules:
            - If no explicit status, assume "applied"
            - Set null for missing fields
            - Company names should be properly capitalized
            """
            
            response = await self.openai_service._get_chat_completion(
                system_prompt="Extract job details as JSON. Be accurate.",
                user_message=extraction_prompt,
                response_format={"type": "json_object"}
            )
            
            if response:
                import json
                extracted = json.loads(response)
                
                if extracted.get("job_title") and extracted.get("company_name"):
                    # Create the job
                    job_data = JobCreate(
                        user_id=str(user_message.user_id),
                        job_title=extracted["job_title"],
                        company_name=extracted["company_name"],
                        job_link=extracted.get("job_link"),
                        status=JobStatus(extracted.get("status", "applied"))
                    )
                    
                    created_job = await self.supabase_service.create_job(job_data, str(user_message.user_id))
                    
                    if created_job:
                        response_text = f"Added your {job_data.job_title} application at {job_data.company_name}! 🎯 Good luck!"
                        return AgentResponse(
                            response=response_text,
                            action_taken="job_created",
                            intent=IntentType.NEW_JOB,
                            confidence=0.9,
                            job_id=created_job.get("id"),
                            conversation_id=conversation_id,
                            suggested_actions=["Update status", "View jobs"]
                        )
                
                # Missing required fields
                missing = []
                if not extracted.get("job_title"):
                    missing.append("job title")
                if not extracted.get("company_name"):
                    missing.append("company name")
                
                response_text = f"I need the {' and '.join(missing)} to add this job. Can you provide that?"
                return AgentResponse(
                    response=response_text,
                    action_taken="clarification_needed",
                    intent=IntentType.NEW_JOB,
                    confidence=0.8,
                    conversation_id=conversation_id,
                    requires_clarification=True,
                    suggested_actions=["Provide details"]
                )
            
        except Exception as e:
            logger.error(f"New job error: {e}")
        
        return AgentResponse(
            response="I'd love to help you add that job! What's the job title and company?",
            action_taken="clarification_needed",
            intent=IntentType.NEW_JOB,
            confidence=0.8,
            conversation_id=conversation_id,
            requires_clarification=True
        )
    
    async def _handle_status_update(self, user_message: UserMessage, conversation_id: Optional[str]) -> AgentResponse:
        """Handle status updates simply"""
        try:
            # Get recent jobs for context
            jobs = await self.supabase_service.get_user_jobs(
                user_id=str(user_message.user_id),
                limit=5
            )
            
            if not jobs:
                return AgentResponse(
                    response="You don't have any jobs to update yet. Want to add one?",
                    action_taken="clarification_needed",
                    intent=IntentType.STATUS_UPDATE,
                    confidence=0.8,
                    conversation_id=conversation_id,
                    suggested_actions=["Add job"]
                )
            
            # AI-powered status and company extraction
            extraction_prompt = f"""
            Extract status update information from this message:
            
            Message: "{user_message.message}"
            
            Respond with JSON:
            {{
                "status": "rejected|interview|offer|withdrawn|applied",
                "companies": ["Tesla", "xAI"],
                "confidence": 0.95
            }}
            
            Rules:
            - Extract ALL companies mentioned
            - Determine the status from context
            - Be confident if the intent is clear
            """
            
            try:
                response = await self.openai_service._get_chat_completion(
                    system_prompt="Extract job status information as JSON. Be accurate.",
                    user_message=extraction_prompt,
                    response_format={"type": "json_object"}
                )
                
                if response:
                    import json
                    extracted = json.loads(response)
                    new_status = JobStatus(extracted.get("status")) if extracted.get("status") else None
                    mentioned_companies = extracted.get("companies", [])
                else:
                    new_status = None
                    mentioned_companies = []
            except Exception as e:
                logger.warning(f"AI extraction failed: {e}")
                # Fallback to simple detection
                message_lower = user_message.message.lower()
                new_status = None
                mentioned_companies = []
                
                if any(word in message_lower for word in ["rejected", "reject", "didn't get", "no longer"]):
                    new_status = JobStatus.REJECTED
                elif any(word in message_lower for word in ["interview", "phone screen", "onsite"]):
                    new_status = JobStatus.INTERVIEW
                elif any(word in message_lower for word in ["offer", "offered"]):
                    new_status = JobStatus.OFFER
                elif any(word in message_lower for word in ["withdrew", "withdrawn", "withdraw"]):
                    new_status = JobStatus.WITHDRAWN
            
            if new_status:
                # Handle multiple companies intelligently
                jobs_to_update = []
                
                if mentioned_companies:
                    # AI extracted specific companies
                    for company in mentioned_companies:
                        for job in jobs:
                            if job.get("company_name", "").lower() == company.lower():
                                jobs_to_update.append(job)
                else:
                    # Fallback: look for company names in message
                    message_lower = user_message.message.lower()
                    for job in jobs:
                        company = job.get("company_name", "").lower()
                        if company and company in message_lower:
                            jobs_to_update.append(job)
                
                if jobs_to_update:
                    updated_jobs = []
                    
                    # Update all matching jobs
                    for job in jobs_to_update:
                        updated = await self.supabase_service.update_job_status(
                            job_id=job["id"],
                            status=new_status,
                            user_id=str(user_message.user_id)
                        )
                        if updated:
                            updated_jobs.append(updated)
                    
                    if updated_jobs:
                        if len(updated_jobs) == 1:
                            # Single job updated
                            job = updated_jobs[0]
                            response_text = f"Updated {job['job_title']} at {job['company_name']} to {new_status.value}! "
                        else:
                            # Multiple jobs updated
                            companies = [job['company_name'] for job in updated_jobs]
                            response_text = f"Updated {len(updated_jobs)} applications at {', '.join(companies)} to {new_status.value}! "
                        
                        # Add encouraging message based on status
                        if new_status == JobStatus.REJECTED:
                            response_text += "Keep your head up - you've got this! 💪"
                        elif new_status == JobStatus.INTERVIEW:
                            response_text += "Exciting! Time to prep! 🎯"
                        elif new_status == JobStatus.OFFER:
                            response_text += "CONGRATULATIONS! 🎉"
                        
                        return AgentResponse(
                            response=response_text,
                            action_taken="status_updated",
                            intent=IntentType.STATUS_UPDATE,
                            confidence=0.9,
                            job_id=updated_jobs[0].get("id") if len(updated_jobs) == 1 else None,
                            conversation_id=conversation_id,
                            suggested_actions=["View jobs"]
                        )
            
            # Need clarification
            return AgentResponse(
                response="I'd like to help update a job status! Which job and what's the new status?",
                action_taken="clarification_needed",
                intent=IntentType.STATUS_UPDATE,
                confidence=0.8,
                conversation_id=conversation_id,
                requires_clarification=True,
                suggested_actions=["Specify job", "View jobs"]
            )
            
        except Exception as e:
            logger.error(f"Status update error: {e}")
            return self._emergency_fallback()
    
    async def _generate_helpful_response(self, message: str) -> str:
        """Single AI call for responses - STRICTLY focused on tracker operations"""
        try:
            response = await self.openai_service._get_chat_completion(
                system_prompt="""You are JobTrackAI, a job application TRACKER. You ONLY help users manage their personal job tracker.

STRICT RULES:
- DO NOT give career advice, interview tips, or general job search guidance
- DO NOT suggest how to apply to companies or improve resumes
- ONLY help with tracker operations: add jobs, update status, view jobs, delete jobs
- If the user mentions a job, ask if they want to ADD it to their tracker
- Keep responses short and focused on tracker actions
- NO generic advice, NO bullshit

Your ONLY job is managing their personal job tracker database.""",
                user_message=f"User said: {message}. Respond ONLY about tracker operations - add, update, view, or delete jobs."
            )
            return response or "I help you track your job applications. Want to add a job, update a status, or view your jobs?"
        except Exception:
            return "I help you track your job applications. Want to add a job, update a status, or view your jobs?"
    
    async def _ensure_conversation_id(self, user_message: UserMessage) -> Optional[str]:
        """Get or create conversation ID"""
        if user_message.conversation_id:
            return user_message.conversation_id
        
        try:
            conv = await self.supabase_service.get_or_create_recent_conversation(str(user_message.user_id))
            return conv.get("id") if conv else None
        except Exception:
            return None
    
    async def _handle_job_deletion(self, user_message: UserMessage, conversation_id: Optional[str]) -> AgentResponse:
        """Handle job deletion requests"""
        try:
            # Get user's jobs
            jobs = await self.supabase_service.get_user_jobs(
                user_id=str(user_message.user_id),
                limit=10
            )
            
            if not jobs:
                return AgentResponse(
                    response="You don't have any jobs to delete yet. Want to add one?",
                    action_taken="information_provided",
                    intent=IntentType.JOB_DELETE,
                    confidence=0.8,
                    conversation_id=conversation_id,
                    suggested_actions=["Add job"]
                )
            
            # Try to find matching job to delete
            message_lower = user_message.message.lower()
            target_job = None
            
            # Look for company name mentioned
            for job in jobs:
                company = job.get("company_name", "").lower()
                job_title = job.get("job_title", "").lower()
                
                if company and company in message_lower:
                    # If company mentioned, check for job title match too
                    if ("machine learning" in message_lower and "machine learning" in job_title) or \
                       ("full stack" in message_lower and "full stack" in job_title) or \
                       ("software engineer" in message_lower and "software engineer" in job_title) or \
                       len([j for j in jobs if j.get("company_name", "").lower() == company]) == 1:
                        target_job = job
                        break
            
            if target_job:
                # Delete the job
                success = await self.supabase_service.delete_job(
                    job_id=target_job["id"],
                    user_id=str(user_message.user_id)
                )
                
                if success:
                    response_text = f"Deleted {target_job['job_title']} at {target_job['company_name']} from your tracker. Clean slate! ✨"
                    return AgentResponse(
                        response=response_text,
                        action_taken="job_deleted",
                        intent=IntentType.JOB_DELETE,
                        confidence=0.9,
                        conversation_id=conversation_id,
                        suggested_actions=["View remaining jobs", "Add new job"]
                    )
                else:
                    return AgentResponse(
                        response="Couldn't delete that job right now. Please try again!",
                        action_taken="error",
                        intent=IntentType.JOB_DELETE,
                        confidence=0.8,
                        conversation_id=conversation_id
                    )
            else:
                # Ask for clarification
                job_list = "\n".join([f"{i+1}. {j['job_title']} at {j['company_name']}" for i, j in enumerate(jobs)])
                response_text = f"Which job would you like to delete?\n\n{job_list}\n\nReply with the number or be more specific!"
                
                return AgentResponse(
                    response=response_text,
                    action_taken="clarification_needed",
                    intent=IntentType.JOB_DELETE,
                    confidence=0.8,
                    conversation_id=conversation_id,
                    requires_clarification=True,
                    suggested_actions=["Specify job", "View all jobs"]
                )
                
        except Exception as e:
            logger.error(f"Job deletion error: {e}")
            return self._emergency_fallback()

    def _emergency_fallback(self) -> AgentResponse:
        """When everything fails"""
        return AgentResponse(
            response="I'm having trouble understanding. Could you try rephrasing that? ✨",
            action_taken="error",
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            suggested_actions=["Add job", "Update status", "View jobs"]
        )
