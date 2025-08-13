"""
OpenAI service for JobTrackAI
Handles AI model interactions and intent classification
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from openai import OpenAI
from openai.types.chat import ChatCompletion
from app.models.agent import IntentType, JobExtraction
from app.models.job import JobStatus

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
            
            INTENT_TYPE ∈ {NEW_JOB, STATUS_UPDATE, JOB_SEARCH, AMBIGUOUS, UNKNOWN}
            
            Short definitions:
            - NEW_JOB: user adds a new application (e.g., "I applied", shares a job link)
            - STATUS_UPDATE: user reports a change or outcome (e.g., rejected/declined/passed, interview/phone screen/onsite, offer, withdrew)
            - JOB_SEARCH: user wants to view/filter existing applications (e.g., "show my jobs", "applications at Google")
            - AMBIGUOUS: unclear or needs clarification
            - UNKNOWN: unrelated to job tracking
            
            Hints:
            - If text mentions "applied" or includes a link → NEW_JOB
            - Outcome/stage words → STATUS_UPDATE
            - "show/list/view my jobs/applications" → JOB_SEARCH
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
            JOB covers adding applications, links to jobs, status changes, viewing/searching applications.
            OTHER covers small talk, insults, random chat, unrelated topics.
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
            - company_name: The company name
            - job_link: URL to the job posting
            - job_description: Brief description of the job
            - status: One of [applied, interview, offer, rejected, withdrawn]
            
            Rules:
            - If the user says they "applied" or shares a job link without a status, infer status = "applied".
            - Map variations like "interviewing", "phone screen", "onsite" to "interview".
            - Only output the five allowed status values when you include status.
            - If information is not present, set to null.
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
            
            return response or "I'm sorry, I couldn't process your request."
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I'm experiencing technical difficulties. Please try again."

    async def generate_friendly_job_list(
        self,
        jobs: list[dict],
        header: str,
        footer_tip: str | None = None,
    ) -> str:
        """Use the LLM to produce a cheerful, supportive summary of jobs without exposing IDs.

        jobs: list of dicts with keys: job_title, company_name, status, job_link (optional)
        """
        try:
            system_prompt = """
            You are JobTrackAI, a friendly assistant. Create a concise, upbeat summary of job applications.
            Requirements:
            - Do NOT invent or alter facts. Use only provided fields.
            - Do NOT include internal IDs.
            - Show each item as: "<index>. <job_title> — <company_name> [<status>]" and on the next indented line include "Link: <job_link>" if present.
            - Keep it supportive and hopeful. End with a short encouraging line”
            - Keep output under ~12 lines when possible.
            """

            content = {
                "header": header,
                "jobs": jobs,
                "footer_tip": footer_tip,
            }
            user_prompt = (
                "Render the provided jobs in the required format and tone.\n" +
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
        # Fallback: simple formatting
        lines = [header]
        for idx, j in enumerate(jobs, start=1):
            title = j.get("job_title", "(untitled)")
            company = j.get("company_name", "(unknown)")
            status = j.get("status", "unknown")
            link = j.get("job_link")
            lines.append(f"{idx}. {title} — {company} [{status}]")
            if link:
                lines.append(f"   Link: {link}")
        if footer_tip:
            lines.append("")
            lines.append(footer_tip)
        # lines.append("\nYou’re doing great — keep going ✨")
        return "\n".join(lines)

    async def generate_friendly_job_created(
        self,
        job_title: str,
        company_name: str,
        status: str,
        job_link: Optional[str] = None,
    ) -> str:
        """Friendly confirmation message after creating a job."""
        try:
            system_prompt = """
            You are JobTrackAI, a warm and encouraging assistant.
            Confirm a newly added job application in a concise, friendly tone (1 emoji max).
            - Format: "Added '<job_title>' at <company_name> with status '<status>'." then optionally include link on next line.
            - End with a brief encouraging nudge.
            - No internal IDs.
            """
            payload = {
                "job_title": job_title,
                "company_name": company_name,
                "status": status,
                "job_link": job_link,
            }
            user_msg = "Create a friendly confirmation for this new job:" + json.dumps(payload)
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error generating friendly job created: {e}")
        base = f"Added '{job_title}' at {company_name} with status '{status}'."
        if job_link:
            base += f"\nLink: {job_link}"
        return base

    async def generate_friendly_status_updated(
        self,
        job_title: str,
        company_name: str,
        status: str,
    ) -> str:
        """Friendly confirmation after updating status; tone guided by status via OpenAI."""
        try:
            system_prompt = """
            You are JobTrackAI, a warm and emotionally intelligent assistant.
            Write a short confirmation for a job application status change with the following rules:
            - Adapt tone to the outcome:
              - rejected: compassionate, validating, gently encouraging (1 emoji max)
              - withdrawn: affirming and positive about choosing fit
              - interview: upbeat and proactive (prep suggestions welcome)
              - offer: celebratory with a nudge toward next steps
              - applied/other: supportive and encouraging
            - Keep it concise (1–2 sentences), no internal IDs, no code quotes.
            - Do NOT invent details.
            """
            payload = {
                "job_title": job_title,
                "company_name": company_name,
                "status": status,
            }
            user_msg = "Create a tone-appropriate confirmation for this status change:\n" + json.dumps(payload)
            response = await self._get_chat_completion(system_prompt=system_prompt, user_message=user_msg)
            if response:
                return response
        except Exception as e:
            logger.error(f"Error in friendly status updated: {e}")
        return f"Updated '{job_title}' at {company_name} to '{status}'."

    async def generate_friendly_fallback(self, intent: IntentType) -> str:
        """LLM-generated fallback message tailored to the inferred intent."""
        try:
            system_prompt = """
            You are JobTrackAI, a friendly assistant. The system needs a fallback reply.
            Produce a concise, supportive, human message (1 emoji max) tailored to the intent provided.
            - For JOB_SEARCH: invite the user to view or filter their applications.
            - For STATUS_UPDATE: ask for the missing piece (job or status) as a single, clear question.
            - For NEW_JOB: ask for the missing required fields (job_title and/or company_name) succinctly.
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
        return "How can I help with your applications? Try 'show my jobs' or share a job title and company ✨"

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
        return "I can’t help with that. I can show your applications, add a new job, or update a status instead ✨"

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
        return prefix + f"Could you share the {', '.join(missing_fields)}? Just a quick phrase is perfect ✨"
    
    async def _get_chat_completion(
        self, 
        system_prompt: str, 
        user_message: str
    ) -> Optional[str]:
        """
        Get chat completion from OpenAI API
        """
        try:
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return None

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
