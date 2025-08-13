"""
Agent service for JobTrackAI
Orchestrates AI agent logic and coordinates between services
"""

import logging
import re
import json
import html as html_module
from typing import Optional
# from openai_agents import Agent  # Not available, using simpler approach
from app.models.agent import UserMessage, AgentResponse, IntentType, JobExtraction
from app.models.job import JobCreate, JobStatus
from app.services.openai_service import OpenAIService
from app.services.job_service import JobService
from app.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

# Schema-aware guidance to keep AI prompts aligned with DB columns only
SCHEMA_PROMPT = (
    "You must only request or confirm fields that exist in the jobs table schema. "
    "The available fields are exactly: job_title (text), company_name (text), job_link (text, optional), "
    "job_description (text, optional), status (text: applied | interview | offer | rejected | withdrawn), "
    "date_added (timestamp, optional – defaults to now). Do not ask for any other fields. "
    "If you can infer a field from the user's message (e.g., status='applied' when they say 'applied' or when a job link is shared), do not ask for it. "
    "Only ask for truly missing required fields. If exactly one required field is missing, ask for that one field only. "
    "If sufficient information is present (job_title and company_name), proceed as if the record will be created with status defaulting to 'applied' and acknowledge it. "
    "Do not request contact person, location, application method, or anything else not listed above. "
    "If a field is optional and the user doesn't provide it, proceed and note it as missing. For date_added, use 'today' by default if not provided."
)

