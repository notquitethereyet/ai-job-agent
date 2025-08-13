"""
OpenAI service for JobTrackAI
Handles AI model interactions and intent classification
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple, List

from openai import OpenAI
from openai.types.chat import ChatCompletion

from app.models.job import JobStatus
from app.models.agent import IntentType, JobExtraction

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for OpenAI API interactions"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Default model for cost/speed balance
        
    async def classify_intent(self, message: str) -> tuple[IntentType, float]:
        """
        Classify the intent of a user message
        Returns: (intent_type, confidence_score)
        """
        try:
            system_prompt = """
            You are an AI assistant that classifies user messages about tracking job applications.
            
            Output ONLY one line in this exact format:
            INTENT_TYPE|CONFIDENCE
            
            INTENT_TYPE ∈ {NEW_JOB, STATUS_UPDATE, JOB_SEARCH, AMBIGUOUS, UNKNOWN}
            
            Hints:
            - NEW_JOB if text but not limited to contains phrases like: "i applied", "applied to", "new job", or includes a job link.
            - STATUS_UPDATE for phrases but not limited to phrases like: "rejected", "rejected me", "they passed", "turned me down", "didn't make it", "no longer moving forward", "got an interview", "phone screen", "onsite", "offer", "withdrew", "update status", "status update", "status change", "status changed", "status updated", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status updated to", "status
            - JOB_SEARCH but not limited to contains phrases like "show my jobs", "my applications", "list jobs", "what jobs".
            - If both NEW_JOB and JOB_SEARCH cues appear, prefer NEW_JOB when a link is present; otherwise JOB_SEARCH.
            - Confidence ∈ [0,1].
            """
            # override with a concise, graceful prompt
            system_prompt = """
            You classify user messages about tracking job applications.
            
            Output ONLY one line in this exact format:
            INTENT_TYPE|CONFIDENCE
            
            INTENT_TYPE ∈ {NEW_JOB, STATUS_UPDATE, JOB_SEARCH, JOB_DELETE, AMBIGUOUS, UNKNOWN}
            
            Short definitions:
            - NEW_JOB: user adds a new application (e.g., "I applied", shares a job link)
            - STATUS_UPDATE: user reports a change or outcome (e.g., rejected/declined/passed, interview/phone screen/onsite, offer, withdrew)
            - JOB_SEARCH: user wants to view/filter existing applications (e.g., "show my jobs", "applications at Google")
            - JOB_DELETE: user wants to remove/delete job applications (e.g., "delete my rejected jobs", "remove this application", "clear my rejections")
            - AMBIGUOUS: unclear or needs clarification
            - UNKNOWN: unrelated to job tracking
            
            Hints:
            - If text mentions "applied" or includes a link → NEW_JOB
            - Outcome/stage words → STATUS_UPDATE
            - "show/list/view my jobs/applications" → JOB_SEARCH
            - "delete/remove/clear" + jobs/applications → JOB_DELETE
            - If both NEW_JOB and JOB_SEARCH cues appear, prefer NEW_JOB when a link is present; otherwise JOB_SEARCH
            
            Confidence ∈ [0,1].
            """
            
            response = await self._get_chat_completion(
                system_prompt=system_prompt,
                user_message=message
            )
            
            # Parse response
            logger.info(f"Raw AI response: {response}")
            
            if response and "|" in response:
                intent_str, confidence_str = response.split("|")
                intent_str = intent_str.strip().upper()
                confidence_str = confidence_str.strip()
                
                logger.info(f"Parsed intent: '{intent_str}', confidence: '{confidence_str}'")
                
                # Try to match the intent
                try:
                    # First try exact match
                    intent = IntentType(intent_str)
                except ValueError:
                    # Try removing underscores
                    intent_str_clean = intent_str.replace('_', '')
                    try:
                        intent = IntentType(intent_str_clean)
                    except ValueError:
                        # Try common variations
                        intent_mapping = {
                            'NEWJOB': IntentType.NEW_JOB,
                            'STATUSUPDATE': IntentType.STATUS_UPDATE,
                            'JOBSEARCH': IntentType.JOB_SEARCH,
                            'AMBIGUOUS': IntentType.AMBIGUOUS,
                            'UNKNOWN': IntentType.UNKNOWN
                        }
                        intent = intent_mapping.get(intent_str, IntentType.UNKNOWN)
                
                try:
                    confidence = float(confidence_str)
                    return intent, confidence
                except ValueError:
                    logger.warning(f"Invalid confidence score: {confidence_str}")
                    return intent, 0.8  # Default confidence
            else:
                logger.warning(f"Unexpected response format: {response}")
                return IntentType.UNKNOWN, 0.0
                
        except Exception as e:
            logger.error(f"Error classifying intent: {str(e)}")
            return IntentType.UNKNOWN, 0.0

    async def detect_unsafe_request(self, message: str) -> tuple[bool, float, str]:
        """Detect sensitive/malicious requests (internal ids, secrets, credentials, env vars, etc.).
        Returns: (is_unsafe, confidence, reason)
        """
        try:
            system_prompt = """
            You are a safety classifier for a job-tracking assistant.
            Decide if the user's message requests sensitive or unsafe information (e.g., internal IDs, environment variables, secrets, API keys, passwords, credentials, tokens, service keys, or confidential system data).
            Output EXACTLY one line:
            LABEL|CONFIDENCE|REASON
            where LABEL ∈ {SAFE, UNSAFE} and CONFIDENCE ∈ [0,1]. Keep REASON short.
            """
            res = await self._get_chat_completion(system_prompt=system_prompt, user_message=message)
            if res and "|" in res:
                parts = res.split("|", 2)
                if len(parts) == 3:
                    label = parts[0].strip().upper()
                    try:
                        conf = float(parts[1].strip())
                    except Exception:
                        conf = 0.8
                    reason = parts[2].strip()
                    return (label == "UNSAFE", conf, reason)
            return (False, 0.0, "")
        except Exception as e:
            logger.error(f"Safety detection error: {e}")
            return (False, 0.0, "")

    async def detect_job_related(self, message: str) -> tuple[bool, float]:
        """Detect whether the message is about job applications/tracking.
        Returns: (is_job_related, confidence)
        """
        try:
            system_prompt = """
            You classify whether a user message is about job applications/tracking.
            Output EXACTLY one line: LABEL|CONFIDENCE
            LABEL ∈ {JOB, OTHER}; CONFIDENCE ∈ [0,1].
            JOB covers adding applications, links to jobs, status changes, viewing/searching applications, 
            interview anxiety, job search stress, confidence issues related to applications.
            OTHER covers completely unrelated topics (weather, sports, random chat).
            """
            res = await self._get_chat_completion(system_prompt=system_prompt, user_message=message)
            if res and "|" in res:
                lbl, conf = res.split("|", 1)
                lbl = lbl.strip().upper()
                try:
                    return (lbl == "JOB", float(conf.strip()))
                except Exception:
                    return (lbl == "JOB", 0.8)
            return (False, 0.0)
        except Exception as e:
            logger.error(f"Job-related detection error: {e}")
            return (False, 0.0)

    async def detect_emotional_state(self, message: str) -> tuple[str, float]:
        """Detect user's emotional state for appropriate response tone.
        Returns: (emotion, confidence) where emotion ∈ {confident, anxious, frustrated, disappointed, excited}
        """
        try:
            system_prompt = """
            You analyze the emotional tone of a user's message about job applications.
            Output EXACTLY one line: EMOTION|CONFIDENCE
            EMOTION ∈ {confident, anxious, frustrated, disappointed, excited, neutral}
            CONFIDENCE ∈ [0,1]
            
            - confident: positive, determined, ready to take action
            - anxious: worried about interviews, uncertain, nervous
            - frustrated: annoyed with process, AI not understanding, system issues  
            - disappointed: sad about rejections, feeling down
            - excited: happy about opportunities, interviews, offers
            - neutral: matter-of-fact, just sharing information
            """
            res = await self._get_chat_completion(system_prompt=system_prompt, user_message=message)
            if res and "|" in res:
                emotion, conf = res.split("|", 1)
                emotion = emotion.strip().lower()
                try:
                    return (emotion, float(conf.strip()))
                except Exception:
                    return (emotion, 0.8)
            return ("neutral", 0.5)
        except Exception as e:
            logger.error(f"Emotional state detection error: {e}")
            return ("neutral", 0.5)

    async def generate_emotional_support_response(self, message: str, emotion: str) -> str:
        """Generate emotionally appropriate response based on user's state."""
        try:
            system_prompt = f"""
            You are JobTrackAI, an emotionally intelligent assistant. The user is feeling {emotion}.
            
            Respond appropriately:
            - anxious: Offer reassurance, practical interview tips, confidence building
            - frustrated: Validate feelings, be more helpful, acknowledge pain points
            - disappointed: Be compassionate, encouraging, focus on resilience 
            - excited: Match energy, celebrate with them
            - confident: Support momentum, offer next steps
            - neutral: Be helpful and supportive as usual
            
            Keep it genuine, 1-2 sentences max, and always offer actionable next steps.
            """
            res = await self._get_chat_completion(system_prompt=system_prompt, user_message=f"User said: {message}")
            if res:
                return res
        except Exception as e:
            logger.error(f"Emotional support response error: {e}")
        
        # Fallback based on emotion
        if emotion == "anxious":
            return "Interview nerves are totally normal! Want me to help you prep some talking points or practice questions? 💪"
        elif emotion == "frustrated":
            return "I hear you - job searching can be rough. Let me be more helpful - what do you need right now? ✊"
        elif emotion == "disappointed":
            return "Rejections suck, but they don't define your worth. Every 'no' gets you closer to the right 'yes' ❤️"
        else:
            return "I'm here to help make this easier. What can I do for you? ✨"

    async def generate_smalltalk_redirect(self, message: str) -> str:
        """Friendly, brief small-talk response that redirects to job-tracking actions."""
        try:
            system_prompt = """
            You are JobTrackAI, a friendly and extremely witty assistant. The user sent small talk/off-topic or casual content.
            Respond with funny or kind sentences depending on the user's message, then redirect to job-tracking options.
            Try to keep it to 2 sentences.
            """
            user_msg = f"Small talk from user: {message}\nCreate a friendly redirect."
            res = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if res:
                return res
        except Exception as e:
            logger.error(f"Smalltalk redirect error: {e}")
        return "Got it! I’m here to help with your job search — want to add a job, update a status, or see your applications? ✨"
    
    async def extract_job_details(self, message: str) -> JobExtraction:
        """
        Extract job details from user message, including normalized status
        """
        try:
            system_prompt = """
            You are an AI assistant that extracts job information from user messages.
            
            Extract the following information if present:
            - job_title: The job role/title
            - company_name: The company name (be smart about casual mentions like "my google jobs", "amazon applications", "meta positions")
            - job_link: URL to the job posting
            - job_description: Brief description of the job
            - status: One of [applied, interview, offer, rejected, withdrawn]
            
            Rules:
            - If the user says they "applied" or shares a job link without a status, infer status = "applied".
            - Map variations like "interviewing", "phone screen", "onsite" to "interview".
            - Only output the five allowed status values when you include status.
            - For search queries like "show my google jobs", "my amazon applications", extract the company name
            - Company names should be properly capitalized (google -> Google, amazon -> Amazon, etc.)
            - If information is not present, set to null.
            
            Examples:
            - "show me my google jobs" -> company_name: "Google"
            - "my amazon applications" -> company_name: "Amazon"  
            - "meta positions" -> company_name: "Meta"
            - "apple interviews" -> company_name: "Apple"
            - "got rejected by google for the machine learning job" -> company_name: "Google", job_title: "Machine Learning Engineer", status: "rejected"
            - "machine learning job" -> job_title: "Machine Learning Engineer"
            - "ML Engineer" -> job_title: "Machine Learning Engineer"
            
            Respond with a JSON object containing only the extracted fields.
            """
            
            response = await self._get_chat_completion(
                system_prompt=system_prompt,
                user_message=message
            )
            
            # Parse JSON response
            try:
                if response:
                    # Try to extract JSON from response
                    if '{' in response and '}' in response:
                        start = response.find('{')
                        end = response.rfind('}') + 1
                        json_str = response[start:end]
                        data = json.loads(json_str)
                        status_value = self._normalize_status(data.get('status'), original_message=message)
                        return JobExtraction(
                            job_title=(data.get('job_title') or None),
                            company_name=(data.get('company_name') or None),
                            job_link=(data.get('job_link') or None),
                            job_description=(data.get('job_description') or None),
                            status=status_value,
                            confidence=0.8  # Default confidence for successful extraction
                        )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse JSON response: {e}")
            
            # Fallback to placeholder
            return JobExtraction(
                job_title=None,
                company_name=None,
                job_link=None,
                job_description=None,
                status=self._normalize_status(None, original_message=message),
                confidence=0.0
            )
            
        except Exception as e:
            logger.error(f"Error extracting job details: {str(e)}")
            return JobExtraction(confidence=0.0)
    
    async def generate_response(self, message: str, context: str = "") -> str:
        """
        Generate a natural language response to user message
        """
        try:
            system_prompt = """
            You are JobTrackAI, a warm and encouraging assistant who helps users track job applications.
            Tone: friendly, concise, supportive, never cheesy or overbearing.
            Never expose internal IDs. Only mention fields in the jobs schema.
            When listing jobs for the same company, use a numbered order.
            Ask for clarification only for required fields that are still missing.
            """
            
            user_prompt = f"Context: {context}\n\nUser message: {message}"
            
            response = await self._get_chat_completion(
                system_prompt=system_prompt,
                user_message=user_prompt
            )
            
            return response or await self.generate_dynamic_fallback("generic_failure", {"context": context})
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return await self.generate_dynamic_fallback("technical_error", {"error": str(e)})

    async def generate_friendly_job_list(
        self,
        jobs: list[dict],
        header: str,
        footer_tip: str | None = None,
        user_message: str = "",
        conversation_context: str = "",
    ) -> str:
        """Use the LLM to produce a cheerful, supportive summary of jobs without exposing IDs.

        jobs: list of dicts with keys: job_title, company_name, status, job_link (optional)
        """
        try:
            system_prompt = """
            You are JobTrackAI, a warm and emotionally intelligent assistant. Create a personalized summary of job applications.
            
            Requirements:
            - Do NOT invent or alter facts. Use only provided fields.
            - Do NOT include internal IDs.
            - Show each item as: "<index>. <job_title> — <company_name> [<status>]" and on the next indented line include "Link: <job_link>" if present.
            - Be supportive and encouraging, but adapt tone to user's request and context
            - If user asked for specific company/role, acknowledge their focused search
            - End with a brief encouraging line that feels natural to the conversation
            - Keep it conversational, not robotic
            """

            content = {
                "header": header,
                "jobs": jobs,
                "footer_tip": footer_tip,
                "user_message": user_message,
                "conversation_context": conversation_context,
            }
            user_prompt = (
                "Create a personalized job list response based on the user's request and context.\n" +
                json.dumps(content, ensure_ascii=False)
            )

            response = await self._get_chat_completion(
                system_prompt=system_prompt,
                user_message=user_prompt,
            )
            if response:
                return response
        except Exception as e:
            logger.error(f"Error generating friendly job list: {e}")
        # Dynamic fallback formatting
        return await self.generate_dynamic_fallback("job_list_fallback", {
            "jobs": jobs,
            "header": header,
            "footer_tip": footer_tip
        })

    async def generate_friendly_job_created(
        self,
        job_title: str,
        company_name: str,
        status: str,
        job_link: Optional[str] = None,
        conversation_context: Optional[str] = None,
        user_message: Optional[str] = None,
    ) -> str:
        """Friendly confirmation message after creating a job."""
        try:
            system_prompt = """
            You are JobTrackAI, a warm, emotionally intelligent assistant who genuinely celebrates job application milestones.
            
            Create a personalized confirmation for this newly added job application.
            
            Guidelines:
            - Be genuinely excited and encouraging (but not over the top)
            - Make it feel personal to their specific situation
            - Use natural, conversational language (avoid robotic templates)
            - Include 1 emoji max, and only if it feels natural
            - If they seem excited, match their energy
            - If they're just matter-of-fact, be supportive but not overly cheerful
            - Reference specific details about the role/company when relevant
            - Keep it concise but meaningful
            - NO internal IDs or technical details
            
            Remember: This is a real person working toward their career goals. Make them feel heard and supported.
            """
            
            payload = {
                "job_title": job_title,
                "company_name": company_name,
                "status": status,
                "job_link": job_link,
                "user_message": user_message,
                "conversation_context": conversation_context,
            }
            
            user_msg = f"""
            Generate a personalized job creation confirmation:
            
            Job Details: {json.dumps(payload)}
            
            Make this feel like a real conversation, not a template. Consider the user's tone and context.
            """
            
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error generating friendly job created: {e}")
        return await self.generate_dynamic_fallback("job_created_fallback", {
            "job_title": job_title,
            "company_name": company_name,
            "status": status,
            "job_link": job_link
        })

    async def generate_friendly_status_updated(
        self,
        job_title: str,
        company_name: str,
        status: str,
        user_message: str = "",
        conversation_context: str = "",
    ) -> str:
        """Friendly confirmation after updating status; tone guided by status via OpenAI."""
        try:
            system_prompt = """
            You are JobTrackAI, a warm and emotionally intelligent assistant.
            Create a personalized status update confirmation that feels natural and supportive.
            
            Tone guidelines based on status:
            - rejected: Compassionate, validating, gently encouraging - acknowledge the disappointment but remind them of their worth
            - withdrawn: Affirming - celebrate their decision-making and self-awareness
            - interview: Excited and supportive - offer encouragement and confidence building
            - offer: Celebratory - this is huge news, be genuinely excited for them
            - applied: Supportive momentum - acknowledge their proactive effort
            
            Key principles:
            - Match the user's tone and energy from their message
            - Be genuine and conversational, not robotic
            - Keep it concise but meaningful (1-2 sentences)
            - Use 1 emoji max, and only if it feels natural
            - Reference specific details when relevant
            - No internal IDs or technical details
            """
            
            payload = {
                "job_title": job_title,
                "company_name": company_name,
                "status": status,
                "user_message": user_message,
                "conversation_context": conversation_context,
            }
            user_msg = f"""
            Create a personalized status update confirmation:
            
            Status Update: {json.dumps(payload)}
            
            Make this feel like a supportive friend responding, not a system notification.
            """
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error in friendly status updated: {e}")
        return await self.generate_dynamic_fallback("status_updated_fallback", {
            "job_title": job_title,
            "company_name": company_name,
            "status": status
        })

    async def generate_friendly_fallback(self, intent: IntentType) -> str:
        """LLM-generated fallback message tailored to the inferred intent."""
        try:
            system_prompt = """
            You are JobTrackAI, a friendly assistant. The system needs a fallback reply.
            Produce a concise, supportive, human message (1 emoji max) tailored to the intent provided.
            - For JOB_SEARCH: invite the user to view or filter their applications.
            - For STATUS_UPDATE: ask for the missing piece (job or status) as a single, clear question.
            - For NEW_JOB: ask for the missing required fields (job_title and/or company_name) succinctly.
            - For JOB_DELETE: ask what they want to delete (by status, company, etc.).
            - For AMBIGUOUS/UNKNOWN: suggest a couple of helpful next actions.
            Do not expose internal IDs.
            """
            payload = {"intent": intent.value}
            user_msg = "Generate a single friendly fallback for this intent:\n" + json.dumps(payload)
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error generating friendly fallback: {e}")
        # Minimal safe fallback  
        return await self.generate_dynamic_fallback("friendly_fallback_emergency", {"intent": intent.value})

    async def generate_friendly_refusal(self, reason: str) -> str:
        """Kind yet firm refusal message for sensitive or malicious requests (via OpenAI)."""
        try:
            system_prompt = """
            You are JobTrackAI, a gen-z assistant. The user asked for something sensitive or unsafe.
            Respond with something witty and funny e.g: "Get your money up, not your funny up".
            Do NOT expose internal IDs, environment variables, secrets, or any confidential data.
            Try to keep it to 2-3 sentences.
            """
            payload = {"reason": reason}
            user_msg = "Refuse this unsafe request and suggest safe next steps:\n" + json.dumps(payload)
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error generating friendly refusal: {e}")
        return await self.generate_dynamic_fallback("refusal_fallback", {"reason": reason})

    async def generate_friendly_missing_fields(
        self,
        known_fields: Dict[str, Any],
        missing_fields: list[str],
    ) -> str:
        """Ask for missing required fields in a warm, concise tone, restating what we already have.

        known_fields keys can include: job_title, company_name, status, job_link, job_description
        missing_fields: list of field names to request (e.g., ["job_title"]).
        """
        try:
            system_prompt = """
            You are JobTrackAI, a friendly assistant. Ask for the missing required field(s) in a warm, concise way.
            Rules:
            - Restate any known fields succinctly.
            - Ask ONLY for the specific missing fields by name.
            - Keep tone supportive, 1 emoji max, no fluff.
            - Do not expose internal IDs.
            - Use short lines, no long paragraphs.
            """
            payload = {
                "known": known_fields,
                "missing": missing_fields,
            }
            user_message = "Craft a single friendly prompt asking for the exact missing fields, given this context:\n" + json.dumps(payload)
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_message)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error generating friendly missing fields prompt: {e}")
        # Fallback
        known_lines = []
        if known_fields.get("company_name"):
            known_lines.append(f"Company: {known_fields['company_name']}")
        if known_fields.get("job_title"):
            known_lines.append(f"Job Title: {known_fields['job_title']}")
        if known_fields.get("status"):
            known_lines.append(f"Status: {known_fields['status']}")
        if known_fields.get("job_link"):
            known_lines.append(f"Link: {known_fields['job_link']}")
        prefix = ("\n".join(known_lines) + "\n\n") if known_lines else ""
        return await self.generate_dynamic_fallback("missing_fields_fallback", {
            "known_fields": known_fields,
            "missing_fields": missing_fields
        })
    
    async def _get_chat_completion(
        self, 
        system_prompt: str, 
        user_message: str,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Get chat completion from OpenAI API
        
        Args:
            system_prompt: The system prompt to guide the model
            user_message: The user message to respond to
            response_format: Optional format specification, e.g. {"type": "json_object"}
        """
        try:
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 500,
                "temperature": 0.1
            }
            
            # Add response_format if specified
            if response_format:
                params["response_format"] = response_format
                
            response: ChatCompletion = self.client.chat.completions.create(**params)
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return None

    async def generate_friendly_error(self, error_type: str, context: Dict[str, Any] = None) -> str:
        """Generate a friendly, witty error message with personality."""
        try:
            system_prompt = """
            You are JobTrackAI, a friendly assistant with a touch of humor. The user encountered an error.
            Generate a friendly, supportive error message with these rules:
            - Keep it concise (1-2 sentences)
            - Add a touch of personality and wit (1 emoji max)
            - Be encouraging and suggest a simple next step
            - Do NOT expose technical details or internal IDs
            - Match tone to error severity (light for minor issues, more serious for data problems)
            """
            
            payload = {
                "error_type": error_type,
                "context": context or {}
            }
            user_msg = "Create a friendly error message for this situation:\n" + json.dumps(payload)
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error generating friendly error: {e}")
        
        # Dynamic fallback responses
        return await self.generate_dynamic_fallback(f"error_{error_type}", context or {})
    
    async def check_job_details_completeness(self, extraction: Dict[str, Any], conversation_history: List[Dict[str, str]], job_link: Optional[str] = None) -> Dict[str, Any]:
        """Use OpenAI to determine if all required job details are present based on conversation context.
        
        Args:
            extraction: Dictionary containing extracted job details
            conversation_history: List of conversation messages with 'role' and 'content' keys
            job_link: Optional job link URL
            
        Returns:
            Dictionary with:
                - complete_fields: Dict of complete fields with their values
                - missing_fields: List of field names still missing
                - confidence: Float indicating confidence in the completeness check
        """
        try:
            system_prompt = """
            You are JobTrackAI, a job application tracking assistant. Your task is to analyze a conversation 
            and determine if all required job details are present for creating a job entry.
            
            Required fields are:
            - job_title: The title of the job position
            - company_name: The name of the company offering the job
            
            Optional fields are:
            - job_link: URL to the job posting
            - job_description: Brief description of the job
            - status: Current application status (default is APPLIED if a job link is present)
            
            Analyze the conversation history and the current extraction to:
            1. Determine if the required fields are complete or can be inferred from context
            2. For any missing required fields, check if they can be found in the conversation history
            3. Return a JSON with complete fields, missing fields, and confidence score
            
            Rules:
            - If a short reply (1-3 words) follows a request for a specific field, treat it as that field
            - Company names are often short (e.g., "Google", "Microsoft", "Apple")
            - Job titles can vary in length but are typically descriptive
            - If a job link is present but other fields are missing, try to infer them from context
            - Be confident (0.9+) only when fields are explicitly mentioned or clearly inferable
            """
            
            # Prepare the payload with extraction and conversation history
            payload = {
                "extraction": extraction,
                "conversation_history": conversation_history[-5:],  # Last 5 messages for context
                "job_link": job_link
            }
            
            user_message = "Analyze this conversation and extraction to determine if all required job details are present:\n" + json.dumps(payload)
            
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_message, response_format={"type": "json_object"})
            
            if not response:
                return {
                    "complete_fields": extraction,
                    "missing_fields": ["job_title", "company_name"] if not extraction.get("job_title") or not extraction.get("company_name") else [],
                    "confidence": 0.5
                }
            
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {response}")
                return {
                    "complete_fields": extraction,
                    "missing_fields": ["job_title", "company_name"] if not extraction.get("job_title") or not extraction.get("company_name") else [],
                    "confidence": 0.5
                }
                
        except Exception as e:
            logger.error(f"Error in check_job_details_completeness: {e}")
            return {
                "complete_fields": extraction,
                "missing_fields": ["job_title", "company_name"] if not extraction.get("job_title") or not extraction.get("company_name") else [],
                "confidence": 0.5
            }

    async def generate_interview_prep_response(self, job_info: dict) -> str:
        """Generate interview preparation advice based on job details."""
        try:
            system_prompt = """
            You are JobTrackAI, a supportive career coach. Generate practical interview prep advice.
            
            Provide 3-4 actionable tips specific to the role/company if available, or general interview advice.
            Keep it encouraging and practical. Include:
            - Research suggestions
            - Common questions to prep
            - One confidence-building tip
            
            Format as short bullet points, max 4 lines total.
            """
            user_msg = f"Help user prep for interview at {job_info.get('company_name', 'this company')} for {job_info.get('job_title', 'this role')}"
            res = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if res:
                return res
        except Exception as e:
            logger.error(f"Interview prep response error: {e}")
        
        return await self.generate_dynamic_fallback("interview_prep_fallback", job_info)

    async def generate_smart_job_clarification(self, message: str, matches: list, context: str = "") -> str:
        """Generate intelligent clarification that tries to understand user intent first."""
        try:
            system_prompt = """
            You are JobTrackAI, an intelligent assistant. The user mentioned a job update but there are multiple matches.
            
            Analyze their message to see if you can determine which job they mean without asking:
            - Look for company names, job titles, or other identifying details
            - Consider recent context if provided
            - If truly ambiguous, ask in a friendly way with a short numbered list
            
            Be smart about context - don't ask if it's obvious which one they mean.
            Always be personalized and natural - no robotic responses.
            """
            
            matches_summary = [f"{i+1}. {j['job_title']} at {j['company_name']}" for i, j in enumerate(matches)]
            user_msg = f"Message: {message}\nMatches: {matches_summary}\nContext: {context}"
            
            res = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if res:
                return res
        except Exception as e:
            logger.error(f"Smart clarification error: {e}")
        
        # Emergency fallback only if OpenAI fails
        return await self.generate_dynamic_fallback("job_clarification", {
            "message": message,
            "match_count": len(matches),
            "matches": matches
        })

    async def generate_dynamic_response(self, response_type: str, context: dict, user_message: str = "", conversation_context: str = "") -> str:
        """Universal dynamic response generator for any scenario - NO MORE HARDCODED STRINGS!"""
        try:
            # Base personality for all responses
            base_personality = """
            You are JobTrackAI, a warm, emotionally intelligent, and witty assistant who helps with job applications.
            
            Core personality traits:
            - Genuinely supportive and encouraging
            - Naturally conversational (not robotic)
            - Adapts tone to user's emotional state
            - Uses gentle humor when appropriate
            - Never exposes internal system details
            - Personalizes responses based on context
            - Keeps responses concise but meaningful
            """
            
            # Response type specific prompts
            prompts = {
                "status_missing": f"""
                {base_personality}
                
                The user wants to update a job status but didn't specify which status.
                Context: {context}
                
                Ask them for the new status in a friendly, natural way. The options are:
                applied, interview, offer, rejected, withdrawn
                
                Make it feel like a conversation, not a form.
                """,
                
                "no_jobs_found": f"""
                {base_personality}
                
                The user has no job applications yet.
                Context: {context}
                
                Encourage them to add their first job application in a supportive way.
                Make them feel like they're starting an exciting journey.
                """,
                
                "job_creation_failed": f"""
                {base_personality}
                
                We couldn't create a job entry for technical reasons.
                Context: {context}
                
                Acknowledge the issue gracefully and suggest trying again.
                Be reassuring - it's not their fault.
                """,
                
                "job_not_found": f"""
                {base_personality}
                
                The user tried to update a job that doesn't exist in their list.
                Context: {context}
                
                Gently let them know we couldn't find that job, and offer to help them add it or find the right one.
                """,
                
                "job_not_found_with_clarification": f"""
                {base_personality}
                
                The user tried to update a job that doesn't exist in their list.
                Context: {context}
                
                Be helpful and transparent:
                1. Explain what we searched for specifically
                2. Show them what jobs they DO have (if any)
                3. Ask clear questions: "Did you mean one of these jobs?" or "Should I add this as a new job?"
                4. Be empathetic to their situation
                """,
                
                "bulk_confirmation": f"""
                {base_personality}
                
                The user wants to update all their jobs to the same status.
                Context: {context}
                
                Ask for confirmation in a way that shows the impact.
                Make sure they really want to do this.
                """,
                
                "generic_error": f"""
                {base_personality}
                
                Something went wrong but we don't want to expose technical details.
                Context: {context}
                
                Acknowledge the hiccup gracefully and suggest next steps.
                Stay positive and helpful.
                """,
                
                "status_updated_with_confirmation": f"""
                {base_personality}
                
                A job status was automatically updated in the database.
                Context: {context}
                
                IMPORTANT: You must clearly tell the user what was changed:
                - Which specific job was updated
                - What the status changed from and to
                - Acknowledge their emotional state appropriately
                
                Be transparent about the action taken while remaining supportive.
                """,
                
                "no_jobs_to_delete": f"""
                {base_personality}
                
                The user wants to delete jobs by status but no jobs exist with that status.
                Context: {context}
                
                Gently let them know there are no jobs to delete with that status.
                Offer to show what jobs they do have or help with other actions.
                """,
                
                "delete_confirmation": f"""
                {base_personality}
                
                The user wants to delete multiple jobs and we need confirmation.
                Context: {context}
                
                IMPORTANT: Show them exactly what will be deleted and ask for clear confirmation.
                - List the specific jobs that will be deleted
                - Make it clear this action cannot be undone
                - Ask for explicit "yes" or "no" confirmation
                Be supportive but make sure they understand the consequences.
                """,
                
                "delete_clarification_needed": f"""
                {base_personality}
                
                The user wants to delete jobs but wasn't specific about which ones.
                Context: {context}
                
                Help them clarify:
                - Ask what criteria they want to use (status, company, etc.)
                - Give examples like "rejected jobs" or "applications at Google"
                - Be helpful and supportive
                """,
                
                "deletion_completed": f"""
                {base_personality}
                
                Jobs have been successfully deleted from the database.
                Context: {context}
                
                Confirm what was deleted and be supportive:
                - Tell them exactly how many jobs were deleted
                - Acknowledge this helps clean up their application list
                - Offer next steps like viewing remaining jobs
                """,
                
                "deletion_failed": f"""
                {base_personality}
                
                Job deletion failed for some reason.
                Context: {context}
                
                Acknowledge the issue and offer alternatives:
                - Explain that the deletion couldn't be completed
                - Suggest trying again or checking what jobs they have
                - Be helpful and reassuring
                """
            }
            
            system_prompt = prompts.get(response_type, f"""
            {base_personality}
            
            Generate a response for: {response_type}
            Context: {context}
            
            Be natural, helpful, and personalized to the situation.
            """)
            
            user_prompt = f"""
            User message: {user_message}
            Conversation context: {conversation_context}
            Situation: {response_type}
            Details: {json.dumps(context)}
            
            Generate a personalized, natural response for this specific situation.
            """
            
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_prompt)
            if response:
                return response
                
        except Exception as e:
            logger.error(f"Error generating dynamic response for {response_type}: {e}")
        
        # Final emergency fallback
        return await self.generate_dynamic_fallback(response_type, context)

    async def generate_dynamic_fallback(self, situation: str, context: dict) -> str:
        """Emergency fallback generator when primary response generation fails."""
        try:
            system_prompt = f"""
            You are JobTrackAI. Generate a brief, helpful response for this situation: {situation}
            Context: {context}
            
            Keep it simple, warm, and actionable. No robotic language.
            """
            
            response = await self._get_chat_completion(
                system_prompt=system_prompt,
                user_message=f"Generate emergency response for: {situation}"
            )
            if response:
                return response
        except Exception:
            pass
        
        # Absolute last resort
        return "Something went wrong, but I'm here to help! What would you like to do with your job applications? ✨"

    def _normalize_status(self, status_str: Optional[str], *, original_message: Optional[str] = None) -> Optional[JobStatus]:
        """Map arbitrary status strings (and message hints) to allowed JobStatus values."""
        try:
            text = (status_str or "").strip().lower()
            msg = (original_message or "").lower()

            # Strong hints from message
            if any(k in msg for k in [" i applied", "i've applied", "applied to", "application submitted", "submit my application", "submitted my application"]):
                return JobStatus.APPLIED

            mapping = {
                "applied": JobStatus.APPLIED,
                "apply": JobStatus.APPLIED,
                "application": JobStatus.APPLIED,
                "interview": JobStatus.INTERVIEW,
                "interviewing": JobStatus.INTERVIEW,
                "phone screen": JobStatus.INTERVIEW,
                "screen": JobStatus.INTERVIEW,
                "onsite": JobStatus.INTERVIEW,
                "offer": JobStatus.OFFER,
                "offered": JobStatus.OFFER,
                "rejected": JobStatus.REJECTED,
                "reject": JobStatus.REJECTED,
                "declined by them": JobStatus.REJECTED,
                "decline": JobStatus.REJECTED,
                "withdrawn": JobStatus.WITHDRAWN,
                "withdraw": JobStatus.WITHDRAWN,
                "withdrew": JobStatus.WITHDRAWN,
            }

            # Exact match first
            if text in mapping:
                return mapping[text]

            # Contains matching
            for key, value in mapping.items():
                if key in text:
                    return value

            # Infer applied when a link is present and no contrary status is given
            if original_message and ("http://" in msg or "https://" in msg):
                return JobStatus.APPLIED

            return None
        except Exception:
            return None
