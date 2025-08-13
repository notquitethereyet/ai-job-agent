"""
Agent service for JobTrackAI
Orchestrates AI agent logic and coordinates between services
"""

import logging
import re
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

            # Off-topic/small-talk handling: if not job-related, reply kindly and redirect
            is_job_related, jr_conf = await self.openai_service.detect_job_related(user_message.message)
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

                        response = (
                            "I couldn't create the job entry right now. Please try again in a moment, "
                            "or confirm and I'll retry."
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
                    response = (
                        "What's the new status? Choose one of: applied, interview, offer, rejected, withdrawn."
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
                            response = (
                                "Looks like you don't have any job applications yet, so there's nothing to update. "
                                "Want to add your first one? ✨"
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
                            response = (
                                f"I found {len(all_jobs)} application(s). Do you want me to set them all to '"
                                f"{new_status.value}'? Reply 'yes all' to confirm or 'cancel'."
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
                        # Offer to create a new job record if they intended a new one
                        detail_bits = []
                        if extraction.job_title:
                            detail_bits.append(f"'{extraction.job_title}'")
                        if extraction.company_name:
                            detail_bits.append(f"at {extraction.company_name}")
                        detail = " ".join(detail_bits) if detail_bits else "the specified job"
                        response = (
                            f"I couldn't find {detail} in your list. Do you want to add it first, or specify a different job?"
                        )
                        agent_response = AgentResponse(
                            response=response,
                            action_taken="clarification_needed",
                            intent=intent,
                            confidence=confidence,
                            requires_clarification=True,
                            clarification_prompt="Provide: job_title and company_name to add, or clarify which existing job to update",
                            suggested_actions=["Add new job", "Search jobs"],
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
                            response = await self.openai_service.generate_friendly_error(
                                error_type="job_update_failed",
                                context={"job_title": job.get("job_title"), "company_name": job.get("company_name")}
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
                        # Multiple matches; ask user to choose without exposing IDs
                        listing = "\n".join([
                            f"{i+1}. {j['job_title']} at {j['company_name']}" for i, j in enumerate(matches)
                        ])
                        response = (
                            "I found multiple matching jobs. Which one do you mean?\n" + listing +
                            "\nReply with the number (e.g., 1 or 2). You’ve got this ✨"
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
            elif intent == IntentType.JOB_SEARCH:
                # Special command-like intents: "withdraw all jobs" / "update all ..." should not be treated as search
                lower_msg = user_message.message.lower()
                if any(kw in lower_msg for kw in ["withdraw all", "reject all", "update all", "set all to"]):
                    response = await self.openai_service.generate_friendly_error(
                        error_type="bulk_updates_unsupported",
                        context={"suggestion": "withdraw <title> at <company> or list jobs to pick"}
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
                        response = await self.openai_service.generate_friendly_error(
                            error_type="no_jobs_found",
                            context={"action": "search"}
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
                            header = "Here are the matching jobs:"
                            tip = "Tip: include more of the title or the exact company to narrow further."
                        else:
                            header = "Here are your last 3 applications:"
                            tip = None
                        response = await self.openai_service.generate_friendly_job_list(
                            jobs=friendly_jobs,
                            header=header,
                            footer_tip=tip,
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
                                    job_link=job_data.job_link
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
                                response = await self.openai_service.generate_friendly_error(
                                    error_type="job_creation_failed",
                                    context={"job_title": pending.get("job_title"), "company_name": pending.get("company_name")}
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
                            response = await self.openai_service.generate_friendly_error(
                                error_type="job_creation_failed",
                                context={"error": str(e)}
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
                        response = self._friendly_fallback_response(intent)
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
            
            # Attempt structured extraction
            extraction = await self.openai_service.extract_job_details(user_message.message)
            if not extraction.job_title:
                # Fallback: try page title from the first URL
                title = await self._fetch_page_title(urls[0])
                if title:
                    extraction.job_title = title
            if not extraction.status:
                extraction.status = JobStatus.APPLIED

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

            # Otherwise, ask minimally for missing fields
            missing = []
            if not extraction.job_title:
                missing.append("job_title")
            if not extraction.company_name:
                missing.append("company_name")
            details = []
            details.append(f"Link: {urls[0]}")
            if extraction.company_name:
                details.append(f"Company: {extraction.company_name}")
            if extraction.job_title:
                details.append(f"Job Title: {extraction.job_title}")
            status_val = (extraction.status or JobStatus.APPLIED).value
            details.append(f"Status: {status_val}")

            return AgentResponse(
                response=("I found a job link! 🎯\n" + "\n".join(details) + ("\n\n" if missing else "") +
                          (f"Please provide the missing required field(s): {', '.join(missing)}." if missing else "")),
                action_taken="job_link_found" if missing else "job_created",
                intent=IntentType.NEW_JOB,
                confidence=0.9,
                requires_clarification=bool(missing),
                clarification_prompt=(f"Provide: {', '.join(missing)}" if missing else None),
                suggested_actions=["Add job details", "Set status", "Skip for now"] if missing else ["Update status", "View all jobs"],
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

    def _friendly_fallback_response(self, intent: IntentType) -> str:
        """Return a friendly, supportive fallback message when no response was generated."""
        if intent == IntentType.JOB_SEARCH:
            return "I couldn’t find any applications to show yet. Want to add your first one? You’ve got this ✨"
        if intent == IntentType.STATUS_UPDATE:
            return "Tell me which job to update and the new status (applied/interview/offer/rejected/withdrawn). I’m here to help ✨"
        if intent == IntentType.NEW_JOB:
            return "Let’s add it! Share the job title and company (a link helps too). We’ll set status to ‘applied’ by default ✨"
        return "I didn’t quite catch that. Try ‘show my jobs’ or ‘add <title> at <company>’. You’ve got this ✨"

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
        return None

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
                    return AgentResponse(
                        response=(
                            f"Added '{job_data.job_title}' at {job_data.company_name} with status '{job_data.status.value}'." +
                            (f"\nLink: {job_data.job_link}" if job_data.job_link else "")
                        ),
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
