# JobTrackAI - Job Application Tracking Agent

Spreadsheets kept ghosting my job applications, so I shipped a hype man with good boundaries. JobTrackAI tracks your apps, talks like a friend, and refuses sketchy requests — all without making you wrangle 16 columns of chaos.

## 🚀 Features (no fluff)

- **Drop a link, walk away**: Auto-snags title/company; defaults status to `applied` when you just share a link or say “I applied”. Only asks for what’s actually missing.
- **Plain English updates**: “2nd one rejected” → picks the right job. Multi-match? You get a short, numbered list — no internal IDs in your face.
- **Talks like a friend**: LLM-crafted tone — upbeat for good news, compassionate for rejections, and short/clear for everything else.
- **Refuses politely**: Small talk gets a gentle redirect; sketchy asks (secrets/internal IDs) get a kind but firm no.
- **Understands context**: Merges partial info across messages and auto-creates when title + company are known.
- **Supabase-backed**: It’s all in Postgres so you can actually query your history.

### Why you might care
- Fewer “what was that job again?” moments
- More “okay king/queen, keep going” energy
- Zero “oops I leaked my API key” energy

### Behavior & Tone
- LLM-crafted responses with adapted tone:
  - Friendly/cheerful for positive events (new job, interview, offer)
  - Compassionate for negative outcomes (rejected/withdrawn)
- Small-talk/off-topic messages receive a brief, kind redirect back to job actions
- Safety guardrails: kind but firm refusals for requests about secrets/internal data (LLM + keyword detection)
- Multi-match updates: numbered choices, accept replies like "2nd one rejected" (no internal IDs ever shown)

## 🏗️ Tech Stack

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **Python 3.11+** - High-performance Python runtime
- **Uvicorn** - ASGI server for production deployment

### AI & LLM
- **OpenAI GPT-4o-mini** - Primary model (fast + affordable)
- **OpenAI GPT-4o** - For heavier reasoning when needed
- LLM drives: intent/entity parsing, tone, small-talk redirects, safety refusals

### Database
- **Supabase** - PostgreSQL database with REST API
- **PostgreSQL** - Primary database (managed by Supabase)



### Development Tools
- **uv** - Fast Python package installer and resolver
- **Pytest** - Testing framework
- **Black** - Code formatting
- **MyPy** - Static type checking

## 📋 Prerequisites

- Python 3.11 or higher
- uv (for dependency management)
- Supabase account and project
- OpenAI API key

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone git@github.com:notquitethereyet/ai-job-agent.git
   cd ai-job-agent
   ```

2. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies (local to this repo)**
   ```bash
   uv sync
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Configure environment variables**
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export SUPABASE_URL="your-supabase-url"
   export SUPABASE_ANON_KEY="your-supabase-anon-key"
   ```

## 🚀 Quick Start

1. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key and Supabase credentials
   ```

2. **Create Supabase database table**
   ```bash
   # Go to Supabase Dashboard → SQL Editor
   # Run the SQL from database/schema.sql
   ```

3. **Run the development server**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

4. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## 📚 API Usage

### Process a Message
```bash
curl -X POST "http://localhost:8000/agent/message" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "I applied to AI Engineer I @ Mintegral. Link: https://www.linkedin.com/jobs/view/4210607143",
       "user_id": "<uuid>"
     }'
# Response will auto-create the job when both title and company are present.
```

### List Jobs
```bash
curl -X POST "http://localhost:8000/agent/message" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "show my jobs",
       "user_id": "<uuid>"
     }'
# Returns a concise list of your jobs with status (first 10). Internal IDs are never exposed.
```

### WhatsApp via Make.com (Option B)

Your Make.com scenario handles user creation in Supabase. When a user exists, call the agent directly:

```bash
POST https://<your-host>/agent/message
Content-Type: application/json

{
  "message": "show my jobs",
  "user_id": "<uuid>"
}
```

Optional: pass `conversation_id` to thread messages, otherwise the server reuses/creates one.

### Add New Job
```bash
curl -X POST "http://localhost:8000/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "job_title": "Software Engineer",
       "company_name": "Google",
       "job_link": "https://linkedin.com/jobs/view/123456",
       "job_description": "Backend development role"
     }'
```

### Update Job Status
```bash
curl -X PATCH "http://localhost:8000/jobs/{job_id}" \
     -H "Content-Type: application/json" \
     -d '{
       "status": "interview"
     }'
```

## 🗄️ Database Schema (so your future self can query stuff)

Core tables:

### users

| Column        | Type        | Description                 |
|---------------|-------------|-----------------------------|
| id            | uuid (PK)   | App user UUID               |
| phone_e164    | text UNIQUE | Phone number in E.164       |
| display_name  | text        | Optional display name       |
| metadata      | jsonb       | Misc per-user settings/data |
| created_at    | timestamptz | Row created                 |
| updated_at    | timestamptz | Row updated                 |

### conversations

| Column           | Type        | Description                     |
|------------------|-------------|---------------------------------|
| id               | uuid (PK)   | Conversation id                 |
| user_id          | uuid        | Owner                           |
| title            | text        | Optional title                  |
| metadata         | jsonb       | LLM state (pending selections)  |
| created_at       | timestamptz | Created                         |
| updated_at       | timestamptz | Updated                         |
| last_message_at  | timestamptz | Recency marker                  |

