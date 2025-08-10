"""
OpenAI service for JobTrackAI
Handles AI model interactions and intent classification
"""

import os
import logging
from typing import Optional, Dict, Any
from openai import OpenAI
from openai.types.chat import ChatCompletion
from ..models.agent import IntentType, JobExtraction

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for OpenAI API interactions"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"  # Default model for cost/speed balance
        
    async def classify_intent(self, message: str) -> tuple[IntentType, float]:
        """
        Classify the intent of a user message
        Returns: (intent_type, confidence_score)
        """
        try:
            system_prompt = """
            You are an AI assistant that helps classify user messages about job applications.
            
            Classify the intent of the user's message into one of these categories:
            - NEW_JOB: User is adding a new job application
            - STATUS_UPDATE: User is updating the status of an existing job
            - JOB_SEARCH: User is asking about job search or existing jobs
            - AMBIGUOUS: Message is unclear and needs clarification
            - UNKNOWN: Message doesn't fit any category
            
            Respond with only the intent type and confidence score (0.0-1.0).
            Format: INTENT_TYPE|CONFIDENCE_SCORE
            """
            
            response = await self._get_chat_completion(
                system_prompt=system_prompt,
                user_message=message
            )
            
            # Parse response
            if response and "|" in response:
                intent_str, confidence_str = response.split("|")
                intent = IntentType(intent_str.strip().upper())
                confidence = float(confidence_str.strip())
                return intent, confidence
            else:
                logger.warning(f"Unexpected response format: {response}")
                return IntentType.UNKNOWN, 0.0
                
        except Exception as e:
            logger.error(f"Error classifying intent: {str(e)}")
            return IntentType.UNKNOWN, 0.0
    
    async def extract_job_details(self, message: str) -> JobExtraction:
        """
        Extract job details from user message
        """
        try:
            system_prompt = """
            You are an AI assistant that extracts job information from user messages.
            
            Extract the following information if present:
            - job_title: The job role/title
            - company_name: The company name
            - job_link: URL to the job posting
            - job_description: Brief description of the job
            
            If information is not present, set to null.
            Respond with a JSON object containing only the extracted fields.
            """
            
            response = await self._get_chat_completion(
                system_prompt=system_prompt,
                user_message=message
            )
            
            # TODO: Parse JSON response and return JobExtraction
            # For now, return placeholder
            return JobExtraction(
                job_title=None,
                company_name=None,
                job_link=None,
                job_description=None,
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
            You are JobTrackAI, an AI assistant that helps users track job applications.
            Be helpful, concise, and professional. Ask for clarification when needed.
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
    
    async def _get_chat_completion(
        self, 
        system_prompt: str, 
        user_message: str
    ) -> Optional[str]:
        """
        Get chat completion from OpenAI API
        """
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
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