class AgentService:
    """Main agent service that processes user messages"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
        self.job_service = JobService()
        self.supabase_service = SupabaseService()
        
        # Initialize specialized agents (simplified approach)
        self.job_tracking_agent = None  # Will use OpenAI service directly
        self.job_parser_agent = None    # Will use OpenAI service directly
    
    async def process_message(self, user_message: UserMessage) -> AgentResponse:
        """
        Main method to process user message and determine appropriate action
        """
        try:
            logger.info(f"Processing message: {user_message.message[:100]}...")

            # Ensure we have a conversation_id (reuse most recent if absent)
            conversation_id = user_message.conversation_id
            if not conversation_id:
                conv = await self.supabase_service.get_or_create_recent_conversation(str(user_message.user_id))
                if conv and conv.get("id"):
                    conversation_id = conv["id"]

            # Persist incoming user message
            if conversation_id:
                await self.supabase_service.add_message(
                    conversation_id=conversation_id,
                    user_id=str(user_message.user_id),
                    role="user",
                    content=user_message.message
                )

            # Build context from recent messages
            recent_context = ""
            if conversation_id:
                recent_msgs = await self.supabase_service.get_recent_messages(conversation_id, limit=8)
                if recent_msgs:
                    formatted = []
                    for m in recent_msgs:
                        prefix = "User" if m.get("role") == "user" else "Assistant"
                        formatted.append(f"{prefix}: {m.get('content','')}")
                    recent_context = "\n".join(formatted)
            
            # Placeholder response text for fallback construction
            response: str = ""

            # Use OpenAI for intent classification, with safe fallbacks
            has_link = self._contains_job_link(user_message.message)
            looks_like_search = self._is_job_search_query(user_message.message)
            intent, confidence = await self.openai_service.classify_intent(user_message.message)
            if intent in (IntentType.UNKNOWN, IntentType.AMBIGUOUS) or confidence < 0.6:
                # Fallback to lightweight keyword rules
                fb_intent, fb_conf = self._classify_intent_simple(user_message.message)
                if fb_intent != IntentType.UNKNOWN:
                    intent, confidence = fb_intent, max(confidence, fb_conf)
            # Strong hint: if there's a link and intent is still unclear, treat as new job
            if intent in (IntentType.UNKNOWN, IntentType.AMBIGUOUS) and has_link:
                intent, confidence = IntentType.NEW_JOB, max(confidence, 0.85)
            # If the text clearly looks like a search query (e.g., "show ... applications"), prefer JOB_SEARCH
            if looks_like_search and intent != IntentType.NEW_JOB:
                intent, confidence = IntentType.JOB_SEARCH, max(confidence, 0.9)

            # Guardrail: detect unsafe/malicious requests (internal ids, env vars, secrets)
            # Safety check: combine LLM detection with lightweight keyword markers
            lower = user_message.message.lower()
            unsafe_markers = [
                "internal ids", "internal id", "environment variables", "env vars", "env variables",
                "secret key", "secrets", "service key", "api keys", "api key", "credentials", "password", "tokens"
            ]
            is_unsafe_llm, unsafe_conf, unsafe_reason = await self.openai_service.detect_unsafe_request(user_message.message)
            if is_unsafe_llm or any(marker in lower for marker in unsafe_markers):
                refusal = await self.openai_service.generate_friendly_refusal(unsafe_reason or "sensitive data request")
                agent_response = AgentResponse(
                    response=refusal,
                    action_taken="information_provided",
                    intent=IntentType.UNKNOWN,
                    confidence=max(confidence, unsafe_conf, 0.9),
                    conversation_id=conversation_id,
                    suggested_actions=["Show jobs", "Add new job", "Update status"],
                )
                # Persist and return early
                if conversation_id:
                    await self.supabase_service.add_message(
                        conversation_id=conversation_id,
                        user_id=str(user_message.user_id),
                        role="assistant",
                        content=agent_response.response,
                        tool_calls={
                            "intent": agent_response.intent.value,
                            "confidence": agent_response.confidence,
                            "action_taken": agent_response.action_taken,
                            "job_id": agent_response.job_id
                        }
                    )
                return agent_response

            # Enhanced emotional intelligence handling
            is_job_related, jr_conf = await self.openai_service.detect_job_related(user_message.message)
            
            # If it's job-related but emotionally charged, handle with empathy first
            if is_job_related:
                emotion, emotion_conf = await self.openai_service.detect_emotional_state(user_message.message)
                
                # Special handling for interview anxiety and frustration
                if emotion in ["anxious", "frustrated", "disappointed"] and emotion_conf > 0.7:
                    # Check if they're talking about a specific job for interview prep
                    if emotion == "anxious" and any(word in user_message.message.lower() 
                                                   for word in ["interview", "nervous", "scared", "anxious"]):
                        # Try to find recent interview-status jobs for prep advice
                        recent_interviews = await self.supabase_service.search_jobs(
                            user_id=str(user_message.user_id),
                            status_filter="interview",
                            limit=3
                        )
                        
                        if recent_interviews:
                            job_info = recent_interviews[0]  # Most recent interview
                            prep_advice = await self.openai_service.generate_interview_prep_response(job_info)
                            response_text = f"Interview nerves are totally normal! Here's some prep for {job_info['job_title']} at {job_info['company_name']}:\n\n{prep_advice}"
                        else:
                            response_text = await self.openai_service.generate_emotional_support_response(user_message.message, emotion)
                    else:
                        response_text = await self.openai_service.generate_emotional_support_response(user_message.message, emotion)
                    
                    agent_response = AgentResponse(
                        response=response_text,
                        action_taken="emotional_support",
                        intent=IntentType.UNKNOWN,
                        confidence=max(confidence, emotion_conf, 0.9),
                        conversation_id=conversation_id,
                        suggested_actions=["Show jobs", "Interview prep", "Add new job"] if emotion == "anxious" 
                                       else ["Add new job", "Update status", "Show jobs"],
                    )
                    if conversation_id:
                        await self.supabase_service.add_message(
                            conversation_id=conversation_id,
                            user_id=str(user_message.user_id),
                            role="assistant",
                            content=agent_response.response,
                            tool_calls={
                                "intent": agent_response.intent.value,
                                "confidence": agent_response.confidence,
                                "action_taken": agent_response.action_taken,
                                "job_id": agent_response.job_id,
                                "emotion_detected": emotion
                            }
                        )
                    return agent_response
            
            # Off-topic/small-talk handling: if not job-related, reply kindly and redirect
            if not is_job_related:
                smalltalk = await self.openai_service.generate_smalltalk_redirect(user_message.message)
                agent_response = AgentResponse(
                    response=smalltalk,
                    action_taken="information_provided",
                    intent=IntentType.UNKNOWN,
                    confidence=max(confidence, jr_conf, 0.9),
                    conversation_id=conversation_id,
                    suggested_actions=["Add new job", "Update status", "Show jobs"],
                )
                if conversation_id:
                    await self.supabase_service.add_message(
                        conversation_id=conversation_id,
                        user_id=str(user_message.user_id),
                        role="assistant",
                        content=agent_response.response,
                        tool_calls={
                            "intent": agent_response.intent.value,
                            "confidence": agent_response.confidence,
                            "action_taken": agent_response.action_taken,
                            "job_id": agent_response.job_id
                        }
                    )
                return agent_response
            
            # Helper to build a strict, schema-aware context for the LLM
            def build_context(instruction_header: str) -> str:
                base = [instruction_header, SCHEMA_PROMPT]
                if recent_context:
                    base.append(f"Recent messages (most recent last):\n{recent_context}")
                return "\n\n".join(base)

            # NEW JOB: try structured extraction and auto-create if possible
            if intent == IntentType.NEW_JOB:
                if has_link:
                    return await self._handle_job_link_message(user_message)
                extraction = await self.openai_service.extract_job_details(user_message.message)
                created_response = await self._maybe_create_job_from_extraction(user_message, extraction)
                if created_response:
                    agent_response = created_response
                else:
                    # Ask only for the truly missing required fields
                    missing = self._missing_required_fields(extraction)
                    prompt_lines = []
                    if extraction.job_link:
                        prompt_lines.append(f"I found a job link: {extraction.job_link}")
                    if extraction.company_name:
                        prompt_lines.append(f"Company: {extraction.company_name}")
                    if extraction.job_title:
                        prompt_lines.append(f"Job Title: {extraction.job_title}")
                    status_val = extraction.status or JobStatus.APPLIED
                    prompt_lines.append(f"Status: {status_val.value}")

                    if missing:
                        missing_str = ", ".join(missing)
                        # Friendly prompt via LLM
                        known = {
                            "company_name": extraction.company_name,
                            "job_title": extraction.job_title,
                            "status": (status_val.value if isinstance(status_val, JobStatus) else str(status_val)),
                            "job_link": extraction.job_link,
                        }
                        response = await self.openai_service.generate_friendly_missing_fields(
                            known_fields=known,
                            missing_fields=missing,
                        )
                        # Save pending details into conversation metadata so confirmations can finalize
                        try:
                            if conversation_id:
                                metadata = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                metadata["pending_new_job"] = {
                                    "job_title": extraction.job_title,
                                    "company_name": extraction.company_name,
                                    "job_link": extraction.job_link,
                                    "job_description": extraction.job_description,
                                    "status": (status_val.value if isinstance(status_val, JobStatus) else str(status_val))
                                }
                                await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                        except Exception as e:
                            logger.warning(f"Failed to persist pending_new_job metadata: {e}")
                        agent_response = AgentResponse(
                            response=response,
                            action_taken="clarification_needed",
                            intent=intent,
                            confidence=confidence,
                            requires_clarification=True,
                            clarification_prompt=f"Provide: {missing_str}",
                            suggested_actions=["Add job details", "Set status", "Skip for now"],
                            conversation_id=conversation_id,
                        )
                    else:
                        # Both required fields present but creation didn't occur: return explicit error, not LLM phrasing
                        try:
                            if conversation_id:
                                metadata = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                metadata["pending_new_job"] = {
                                    "job_title": extraction.job_title,
                                    "company_name": extraction.company_name,
                                    "job_link": extraction.job_link,
                                    "job_description": extraction.job_description,
                                    "status": (status_val.value if isinstance(status_val, JobStatus) else str(status_val))
                                }
                                await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                        except Exception as e:
                            logger.warning(f"Failed to persist pending_new_job after creation failure: {e}")

                        response = await self.openai_service.generate_dynamic_response(
                            "job_creation_failed",
                            {
                                "job_title": extraction.job_title,
                                "company_name": extraction.company_name,
                                "action": "creating job entry"
                            },
                            user_message.message,
                            recent_context
                        )
                        agent_response = AgentResponse(
                            response=response,
                            action_taken="error",
                            intent=intent,
                            confidence=confidence,
                            suggested_actions=["Retry", "Share job link", "Add description"],
                            conversation_id=conversation_id,
                        )
            elif intent == IntentType.STATUS_UPDATE:
                extraction = await self.openai_service.extract_job_details(user_message.message)
                new_status = extraction.status or JobStatus.INTERVIEW if "interview" in user_message.message.lower() else extraction.status
                bulk_all = self._is_bulk_all_command(user_message.message)

                if not new_status:
                    response = await self.openai_service.generate_dynamic_response(
                        "status_missing",
                        {
                            "available_statuses": ["applied", "interview", "offer", "rejected", "withdrawn"],
                            "user_intent": "status_update"
                        },
                        user_message.message,
                        recent_context
                    )
                    agent_response = AgentResponse(
                        response=response,
                        action_taken="clarification_needed",
                        intent=intent,
                        confidence=confidence,
                        requires_clarification=True,
                        clarification_prompt="Provide: status (applied/interview/offer/rejected/withdrawn)",
                        suggested_actions=["Set status", "View all jobs"],
                        conversation_id=conversation_id,
                    )
                else:
                    # Handle bulk "all" updates gracefully
                    if bulk_all:
                        all_jobs = await self.supabase_service.get_user_jobs(user_id=str(user_message.user_id))
                        if not all_jobs:
                            response = await self.openai_service.generate_dynamic_response(
                                "no_jobs_found",
                                {
                                    "action_attempted": "bulk status update",
                                    "suggested_action": "add first job"
                                },
                                user_message.message,
                                recent_context
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="information_provided",
                                intent=intent,
                                confidence=confidence,
                                suggested_actions=["Add new job", "View all jobs"],
                                conversation_id=conversation_id,
                            )
                        else:
                            try:
                                if conversation_id:
                                    meta0 = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                    meta0["pending_bulk_update"] = {
                                        "status": new_status.value if new_status else None,
                                        "count": len(all_jobs),
                                    }
                                    await self.supabase_service.update_conversation_metadata(conversation_id, meta0)
                            except Exception:
                                pass
                            response = await self.openai_service.generate_dynamic_response(
                                "bulk_confirmation",
                                {
                                    "job_count": len(all_jobs),
                                    "new_status": new_status.value,
                                    "jobs": [{"title": j.get("job_title"), "company": j.get("company_name")} for j in all_jobs[:3]]
                                },
                                user_message.message,
                                recent_context
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="clarification_needed",
                                intent=intent,
                                confidence=confidence,
                                requires_clarification=True,
                                clarification_prompt="Reply: 'yes all' to confirm or 'cancel'",
                                suggested_actions=["View all jobs", "Cancel"],
                                conversation_id=conversation_id,
                            )
                            # short-circuit to finalization later
                    else:
                        # If the user replied with a number, try to resolve pending selection
                        selection_index = self._extract_selection_index(user_message.message)
                        # Also try to parse an explicit status in the same message (e.g., "2nd one rejected")
                        try:
                            parsed_details = await self.openai_service.extract_job_details(user_message.message)
                            selection_status = parsed_details.status
                        except Exception:
                            selection_status = None

                    pending_candidates = None
                    pending_status = None
                    if conversation_id:
                        try:
                            meta = await self.supabase_service.get_conversation_metadata(conversation_id)
                            pend = (meta or {}).get("pending_job_selection") if meta else None
                            if pend and pend.get("type") == "status_update":
                                pending_candidates = pend.get("candidates")
                                pending_status = pend.get("new_status")
                        except Exception:
                            pass

                    if selection_index and pending_candidates:
                        chosen = next((c for c in pending_candidates if c.get("index") == selection_index), None)
                        if chosen:
                            resolved_status = (
                                selection_status
                                or (JobStatus(pending_status) if pending_status else None)
                                or new_status
                            )
                            if not resolved_status:
                                # Persist the selected job and ask only for the status
                                try:
                                    if conversation_id:
                                        meta = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                        meta["pending_status_job"] = {"id": chosen["id"], "job_title": chosen.get("job_title"), "company_name": chosen.get("company_name")}
                                        await self.supabase_service.update_conversation_metadata(conversation_id, meta)
                                except Exception:
                                    pass
                                response = await self.openai_service.generate_friendly_error(
                                    error_type="status_prompt",
                                    context={"options": ["applied", "interview", "offer", "rejected", "withdrawn"]}
                                )
                                agent_response = AgentResponse(
                                    response=response,
                                    action_taken="clarification_needed",
                                    intent=intent,
                                    confidence=confidence,
                                    requires_clarification=True,
                                    clarification_prompt="Provide: status (applied/interview/offer/rejected/withdrawn)",
                                    suggested_actions=["Set status", "View all jobs"],
                                    conversation_id=conversation_id,
                                )
                                # will be handled on next turn
                            else:
                                updated = await self.supabase_service.update_job_status(
                                    job_id=chosen["id"],
                                    status=resolved_status,
                                    user_id=str(user_message.user_id),
                                )
                                if updated:
                                    # Clear pending selection
                                    try:
                                        meta["pending_job_selection"] = None
                                        await self.supabase_service.update_conversation_metadata(conversation_id, meta)
                                    except Exception:
                                        pass
                                    response = await self.openai_service.generate_friendly_status_updated(
                                        job_title=updated['job_title'],
                                        company_name=updated['company_name'],
                                        status=updated['status'],
                                        user_message=user_message.message,
                                        conversation_context=recent_context,
                                    )
                                    agent_response = AgentResponse(
                                        response=response,
                                        action_taken="status_updated",
                                        intent=intent,
                                        confidence=confidence,
                                        job_id=updated.get("id"),
                                        suggested_actions=["View all jobs", "Add notes"],
                                        conversation_id=conversation_id,
                                    )
                                    # short-circuit return path at end
                        # If selection invalid, fall through to normal matching

                    # Find matching jobs for this user
                    matches = await self.supabase_service.search_jobs(
                        user_id=str(user_message.user_id),
                        company_name=extraction.company_name,
                        job_title=extraction.job_title,
                    )
                    if not matches:
                        # Be more specific about what we searched for and offer clear options
                        detail_bits = []
                        if extraction.job_title:
                            detail_bits.append(f"'{extraction.job_title}'")
                        if extraction.company_name:
                            detail_bits.append(f"at {extraction.company_name}")
                        detail = " ".join(detail_bits) if detail_bits else "that job"
                        
                        # Get all user jobs to show what they do have
                        all_user_jobs = await self.supabase_service.get_user_jobs(user_id=str(user_message.user_id), limit=5)
                        
                        response = await self.openai_service.generate_dynamic_response(
                            "job_not_found_with_clarification",
                            {
                                "job_title": extraction.job_title,
                                "company_name": extraction.company_name,
                                "searched_for": detail,
                                "action_attempted": "status update",
                                "available_jobs": [{"title": j.get("job_title"), "company": j.get("company_name"), "status": j.get("status")} for j in all_user_jobs],
                                "user_message": user_message.message
                            },
                            user_message.message,
                            recent_context
                        )
                        agent_response = AgentResponse(
                            response=response,
                            action_taken="clarification_needed",
                            intent=intent,
                            confidence=confidence,
                            requires_clarification=True,
                            clarification_prompt=f"We searched for {detail} but couldn't find it. Please specify which job to update or if I should add it as new.",
                            suggested_actions=["Specify job to update", "Add as new job", "Show all jobs"],
                            conversation_id=conversation_id,
                        )
                    elif len(matches) == 1:
                        job = matches[0]
                        updated = await self.supabase_service.update_job_status(job_id=job["id"], status=new_status, user_id=str(user_message.user_id))
                        if updated:
                            response = await self.openai_service.generate_friendly_status_updated(
                                job_title=updated['job_title'],
                                company_name=updated['company_name'],
                                status=updated['status'],
                                user_message=user_message.message,
                                conversation_context=recent_context,
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="status_updated",
                                intent=intent,
                                confidence=confidence,
                                job_id=updated.get("id"),
                                suggested_actions=["View all jobs", "Add notes"],
                                conversation_id=conversation_id,
                            )
                        else:
                            response = await self.openai_service.generate_dynamic_response(
                                "job_update_failed",
                                {
                                    "job_title": job.get("job_title"),
                                    "company_name": job.get("company_name"),
                                    "action": "status update"
                                },
                                user_message.message,
                                recent_context
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="error",
                                intent=intent,
                                confidence=confidence,
                                suggested_actions=["Try again", "View all jobs"],
                                conversation_id=conversation_id,
                            )
                    else:
                        # Smart logic: if user mentioned specific company and all matches are from that company, 
                        # update the most recent one automatically
                        companies = set(match.get("company_name", "").lower() for match in matches)
                        user_mentioned_company = extraction.company_name and extraction.company_name.lower() in user_message.message.lower()
                        
                        if len(companies) == 1 and user_mentioned_company:
                            # All matches are from the same company the user mentioned - update the most recent one
                            most_recent_job = matches[0]  # Already sorted by date_added DESC
                            
                            # Notify user about what we're about to do
                            job_description = f"{most_recent_job['job_title']} at {most_recent_job['company_name']}"
                            logger.info(f"Auto-updating {job_description} to {new_status.value} for user {user_message.user_id}")
                            
                            updated = await self.supabase_service.update_job_status(
                                job_id=most_recent_job["id"],
                                status=new_status,
                                user_id=str(user_message.user_id),
                            )
                            if updated:
                                # Generate response that acknowledges the update
                                response = await self.openai_service.generate_dynamic_response(
                                    "status_updated_with_confirmation",
                                    {
                                        "job_title": updated['job_title'],
                                        "company_name": updated['company_name'],
                                        "old_status": most_recent_job.get('status', 'unknown'),
                                        "new_status": updated['status'],
                                        "action": "automatically updated your most recent application",
                                        "user_tone": user_message.message
                                    },
                                    user_message.message,
                                    recent_context
                                )
                                agent_response = AgentResponse(
                                    response=response,
                                    action_taken="status_updated",
                                    intent=intent,
                                    confidence=confidence,
                                    job_id=updated.get("id"),
                                    suggested_actions=["View all jobs", "Add notes"],
                                    conversation_id=conversation_id,
                                )
                            else:
                                response = await self.openai_service.generate_dynamic_response(
                                    "job_update_failed",
                                    {
                                        "job_title": most_recent_job.get("job_title"),
                                        "company_name": most_recent_job.get("company_name"),
                                        "action": "status update"
                                    },
                                    user_message.message,
                                    recent_context
                                )
                                agent_response = AgentResponse(
                                    response=response,
                                    action_taken="error",
                                    intent=intent,
                                    confidence=confidence,
                                    suggested_actions=["Try again", "View all jobs"],
                                    conversation_id=conversation_id,
                                )
                        else:
                            # Use smarter clarification that analyzes context
                            response = await self.openai_service.generate_smart_job_clarification(
                                user_message.message, 
                                matches, 
                                recent_context
                            )
                            # Persist a pending selection map in conversation metadata
                            try:
                                if conversation_id:
                                    metadata = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                    metadata["pending_job_selection"] = {
                                        "type": "status_update",
                                        "candidates": [
                                            {"index": i+1, "id": j["id"], "job_title": j["job_title"], "company_name": j["company_name"]}
                                            for i, j in enumerate(matches)
                                        ],
                                        "new_status": new_status.value if new_status else None,
                                    }
                                    await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                            except Exception as e:
                                logger.warning(f"Failed to persist pending_job_selection: {e}")
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="clarification_needed",
                                intent=intent,
                                confidence=confidence,
                                requires_clarification=True,
                                clarification_prompt="Reply with the number",
                                suggested_actions=["List jobs", "Filter by company"],
                                conversation_id=conversation_id,
                            )
            elif intent == IntentType.JOB_DELETE:
                # Handle job deletion requests
                extraction = await self.openai_service.extract_job_details(user_message.message)
                
                # Check if they want to delete by specific criteria (status, company, or both)
                if extraction.status or extraction.company_name:
                    # Build search parameters
                    search_params = {"user_id": str(user_message.user_id)}
                    if extraction.status:
                        search_params["status_filter"] = extraction.status.value
                    if extraction.company_name:
                        search_params["company_name"] = extraction.company_name
                    
                    jobs_to_delete = await self.supabase_service.search_jobs(**search_params)
                    
                    if not jobs_to_delete:
                        response = await self.openai_service.generate_dynamic_response(
                            "no_jobs_to_delete",
                            {
                                "status_filter": extraction.status.value if extraction.status else None,
                                "company_filter": extraction.company_name,
                                "action": "delete jobs with specified criteria"
                            },
                            user_message.message,
                            recent_context
                        )
                        agent_response = AgentResponse(
                            response=response,
                            action_taken="information_provided",
                            intent=intent,
                            confidence=confidence,
                            conversation_id=conversation_id,
                        )
                    else:
                        # Ask for confirmation before deleting
                        job_list = "\n".join([f"• {j['job_title']} at {j['company_name']}" for j in jobs_to_delete])
                        response = await self.openai_service.generate_dynamic_response(
                            "delete_confirmation",
                            {
                                "jobs_to_delete": jobs_to_delete,
                                "job_count": len(jobs_to_delete),
                                "status_filter": extraction.status.value if extraction.status else None,
                                "company_filter": extraction.company_name,
                                "job_list": job_list
                            },
                            user_message.message,
                            recent_context
                        )
                        
                        # Store pending deletion in metadata
                        try:
                            if conversation_id:
                                metadata = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                metadata["pending_deletion"] = {
                                    "type": "by_criteria",
                                    "status": extraction.status.value if extraction.status else None,
                                    "company": extraction.company_name,
                                    "job_ids": [j["id"] for j in jobs_to_delete],
                                    "job_titles": [f"{j['job_title']} at {j['company_name']}" for j in jobs_to_delete]
                                }
                                await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                        except Exception as e:
                            logger.warning(f"Failed to store pending deletion: {e}")
                        
                        agent_response = AgentResponse(
                            response=response,
                            action_taken="clarification_needed",
                            intent=intent,
                            confidence=confidence,
                            requires_clarification=True,
                            clarification_prompt="Reply 'yes' to confirm deletion or 'cancel' to keep them",
                            suggested_actions=["Confirm deletion", "Cancel", "Show jobs first"],
                            conversation_id=conversation_id,
                        )
                else:
                    # Generic deletion request - ask for clarification
                    response = await self.openai_service.generate_dynamic_response(
                        "delete_clarification_needed",
                        {
                            "user_request": user_message.message
                        },
                        user_message.message,
                        recent_context
                    )
                    agent_response = AgentResponse(
                        response=response,
                        action_taken="clarification_needed",
                        intent=intent,
                        confidence=confidence,
                        requires_clarification=True,
                        clarification_prompt="Specify which jobs to delete (e.g., 'rejected jobs', 'Google applications')",
                        suggested_actions=["Delete by status", "Delete by company", "Show all jobs"],
                        conversation_id=conversation_id,
                    )
            elif intent == IntentType.JOB_SEARCH:
                # Special command-like intents: "withdraw all jobs" / "update all ..." should not be treated as search
                lower_msg = user_message.message.lower()
                if any(kw in lower_msg for kw in ["withdraw all", "reject all", "update all", "set all to"]):
                    response = await self.openai_service.generate_dynamic_response(
                        "bulk_updates_unsupported",
                        {
                            "user_intent": lower_msg,
                            "suggestion": "be more specific about which job"
                        },
                        user_message.message,
                        recent_context
                    )
                    agent_response = AgentResponse(
                        response=response,
                        action_taken="information_provided",
                        intent=IntentType.UNKNOWN,
                        confidence=confidence,
                        conversation_id=conversation_id,
                    )
                else:
                # Try to extract optional filters
                    extraction = await self.openai_service.extract_job_details(user_message.message)
                    if extraction.company_name or extraction.job_title:
                        jobs = await self.supabase_service.search_jobs(
                            user_id=str(user_message.user_id),
                            company_name=extraction.company_name,
                            job_title=extraction.job_title,
                            limit=10,
                        )
                    else:
                        # Default: show the last 3 applications
                        jobs = await self.supabase_service.get_user_jobs(user_id=str(user_message.user_id), limit=3)

                    if not jobs:
                        response = await self.openai_service.generate_dynamic_response(
                            "no_jobs_found",
                            {
                                "action_attempted": "job search",
                                "search_filters": {
                                    "company": extraction.company_name,
                                    "title": extraction.job_title
                                }
                            },
                            user_message.message,
                            recent_context
                        )
                    else:
                        friendly_jobs = [
                            {
                                "job_title": j.get("job_title"),
                                "company_name": j.get("company_name"),
                                "status": j.get("status"),
                                "job_link": j.get("job_link"),
                            }
                            for j in jobs[:10]
                        ]
                        if extraction.company_name or extraction.job_title:
                            # Create a personalized header for filtered results
                            if extraction.company_name and extraction.job_title:
                                header = f"Here are your {extraction.job_title} positions at {extraction.company_name}:"
                            elif extraction.company_name:
                                header = f"Here are your applications at {extraction.company_name}:"
                            elif extraction.job_title:
                                header = f"Here are your {extraction.job_title} applications:"
                            else:
                                header = "Here are the matching jobs:"
                            tip = "Want to see all your jobs? Just ask 'show all my jobs'"
                        else:
                            header = "Here are your last 3 applications:"
                            tip = None
                        response = await self.openai_service.generate_friendly_job_list(
                            jobs=friendly_jobs,
                            header=header,
                            footer_tip=tip,
                            user_message=user_message.message,
                            conversation_context=recent_context,
                        )

                    agent_response = AgentResponse(
                        response=response,
                        action_taken="job_search",
                        intent=intent,
                        confidence=confidence,
                        suggested_actions=["Update status", "Add new job", "View stats"],
                        conversation_id=conversation_id,
                    )
            else:
                # First, see if this message suggests a status update even if intent wasn't classified
                extraction2 = await self.openai_service.extract_job_details(user_message.message)
                if extraction2.status and (extraction2.company_name or extraction2.job_title):
                    # Try to resolve a status update using extracted fields
                    matches = await self.supabase_service.search_jobs(
                        user_id=str(user_message.user_id),
                        company_name=extraction2.company_name,
                        job_title=extraction2.job_title,
                        limit=10,
                    )
                    if len(matches) == 1:
                        job = matches[0]
                        new_status2 = extraction2.status or JobStatus.APPLIED
                        updated = await self.supabase_service.update_job_status(job_id=job["id"], status=new_status2, user_id=str(user_message.user_id))
                        if updated:
                            response = await self.openai_service.generate_friendly_status_updated(
                                job_title=updated['job_title'],
                                company_name=updated['company_name'],
                                status=updated['status'],
                                user_message=user_message.message,
                                conversation_context=recent_context,
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="status_updated",
                                intent=IntentType.STATUS_UPDATE,
                                confidence=max(confidence, 0.9),
                                job_id=updated.get("id"),
                                suggested_actions=["View all jobs", "Add notes"],
                                conversation_id=conversation_id,
                            )
                    elif len(matches) > 1:
                        # Ask for a number selection
                        listing = "\n".join([
                            f"{i+1}. {j['job_title']} at {j['company_name']}" for i, j in enumerate(matches)
                        ])
                        response = (
                            "I found multiple matching jobs. Which one should I update?\n" + listing +
                            "\nReply with the number (e.g., 1 or 2). You’ve got this ✨"
                        )
                        try:
                            if conversation_id:
                                metadata = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                metadata["pending_job_selection"] = {
                                    "type": "status_update",
                                    "candidates": [
                                        {"index": i+1, "id": j["id"], "job_title": j["job_title"], "company_name": j["company_name"]}
                                        for i, j in enumerate(matches)
                                    ],
                                    "new_status": (extraction2.status.value if isinstance(extraction2.status, JobStatus) else str(extraction2.status)),
                                }
                                await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                        except Exception as e:
                            logger.warning(f"Failed to persist pending_job_selection (unknown->status): {e}")
                        agent_response = AgentResponse(
                            response=response,
                            action_taken="clarification_needed",
                            intent=IntentType.STATUS_UPDATE,
                            confidence=confidence,
                            requires_clarification=True,
                            clarification_prompt="Reply with the number",
                            suggested_actions=["List jobs", "Filter by company"],
                            conversation_id=conversation_id,
                        )
                
                # If not a status update, see if the message itself carries enough info to create a job
                if 'agent_response' not in locals():
                    # Merge partial details with any pending_new_job in conversation metadata
                    pending_meta = None
                    if conversation_id:
                        try:
                            meta_for_merge = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                            pending_meta = meta_for_merge.get("pending_new_job") if meta_for_merge else None
                        except Exception:
                            pending_meta = None

                    merged_title = extraction2.job_title or (pending_meta.get("job_title") if pending_meta else None)
                    merged_company = extraction2.company_name or (pending_meta.get("company_name") if pending_meta else None)
                    merged_link = extraction2.job_link or (pending_meta.get("job_link") if pending_meta else None)
                    merged_desc = extraction2.job_description or (pending_meta.get("job_description") if pending_meta else None)
                    merged_status = extraction2.status or (JobStatus(pending_meta.get("status")) if pending_meta and pending_meta.get("status") else JobStatus.APPLIED)

                    if merged_title and merged_company:
                        # Create immediately using merged details
                        merged_extraction = JobExtraction(
                            job_title=merged_title,
                            company_name=merged_company,
                            job_link=merged_link,
                            job_description=merged_desc,
                            status=merged_status,
                            confidence=0.9,
                        )
                        created_response = await self._maybe_create_job_from_extraction(user_message, merged_extraction)
                        if created_response:
                            # Clear pending if any
                            if conversation_id and pending_meta is not None:
                                try:
                                    meta_for_merge["pending_new_job"] = None
                                    await self.supabase_service.update_conversation_metadata(conversation_id, meta_for_merge)
                                except Exception:
                                    pass
                            agent_response = created_response
                    else:
                        # Still missing a required field; update pending and ask for exactly what's missing
                        missing_fields = []
                        if not merged_title:
                            missing_fields.append("job_title")
                        if not merged_company:
                            missing_fields.append("company_name")
                        # Save/merge pending
                        try:
                            if conversation_id:
                                meta_to_save = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                                meta_to_save["pending_new_job"] = {
                                    "job_title": merged_title,
                                    "company_name": merged_company,
                                    "job_link": merged_link,
                                    "job_description": merged_desc,
                                    "status": merged_status.value,
                                }
                                await self.supabase_service.update_conversation_metadata(conversation_id, meta_to_save)
                        except Exception:
                            pass
                        # Ask for only the missing ones, in a friendly tone
                        friendly_prompt = await self.openai_service.generate_friendly_missing_fields(
                            known_fields={
                                "job_title": merged_title,
                                "company_name": merged_company,
                                "job_link": merged_link,
                                "status": merged_status.value,
                            },
                            missing_fields=missing_fields,
                        )
                        agent_response = AgentResponse(
                            response=friendly_prompt,
                            action_taken="clarification_needed",
                            intent=IntentType.NEW_JOB,
                            confidence=max(confidence, 0.9),
                            requires_clarification=True,
                            clarification_prompt=f"Provide: {', '.join(missing_fields)}",
                            suggested_actions=["Add job details", "Set status", "Skip for now"],
                            conversation_id=conversation_id,
                        )
                else:
                    # Detect lightweight confirmations to act on pending context
                    normalized = user_message.message.strip().lower()
                    is_confirmation = normalized in {"yes", "y", "correct", "you are correct", "that's right", "that is correct", "ok", "okay", "sure", "do it"}
                    is_bulk_confirmation = normalized in {"yes all", "confirm all", "apply to all", "do it all", "yes, all", "yes update all", "yes withdraw all"}

                    if conversation_id:
                        metadata = await self.supabase_service.get_conversation_metadata(conversation_id)
                    else:
                        metadata = None
                    pending = (metadata or {}).get("pending_new_job") if metadata else None
                    pending_bulk = (metadata or {}).get("pending_bulk_update") if metadata else None
                    pending_deletion = (metadata or {}).get("pending_deletion") if metadata else None

                    # Handle bulk confirmation
                    if is_bulk_confirmation and pending_bulk and pending_bulk.get("status"):
                        status_str = pending_bulk.get("status")
                        try:
                            status_obj = JobStatus(status_str)
                        except Exception:
                            status_obj = JobStatus.APPLIED
                        jobs_to_update = await self.supabase_service.get_user_jobs(user_id=str(user_message.user_id))
                        if not jobs_to_update:
                            response = await self.openai_service.generate_friendly_error(
                                error_type="no_jobs_to_update",
                                context={"action": "update"}
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="information_provided",
                                intent=IntentType.STATUS_UPDATE,
                                confidence=max(confidence, 0.9),
                                conversation_id=conversation_id,
                            )
                        else:
                            success = 0
                            for j in jobs_to_update:
                                updated = await self.supabase_service.update_job_status(job_id=j["id"], status=status_obj, user_id=str(user_message.user_id))
                                if updated:
                                    success += 1
                            # Clear pending
                            try:
                                metadata["pending_bulk_update"] = None
                                await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                            except Exception:
                                pass
                            response = (
                                f"Updated {success} application(s) to '{status_obj.value}'. "
                                "You’re making steady progress — keep going ✨"
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="status_updated",
                                intent=IntentType.STATUS_UPDATE,
                                confidence=max(confidence, 0.9),
                                conversation_id=conversation_id,
                            )
                    elif is_confirmation and pending_deletion:
                        # Handle deletion confirmation
                        if pending_deletion.get("type") == "by_status":
                            status_filter = pending_deletion.get("status")
                            count_deleted, deleted_titles = await self.supabase_service.delete_jobs_by_status(
                                user_id=str(user_message.user_id),
                                status=status_filter
                            )
                            
                            # Clear pending deletion
                            try:
                                metadata["pending_deletion"] = None
                                await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                            except Exception:
                                pass
                            
                            if count_deleted > 0:
                                response = await self.openai_service.generate_dynamic_response(
                                    "deletion_completed",
                                    {
                                        "count_deleted": count_deleted,
                                        "status_filter": status_filter,
                                        "deleted_jobs": deleted_titles,
                                        "action": "bulk deletion by status"
                                    },
                                    user_message.message,
                                    recent_context
                                )
                                agent_response = AgentResponse(
                                    response=response,
                                    action_taken="jobs_deleted",
                                    intent=IntentType.JOB_DELETE,
                                    confidence=max(confidence, 0.9),
                                    conversation_id=conversation_id,
                                    suggested_actions=["Show remaining jobs", "Add new job"],
                                )
                            else:
                                response = await self.openai_service.generate_dynamic_response(
                                    "deletion_failed",
                                    {
                                        "status_filter": status_filter,
                                        "reason": "no jobs found or deletion failed"
                                    },
                                    user_message.message,
                                    recent_context
                                )
                                agent_response = AgentResponse(
                                    response=response,
                                    action_taken="error",
                                    intent=IntentType.JOB_DELETE,
                                    confidence=confidence,
                                    conversation_id=conversation_id,
                                )
                    elif is_confirmation and pending and (pending.get("job_title") and pending.get("company_name")):
                        try:
                            job_data = JobCreate(
                                user_id=str(user_message.user_id),
                                job_title=pending.get("job_title"),
                                company_name=pending.get("company_name"),
                                job_link=pending.get("job_link"),
                                job_description=pending.get("job_description"),
                                status=JobStatus(pending.get("status")) if pending.get("status") else JobStatus.APPLIED,
                            )
                            created = await self.supabase_service.create_job(job_data, str(user_message.user_id))
                            if created:
                                # Clear pending
                                metadata["pending_new_job"] = None
                                await self.supabase_service.update_conversation_metadata(conversation_id, metadata)
                                response = await self.openai_service.generate_friendly_job_created(
                                    job_title=job_data.job_title,
                                    company_name=job_data.company_name,
                                    status=job_data.status.value,
                                    job_link=job_data.job_link,
                                    conversation_context=recent_context,
                                    user_message=user_message.message
                                )
                                agent_response = AgentResponse(
                                    response=response,
                                    action_taken="job_created",
                                    intent=IntentType.NEW_JOB,
                                    confidence=max(confidence, 0.9),
                                    job_id=created.get("id"),
                                    suggested_actions=["Update status", "View all jobs", "Add notes"],
                                    conversation_id=conversation_id,
                                )
                            else:
                                response = await self.openai_service.generate_dynamic_response(
                                    "job_creation_failed",
                                    {
                                        "job_title": pending.get("job_title"),
                                        "company_name": pending.get("company_name"),
                                        "action": "creating job from confirmation"
                                    },
                                    user_message.message,
                                    recent_context
                                )
                                agent_response = AgentResponse(
                                    response=response,
                                    action_taken="error",
                                    intent=IntentType.NEW_JOB,
                                    confidence=confidence,
                                    conversation_id=conversation_id,
                                )
                        except Exception as e:
                            logger.error(f"Failed to create job from pending context: {e}")
                            response = await self.openai_service.generate_dynamic_response(
                                "job_creation_failed",
                                {
                                    "error_details": "system error during creation",
                                    "action": "creating job from pending context"
                                },
                                user_message.message,
                                recent_context
                            )
                            agent_response = AgentResponse(
                                response=response,
                                action_taken="error",
                                intent=IntentType.NEW_JOB,
                                confidence=confidence,
                                conversation_id=conversation_id,
                            )
                    else:
                        response = await self.openai_service.generate_response(
                            user_message.message,
                            context=build_context(
                                "You are JobTrackAI. Be helpful and concise. Only request fields that exist in the jobs schema."
                            )
                        )
            
            # If we haven't already constructed a structured AgentResponse, do it now
            if 'agent_response' not in locals():
                # Ensure we never return an empty response
                if not isinstance(response, str) or not response.strip():
                    try:
                        response = await self.openai_service.generate_friendly_fallback(intent)
                    except Exception:
                        response = await self._friendly_fallback_response(intent, user_message.message, recent_context)
                # For generic LLM responses, do not infer actions from text. Keep it informational.
                action_taken = "information_provided"
                agent_response = AgentResponse(
                    response=response,
                    action_taken=action_taken,
                    intent=intent,
                    confidence=confidence,
                    suggested_actions=self._get_suggested_actions(response),
                    conversation_id=conversation_id
                )

            # Persist assistant response with metadata
            if conversation_id:
                await self.supabase_service.add_message(
                    conversation_id=conversation_id,
                    user_id=str(user_message.user_id),
                    role="assistant",
                    content=agent_response.response,
                    tool_calls={
                        "intent": agent_response.intent.value,
                        "confidence": agent_response.confidence,
                        "action_taken": agent_response.action_taken,
                        "job_id": agent_response.job_id
                    }
                )

            return agent_response
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return AgentResponse(
                response="I'm experiencing technical difficulties. Please try again.",
                action_taken="error",
                intent=IntentType.UNKNOWN,
                confidence=0.0
            )
    
    def _contains_job_link(self, message: str) -> bool:
        """Check if message contains a URL (treated as potential job link)"""
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message)
        return bool(urls)
    
    async def _handle_job_link_message(self, user_message: UserMessage) -> AgentResponse:
        """Handle messages that contain job links by extracting details and auto-creating when possible"""
        try:
            # Extract URLs from message
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, user_message.message)
            
            if not urls:
                return AgentResponse(
                    response="I found a link but couldn't extract it properly. Please try again.",
                    action_taken="error",
                    intent=IntentType.NEW_JOB,
                    confidence=0.0
                )
            
            # Check if it's a LinkedIn job link
            is_linkedin_job = any('linkedin.com/jobs/view' in url.lower() for url in urls)
            
            # Attempt structured extraction
            extraction = await self.openai_service.extract_job_details(user_message.message)
            
            # For LinkedIn job links, make a more aggressive attempt to get job details
            if is_linkedin_job:
                linkedin_url = next((url for url in urls if 'linkedin.com/jobs/view' in url.lower()), None)
                if linkedin_url and (not extraction.job_title or not extraction.company_name):
                    # Try to scrape the LinkedIn job page for title and company
                    logger.info(f"Attempting to fetch details from LinkedIn job URL: {linkedin_url}")
                    title, company = await self._fetch_linkedin_job_details(linkedin_url)
                    
                    if title and not extraction.job_title:
                        extraction.job_title = title
                        logger.info(f"Extracted job title from LinkedIn: {title}")
                    
                    if company and not extraction.company_name:
                        extraction.company_name = company
                        logger.info(f"Extracted company from LinkedIn: {company}")
                    
                    # Store the URL as job_link if not already set
                    if not extraction.job_link:
                        extraction.job_link = linkedin_url
            
            # General fallback for any job link
            if not extraction.job_title:
                # Try page title from the first URL
                title = await self._fetch_page_title(urls[0])
                if title:
                    extraction.job_title = title
                    logger.info(f"Using page title as job title: {title}")
            
            # Set default status if not provided
            if not extraction.status:
                extraction.status = JobStatus.APPLIED
            
            # Get conversation history to provide context
            conversation_history = []
            conversation_id = user_message.conversation_id
            if conversation_id:
                try:
                    # Get the last few messages for context
                    messages = await self.supabase_service.get_conversation_messages(conversation_id, limit=5)
                    if messages:
                        conversation_history = [
                            {"role": "user" if msg.get("is_user") else "assistant", "content": msg.get("content", "")}
                            for msg in messages
                        ]
                except Exception as e:
                    logger.warning(f"Failed to get conversation history: {e}")
            
            # Use OpenAI to check for field completeness using conversation context
            extraction_dict = {
                "job_title": extraction.job_title,
                "company_name": extraction.company_name,
                "job_link": extraction.job_link or urls[0],
                "job_description": extraction.job_description,
                "status": extraction.status.value if extraction.status else JobStatus.APPLIED.value
            }
            
            # Check if we can infer missing fields from context
            completeness_check = await self.openai_service.check_job_details_completeness(
                extraction=extraction_dict,
                conversation_history=conversation_history,
                job_link=urls[0]
            )
            
            # Update extraction with any fields inferred from context
            complete_fields = completeness_check.get("complete_fields", {})
            if complete_fields:
                if complete_fields.get("job_title") and not extraction.job_title:
                    extraction.job_title = complete_fields["job_title"]
                    logger.info(f"Inferred job title from context: {extraction.job_title}")
                
                if complete_fields.get("company_name") and not extraction.company_name:
                    extraction.company_name = complete_fields["company_name"]
                    logger.info(f"Inferred company name from context: {extraction.company_name}")
                
                if complete_fields.get("job_description") and not extraction.job_description:
                    extraction.job_description = complete_fields["job_description"]
            
            # Get missing fields from the completeness check
            missing = completeness_check.get("missing_fields", [])
            if not missing:
                # Double-check required fields
                if not extraction.job_title:
                    missing.append("job_title")
                if not extraction.company_name:
                    missing.append("company_name")

            # If we have both required fields, auto-create
            if extraction.job_title and extraction.company_name:
                job_data = JobCreate(
                    user_id=str(user_message.user_id),
                    job_title=extraction.job_title,
                    company_name=extraction.company_name,
                    job_link=extraction.job_link or urls[0],
                    job_description=extraction.job_description,
                    status=extraction.status or JobStatus.APPLIED,
                )
                created = await self.supabase_service.create_job(job_data, str(user_message.user_id))
                if created:
                    friendly = await self.openai_service.generate_friendly_job_created(
                        job_title=job_data.job_title,
                        company_name=job_data.company_name,
                        status=job_data.status.value,
                        job_link=job_data.job_link,
                    )
                    return AgentResponse(
                        response=friendly,
                        action_taken="job_created",
                        intent=IntentType.NEW_JOB,
                        confidence=0.95,
                        job_id=created.get("id"),
                        requires_clarification=False,
                        suggested_actions=["Update status", "View all jobs", "Add notes"],
                    )

            # Otherwise, prepare details for response
            details = []
            details.append(f"Link: {urls[0]}")
            if extraction.company_name:
                details.append(f"Company: {extraction.company_name}")
            if extraction.job_title:
                details.append(f"Job Title: {extraction.job_title}")
            status_val = (extraction.status or JobStatus.APPLIED).value
            details.append(f"Status: {status_val}")
            
            # Save pending job info to conversation metadata
            try:
                if conversation_id:
                    meta = await self.supabase_service.get_conversation_metadata(conversation_id) or {}
                    meta["pending_new_job"] = {
                        "job_title": extraction.job_title,
                        "company_name": extraction.company_name,
                        "job_link": urls[0],
                        "job_description": extraction.job_description,
                        "status": status_val
                    }
                    await self.supabase_service.update_conversation_metadata(conversation_id, meta)
            except Exception as e:
                logger.warning(f"Failed to save pending job info: {e}")

            # Generate a friendly response asking for missing fields
            if missing:
                friendly_prompt = await self.openai_service.generate_friendly_missing_fields(
                    known_fields={
                        "job_title": extraction.job_title,
                        "company_name": extraction.company_name,
                        "job_link": urls[0],
                        "status": status_val,
                    },
                    missing_fields=missing,
                )
                
                return AgentResponse(
                    response=friendly_prompt,
                    action_taken="job_link_found",
                    intent=IntentType.NEW_JOB,
                    confidence=0.9,
                    requires_clarification=True,
                    clarification_prompt=f"Provide: {', '.join(missing)}",
                    suggested_actions=["Add job details", "Set status", "Skip for now"],
                )
            else:
                return AgentResponse(
                    response=("I found a job link! 🎯\n" + "\n".join(details)),
                    action_taken="job_link_found",
                    intent=IntentType.NEW_JOB,
                    confidence=0.9,
                    requires_clarification=False,
                    suggested_actions=["Update status", "View all jobs"],
                )
            
        except Exception as e:
            logger.error(f"Error handling job link: {str(e)}")
            return AgentResponse(
                response="I encountered an issue while processing the job link. Please try again.",
                action_taken="error",
                intent=IntentType.NEW_JOB,
                confidence=0.0
            )
    
    
    
    def _determine_action(self, response: str) -> str:
        """Determine what action was taken based on the response"""
        response_lower = response.lower()
        
        if "added" in response_lower or "created" in response_lower:
            return "job_created"
        elif "updated" in response_lower or "changed" in response_lower:
            return "status_updated"
        elif "found" in response_lower or "showing" in response_lower:
            return "job_search"
        elif "clarification" in response_lower or "confirm" in response_lower:
            return "clarification_needed"
        else:
            return "information_provided"
    
    def _classify_intent_simple(self, message: str) -> tuple[IntentType, float]:
        """Simple rule-based intent classification"""
        message_lower = message.lower()
        
        # Check for deletion indicators
        if any(phrase in message_lower for phrase in [
            "delete", "remove", "clear", "get rid of", "clean up"
        ]) and any(phrase in message_lower for phrase in [
            "job", "application", "rejected", "offer"
        ]):
            return IntentType.JOB_DELETE, 0.9
        
        # Check for new job indicators
        if any(phrase in message_lower for phrase in [
            "applied to", "new job", "found a job", "job link", "linkedin.com", "indeed.com"
        ]):
            return IntentType.NEW_JOB, 0.9
        
        # Check for status update indicators
        if any(phrase in message_lower for phrase in [
            "update status", "status to", "got rejected", "rejected me", "turned me down", "passed on me", "didn't make it", "no longer moving forward",
            "interview", "phone screen", "onsite", "offer", "withdrawn"
        ]):
            return IntentType.STATUS_UPDATE, 0.9
        # Bare number reply (selection) often follows a clarification list
        if re.fullmatch(r"\s*(\d{1,2})\s*", message_lower):
            return IntentType.STATUS_UPDATE, 0.8
        
        # Check for job search indicators
        if any(phrase in message_lower for phrase in [
            "show me", "what jobs", "my applications", "all my jobs", "recent applications",
            "my jobs", "show my jobs", "list jobs", "show jobs", "view jobs", "show applications", "list applications"
        ]):
            return IntentType.JOB_SEARCH, 0.9
        
        # Check for ambiguous messages
        if any(phrase in message_lower for phrase in [
            "help", "what can you do", "how does this work"
        ]):
            return IntentType.AMBIGUOUS, 0.8
        
        return IntentType.UNKNOWN, 0.5

    def _is_job_search_query(self, message: str) -> bool:
        """Heuristic to detect search queries like "show my current job applications"."""
        text = message.lower().strip()
        keywords = [
            "show my jobs",
            "show my applications",
            "current applications",
            "current job applications",
            "list my jobs",
            "view my jobs",
            "show jobs",
            "my jobs",
            "my applications",
        ]
        return any(k in text for k in keywords)
    
    def _get_suggested_actions(self, response: str) -> list[str]:
        """Get suggested next actions based on the response"""
        response_lower = response.lower()
        
        if "new job" in response_lower:
            return ["Add job details", "Share job link", "Set status"]
        elif "status" in response_lower:
            return ["Update status", "View all jobs", "Add notes"]
        elif "search" in response_lower:
            return ["Filter by company", "Filter by status", "View recent"]
        else:
            return ["Add new job", "Update status", "Search jobs"]

    async def _friendly_fallback_response(self, intent: IntentType, user_message: str = "", context: str = "") -> str:
        """Return a dynamically generated, friendly, supportive fallback message."""
        try:
            return await self.openai_service.generate_dynamic_response(
                "fallback_response",
                {
                    "intent": intent.value,
                    "user_message": user_message,
                    "context": context
                },
                user_message,
                context
            )
        except Exception as e:
            logger.error(f"Failed to generate dynamic fallback: {e}")
            # Emergency hard fallback only if OpenAI completely fails
            return await self.openai_service.generate_dynamic_fallback("emergency_fallback", {"intent": intent.value})

    def _extract_selection_index(self, message: str) -> Optional[int]:
        """Extract a selection index from text like '2', '2nd one', 'the 1st', etc."""
        text = (message or "").strip().lower()
        # direct number
        m = re.fullmatch(r"\s*(\d{1,2})\s*", text)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        # ordinal forms
        m2 = re.search(r"\b(\d{1,2})(st|nd|rd|th)\b", text)
        if m2:
            try:
                return int(m2.group(1))
            except Exception:
                return None
        # spelled variants
        mapping = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
        for k, v in mapping.items():
            if k in text:
                return v
        return None

    def _is_bulk_all_command(self, message: str) -> bool:
        text = message.lower()
        return any(kw in text for kw in [
            "withdraw all", "reject all", "update all", "set all to", "mark all", "change all"
        ])

    async def _fetch_page_title(self, url: str) -> Optional[str]:
        """Fetch page title from URL as a lightweight hint for job_title."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0, headers={
                "User-Agent": "JobTrackAI/1.0 (+https://example.com)"
            }) as client:
                r = await client.get(url, follow_redirects=True)
                if r.status_code >= 200 and r.status_code < 300:
                    m = re.search(r"<title[^>]*>([\s\S]*?)</title>", r.text, re.IGNORECASE)
                    if m:
                        title = html_module.unescape(m.group(1)).strip()
                        # Clean common suffixes
                        title = re.sub(r"\s*[|\-–—]\s*LinkedIn.*$", "", title, flags=re.IGNORECASE)
                        title = re.sub(r"\s*-\s*Jobs.*$", "", title, flags=re.IGNORECASE)
                        return title[:120]
        except Exception:
            return None
            
    async def _fetch_linkedin_job_details(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Extract job title and company name from LinkedIn job URL
        
        Returns a tuple of (job_title, company_name)
        """
        try:
            import httpx
            # Use the same httpx client as _fetch_page_title for consistency
            async with httpx.AsyncClient(timeout=8.0, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }) as client:
                r = await client.get(url, follow_redirects=True)
                if r.status_code >= 200 and r.status_code < 300:
                    # Try to extract job title and company from the page content
                    job_title = None
                    company_name = None
                    
                    # First extract the title
                    title_match = re.search(r"<title[^>]*>([\s\S]*?)</title>", r.text, re.IGNORECASE)
                    if title_match:
                        page_title = html_module.unescape(title_match.group(1)).strip()
                        
                        # LinkedIn titles often follow patterns like:
                        # "Job Title at Company | LinkedIn"
                        # "Job Title at Company: Location | LinkedIn"
                        if ' at ' in page_title and '|' in page_title:
                            title_part = page_title.split('|')[0].strip()
                            parts = title_part.split(' at ', 1)
                            if len(parts) >= 2:
                                job_title = parts[0].strip()
                                # Company might have location after a colon
                                company_part = parts[1].split(':', 1)[0].strip()
                                company_name = company_part
                    
                    # Try to extract from meta tags which often contain structured data
                    og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', r.text, re.IGNORECASE)
                    if og_title and not job_title:
                        og_title_text = html_module.unescape(og_title.group(1)).strip()
                        if ' at ' in og_title_text:
                            parts = og_title_text.split(' at ', 1)
                            job_title = parts[0].strip()
                            if len(parts) > 1 and not company_name:
                                company_name = parts[1].split(':', 1)[0].strip()
                    
                    # Try to extract from JSON-LD which LinkedIn often uses
                    json_ld_match = re.search(r'<script type="application/ld\+json">([\s\S]*?)</script>', r.text, re.IGNORECASE)
                    if json_ld_match:
                        try:
                            json_data = json.loads(json_ld_match.group(1))
                            if not job_title and 'title' in json_data:
                                job_title = json_data['title']
                            if not company_name and 'hiringOrganization' in json_data:
                                if isinstance(json_data['hiringOrganization'], dict) and 'name' in json_data['hiringOrganization']:
                                    company_name = json_data['hiringOrganization']['name']
                        except json.JSONDecodeError:
                            pass
                    
                    # Clean up extracted data
                    if job_title:
                        job_title = job_title.replace('\n', ' ').strip()
                        job_title = re.sub(r'\s+', ' ', job_title)
                    
                    if company_name:
                        company_name = company_name.replace('\n', ' ').strip()
                        company_name = re.sub(r'\s+', ' ', company_name)
                        # Remove "LinkedIn" if it's part of the company name erroneously
                        company_name = re.sub(r'\s*LinkedIn\s*$', '', company_name, flags=re.IGNORECASE)
                    
                    logger.info(f"LinkedIn extraction results - Title: {job_title}, Company: {company_name}")
                    return job_title, company_name
                    
        except Exception as e:
            logger.warning(f"Error fetching LinkedIn job details: {str(e)}")
        
        return None, None

    def _missing_required_fields(self, extraction: JobExtraction) -> list[str]:
        missing: list[str] = []
        if not extraction.job_title:
            missing.append("job_title")
        if not extraction.company_name:
            missing.append("company_name")
        return missing

    async def _maybe_create_job_from_extraction(self, user_message: UserMessage, extraction: JobExtraction) -> Optional[AgentResponse]:
        """If title and company present, create job immediately and respond."""
        try:
            if extraction.job_title and extraction.company_name:
                job_data = JobCreate(
                    user_id=str(user_message.user_id),
                    job_title=extraction.job_title,
                    company_name=extraction.company_name,
                    job_link=extraction.job_link,
                    job_description=extraction.job_description,
                    status=extraction.status or JobStatus.APPLIED,
                )
                created = await self.supabase_service.create_job(job_data, str(user_message.user_id))
                if created:
                    # Get conversation context for personalized response
                    conversation_id = getattr(user_message, 'conversation_id', None)
                    recent_context = ""
                    if conversation_id:
                        try:
                            recent_msgs = await self.supabase_service.get_recent_messages(conversation_id, limit=5)
                            if recent_msgs:
                                formatted = []
                                for m in recent_msgs:
                                    prefix = "User" if m.get("role") == "user" else "Assistant"
                                    formatted.append(f"{prefix}: {m.get('content','')}")
                                recent_context = "\n".join(formatted)
                        except Exception:
                            pass
                    
                    # Generate dynamic, personalized job creation response
                    response = await self.openai_service.generate_friendly_job_created(
                        job_title=job_data.job_title,
                        company_name=job_data.company_name,
                        status=job_data.status.value,
                        job_link=job_data.job_link,
                        conversation_context=recent_context,
                        user_message=user_message.message
                    )
                    
                    return AgentResponse(
                        response=response,
                        action_taken="job_created",
                        intent=IntentType.NEW_JOB,
                        confidence=0.95,
                        job_id=created.get("id"),
                        requires_clarification=False,
                        suggested_actions=["Update status", "View all jobs", "Add notes"],
                    )
        except Exception as e:
            logger.error(f"Auto-create job failed: {e}")
        return None