### messages

| Column           | Type        | Description                     |
|------------------|-------------|---------------------------------|
| id               | uuid (PK)   | Message id                      |
| conversation_id  | uuid        | FK to conversations             |
| user_id          | uuid        | User owner                      |
| role             | text        | 'user' or 'assistant'           |
| content          | text        | Plain text                      |
| tool_calls       | jsonb       | Optional tool/intent metadata   |
| created_at       | timestamptz | Timestamp                       |

### jobs

| Column           | Type        | Description                                    |
|------------------|-------------|------------------------------------------------|
| id               | uuid (PK)   | Unique job ID                                  |
| user_id          | uuid        | Owner of job entry                             |
| job_title        | text        | Job role name                                  |
| company_name     | text        | Company name                                   |
| job_link         | text        | URL to posting                                 |
| job_description  | text        | Short summary                                  |
| status           | text        | Current status (applied, interview, offer, etc.) |
| date_added       | timestamptz | When job was added                             |
| last_updated     | timestamptz | Last status change                             |

## 🔧 Configuration

### Environment Variables

| Variable           | Description                    | Required |
|--------------------|--------------------------------|----------|
| `OPENAI_API_KEY`  | OpenAI API key                | Yes      |
| `SUPABASE_URL`    | Supabase project URL          | Yes      |
| `SUPABASE_ANON_KEY` | Supabase anonymous key       | Yes      |
| `LOG_LEVEL`       | Logging level (default: INFO) | No       |
| `DEBUG`           | Enable debug mode (default: false) | No |
| `OPENAI_MODEL`    | Override model (default: gpt-4o-mini) | No |

### Development Settings

```bash
# Enable debug mode
export DEBUG=true

# Set log level
export LOG_LEVEL=DEBUG

# Enable verbose logging
export VERBOSE_LOGGING=true
```

### Project Structure (lightweight on purpose)

```
 ai-job-agent/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models/              # Pydantic models
│   ├── services/            # Business logic
│   ├── api/                 # API endpoints
│   └── utils/               # Utility functions
├── tests/                   # Test files
├── .cursor/rules/           # Cursor IDE rules
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
└── README.md                # This file
```

## 🚀 Deployment

### Railway (recommended)

1) Create a new project on Railway and select Deploy from GitHub.
2) Add environment variables in Railway project settings:
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - Optional: `LOG_LEVEL=INFO`, `DEBUG=false`
3) Railway will detect the `Dockerfile` and build automatically.
4) Once deployed, open the app URL and visit `/docs`.

Health check path: `/health`

### Docker

```bash
# Build image
docker build -t jobtrackai .

# Run container
docker run -p 8000:8000 --env-file .env jobtrackai
```

### Troubleshooting (Railway/Docker)

- **ModuleNotFoundError: No module named 'app.models'** ✅ FIXED
  - **Root cause**: Empty `app/__init__.py` file prevented Python from recognizing `app` as a package
  - **Solution**: Added package docstring to `app/__init__.py`
  - **Prevention**: Ensure all package directories have non-empty `__init__.py` files
  - Use package-relative imports inside the `app` package (already applied):
    - `from .models.agent import UserMessage`
    - `from .services.agent_service import AgentService`
  - Updated Dockerfile to use `uv` for better dependency management and consistency
  - Updated railway.toml to use `uv run` command for execution
- **Service initialization fails on startup**
  - Set required env vars in Railway: `OPENAI_API_KEY`, and either `SUPABASE_URL` + `SUPABASE_ANON_KEY` or `DATABASE_URL`.
  - Health check is available at `/health` even if database isn't configured; DB operations require the envs.

### Production Considerations (when you stop running it on your laptop)

- Use production ASGI server (Gunicorn + Uvicorn)
- Set up reverse proxy (Nginx)
- Configure SSL/TLS certificates
- Implement proper logging and monitoring
- Set up database connection pooling
- Configure rate limiting and security headers

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

Licensed under the "Do whatever you want lil bro" License

## 🆘 Support

- **Documentation**: Check the [API docs](http://localhost:8000/docs) when running locally
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Join the conversation in GitHub Discussions

## 🔮 Roadmap

### MVP Features (Current)
- ✅ Intent classification (new job vs. status update)
- ✅ AI-powered message processing with OpenAI
- ✅ Full CRUD operations for job management
- ✅ Supabase integration with PostgreSQL
- ✅ FastAPI endpoints for all operations
- ✅ Job statistics and reporting
- ✅ Robust error handling & logging
- ✅ Graceful fallback for job link processing

### Future Enhancements
- 🔄 Chat (Discord/WhatsApp) integration
- 🔄 Resume tailoring for ATS
- 🔄 Keyword matching between job description and resume
- 🔄 Multi-user authentication for personal dashboards
- 🔄 Automatic company research summaries
- 🔄 Advanced analytics and reporting

---

**Built with ❤️ using FastAPI, OpenAI, and Supabase**

## 🧪 Manual Testing

Use the curated prompts in `TEST_PROMPTS.md` to validate happy paths, small-talk redirects, safety refusals, and edge cases (multi-entity updates, links, slang, etc.).
