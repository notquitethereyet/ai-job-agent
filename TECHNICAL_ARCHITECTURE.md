# JobTrackAI: Technical Architecture Documentation

This document provides a comprehensive technical overview of the JobTrackAI system, explaining the end-to-end process flow from WhatsApp chat to the AI agent and database interactions.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Details](#component-details)
   - [WhatsApp Integration](#whatsapp-integration)
   - [Make.com Scenarios](#makecom-scenarios)
   - [FastAPI Backend](#fastapi-backend)
   - [OpenAI Integration](#openai-integration)
   - [Supabase Database](#supabase-database)
4. [Data Flow](#data-flow)
5. [Key Processes](#key-processes)
   - [New User Registration](#new-user-registration)
   - [Message Processing](#message-processing)
   - [Job Creation](#job-creation)
   - [Job Status Updates](#job-status-updates)
   - [Job Listing](#job-listing)
6. [Deployment Architecture](#deployment-architecture)
7. [Environment Configuration](#environment-configuration)

## System Overview

JobTrackAI is an AI-powered job application tracking system that allows users to interact with a virtual assistant through WhatsApp. The system helps users track their job applications, update statuses, and get insights about their job search process. The application uses natural language processing to understand user intents and provides friendly, personalized responses.

The system consists of the following major components:
- WhatsApp Business API for messaging
- Make.com (formerly Integromat) for webhook processing and integration
- FastAPI backend for business logic and AI processing
- OpenAI for natural language understanding and response generation
- Supabase for database storage and authentication

## Architecture Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐
│  WhatsApp   │────▶│  Make.com   │────▶│  FastAPI Backend        │
│  Business   │     │  Scenarios  │     │  (Railway Deployment)   │
│  API        │◀────│             │◀────│                         │
└─────────────┘     └─────────────┘     │  ┌─────────────────┐    │
                                        │  │ Agent Service   │    │
                                        │  │ - Intent        │    │
                                        │  │   Detection     │    │
                                        │  │ - Message       │    │
                                        │  │   Processing    │    │
                                        │  └─────────────────┘    │
                                        │                         │
                                        │  ┌─────────────────┐    │
                                        │  │ OpenAI Service  │    │
                                        │  │ - NLP           │    │
                                        │  │ - Response      │    │
                                        │  │   Generation    │    │
                                        │  └─────────────────┘    │
                                        │                         │
                                        │  ┌─────────────────┐    │
                                        │  │ Supabase        │    │
                                        │  │ Service         │    │
                                        │  │ - Data Storage  │    │
                                        │  │ - User Mgmt     │    │
                                        │  └─────────────────┘    │
                                        └─────────────┬───────────┘
                                                      │
                                                      ▼
                                        ┌─────────────────────────┐
                                        │  Supabase Database      │
                                        │  - Users                │
                                        │  - Jobs                 │
                                        │  - Conversations        │
                                        └─────────────────────────┘
```

## Component Details

### WhatsApp Integration

JobTrackAI uses the WhatsApp Business API to send and receive messages. Users interact with the system through a WhatsApp chat interface, sending natural language messages about their job applications.

**Key Features:**
- Webhook-based message reception
- Message delivery to users
- Support for text-based interactions

### Make.com Scenarios

Make.com (formerly Integromat) serves as the integration layer between WhatsApp and the FastAPI backend. Two main scenarios handle the workflow:

#### 1. New User Scenario (`new_user.json`)

This scenario handles:
- Incoming WhatsApp webhook events
- User lookup in Supabase database
- New user registration if the user doesn't exist
- Message forwarding to the FastAPI backend
- Welcome message for new users

**Flow:**
1. WhatsApp webhook event triggers the scenario
2. Scenario checks if the user exists in Supabase
3. If not, creates a new user record and sends a welcome message
4. If user exists, sets variables (user_id, message) and forwards to the bot scenario
5. Variables are passed to the FastAPI backend for processing

#### 2. Bot Interaction Scenario (`bot.json`)

This scenario handles:
- Processing responses from the FastAPI backend
- Sending messages back to the user via WhatsApp

**Flow:**
1. Receives message content, user ID, and WhatsApp ID as parameters
2. Sends HTTP request to the FastAPI backend with user message and ID
3. Processes the response from the API
4. Directly sends the agent's response back to the user via WhatsApp using the WhatsApp Business Cloud API
5. Uses the user's WhatsApp ID to ensure the message is delivered to the correct recipient

### FastAPI Backend

The backend is built with FastAPI and provides the core business logic, AI processing, and database interactions.

**Key Components:**

1. **Main Application (`main.py`)**
   - FastAPI setup and configuration
   - Endpoint definitions
   - Service initialization
   - Error handling

2. **Models**
   - `agent.py`: Defines UserMessage and AgentResponse models
   - `job.py`: Defines Job-related models including JobStatus enum

3. **Services**
   - `agent_service.py`: Core logic for processing user messages, detecting intents, and generating responses
   - `openai_service.py`: Integration with OpenAI for NLP and dynamic response generation
   - `supabase_service.py`: Database interactions with Supabase
   - `job_service.py`: Job-specific business logic

### OpenAI Integration

The system uses OpenAI's language models for:
- Intent classification
- Entity extraction (job details, status updates)
- Generating dynamic, personalized responses with personality

**Key Features:**
- `generate_friendly_job_created`: Creates personalized job creation confirmations
- `generate_friendly_status_updated`: Creates personalized status update confirmations
- `generate_friendly_error`: Creates friendly error messages with personality
- `generate_friendly_fallback`: Creates responses when intent is unclear
- `generate_friendly_job_list`: Creates responses for job listing requests

### Supabase Database

Supabase provides the database layer with PostgreSQL and additional features:

**Key Tables:**
- `users`: Stores user information
- `jobs`: Stores job application details
- `conversations`: Stores conversation history and metadata

**Connection Methods:**
- REST API for most operations
- Transaction pooler for database connections (aws-0-us-west-1.pooler.supabase.com:6543)

## Data Flow

### End-to-End Message Flow

1. **User Sends Message (WhatsApp):**
   - User sends a text message via WhatsApp
   - Example: "I applied for Software Engineer at Google yesterday"

2. **WhatsApp to Make.com:**
   - WhatsApp Business API sends a webhook event to Make.com
   - Make.com processes the incoming webhook payload

3. **Make.com to Supabase (User Check):**
   - Make.com checks if the WhatsApp number exists in the users table
   - If not, creates a new user record

4. **Make.com to FastAPI:**
   - Make.com forwards the message to the FastAPI backend
   - Endpoint: POST /agent/message
   - Payload: { "user_id": "user123", "message": "I applied for Software Engineer at Google yesterday" }

5. **FastAPI Processing:**
   - `AgentService.process_message()` receives the request
   - OpenAI service detects intent (job creation)
   - OpenAI service extracts entities (job title, company, status, date)
   - Supabase service creates a new job record
   - OpenAI service generates a friendly response

6. **FastAPI to Make.com:**
   - FastAPI returns the response to Make.com
   - Response includes the message text and any actions taken

7. **Make.com to WhatsApp:**
   - Make.com forwards the response to WhatsApp
   - User receives the friendly, personalized response

## Key Processes

### New User Registration

When a new user messages the system for the first time:

1. Make.com receives the WhatsApp webhook event
2. Make.com checks if the phone number exists in Supabase
3. If not, Make.com creates a new user record with:
   - WhatsApp phone number as identifier
   - Default settings
   - Creation timestamp
4. The user is now registered and can interact with the system

### Message Processing

When processing a user message:

1. `AgentService.process_message()` receives the message
2. `OpenAIService.classify_intent()` determines the user's intent:
   - Job creation
   - Status update
   - Job listing
   - General question
   - Other intents

3. Based on the intent, different processing paths are taken:
   - Entity extraction for job details
   - Database lookups for existing jobs
   - Status normalization for updates
   - Response generation appropriate to the intent

4. The system maintains conversation context in Supabase to handle multi-turn interactions

### Job Creation

When a user wants to add a new job application:

1. System detects "job creation" intent
2. OpenAI extracts job details:
   - Job title
   - Company name
   - Application date
   - Initial status (default: applied)
   - Any notes or additional information

3. System creates a job record in Supabase
4. System generates a friendly confirmation using `generate_friendly_job_created()`
5. If information is missing, system asks for clarification

### Job Status Updates

When a user wants to update a job status:

1. System detects "status update" intent
2. System identifies which job to update:
   - From explicit mentions ("update Google job to interview")
   - From conversation context
   - By asking for clarification if ambiguous

3. System normalizes the status value to a valid JobStatus enum
4. System updates the job record in Supabase
5. System confirms with a friendly message using `generate_friendly_status_updated()`

### Job Listing

When a user wants to see their job applications:

1. System detects "job listing" intent
2. System retrieves jobs from Supabase:
   - All jobs or filtered by status
   - Limited to recent or relevant jobs
   - Sorted appropriately

3. System formats the job list in a readable way
4. System generates a friendly response with `generate_friendly_job_list()`

## Deployment Architecture

JobTrackAI is deployed on Railway with the following configuration:

- **Web Service**: FastAPI application
- **Database**: Connection to Supabase via transaction pooler
- **Environment Variables**: Configured in Railway dashboard
- **Dockerfile**: Defines the container setup

**Key Deployment Considerations:**
- Railway environment must have correct Supabase connection details
- Transaction pooler is used for database connections (aws-0-us-west-1.pooler.supabase.com:6543)
- Environment variables must include OpenAI API keys

## Environment Configuration

The following environment variables are required:

```
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
DATABASE_URL=postgresql://postgres.user:password@aws-0-us-west-1.pooler.supabase.com:6543/postgres

# Application Configuration
LOG_LEVEL=INFO
PORT=8000
HOST=0.0.0.0
```

**Important Notes:**
- `SUPABASE_URL` must be the REST API URL (https://your-project.supabase.co)
- `DATABASE_URL` must use the transaction pooler (aws-0-us-west-1.pooler.supabase.com:6543)
- Local development can use direct Postgres connection, but production should use the transaction pooler
