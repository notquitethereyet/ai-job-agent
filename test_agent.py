"""
Simple test script for JobTrackAI agent
"""

import asyncio
import os
from dotenv import load_dotenv
from app.services.agent_service import AgentService
from app.models.agent import UserMessage

# Load environment variables
load_dotenv()

async def test_agent():
    """Test the agent with sample messages"""
    
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set. Using mock responses.")
        print("   Set OPENAI_API_KEY in .env file to test with real AI.")
    
    agent_service = AgentService()
    
    # Test messages
    test_messages = [
        "I applied to a Software Engineer position at Google",
        "Update my application status to interview",
        "Show me all my job applications",
        "What jobs have I applied to recently?"
    ]
    
    print("🤖 Testing JobTrackAI Agent\n")
    
    for i, message in enumerate(test_messages, 1):
        print(f"Test {i}: {message}")
        print("-" * 50)
        
        try:
            user_msg = UserMessage(message=message, user_id="test_user")
            response = await agent_service.process_message(user_msg)
            
            print(f"Response: {response.response}")
            print(f"Action: {response.action_taken}")
            print(f"Intent: {response.intent}")
            print(f"Confidence: {response.confidence}")
            if response.requires_clarification:
                print(f"Clarification needed: {response.clarification_prompt}")
            print()
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print()

if __name__ == "__main__":
    asyncio.run(test_agent())
