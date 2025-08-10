# JobTrackAI - Job Application Tracking Agent

An AI-powered agent that processes user messages and job links, understands their intent, and updates a central job application tracking database.

## 🚀 Features

- **Smart Job Parsing**: Automatically extracts job details from LinkedIn links
- **Intent Recognition**: Understands new job applications vs. status updates
- **AI-Powered Processing**: Uses OpenAI GPT-4o for natural language understanding
- **Centralized Tracking**: Stores all job applications in Supabase database
- **Ambiguity Resolution**: Prompts for clarification when multiple matches exist
- **Robust Error Handling**: Comprehensive logging and fallback mechanisms

## 🏗️ Tech Stack

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **Python 3.11+** - High-performance Python runtime
- **Uvicorn** - ASGI server for production deployment

### AI & LLM
- **OpenAI GPT-4o-mini** - Primary model for cost/speed balance
- **OpenAI GPT-4o** - Alternative for complex reasoning tasks
- **OpenAI Agents** - For intent classification and entity recognition

### Database
- **Supabase** - PostgreSQL database with REST API
- **PostgreSQL** - Primary database (managed by Supabase)

### Web Scraping
- **BeautifulSoup4** - HTML parsing for job page extraction
- **Requests** - HTTP client for fetching job pages
- **Selenium** - Fallback for JavaScript-heavy pages

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
   git clone <repository-url>
   cd job-watch
   ```

2. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**
   ```bash
   uv pip install -r requirements.txt
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

1. **Run the development server**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

3. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## 📚 API Usage

### Process a Message
```bash
curl -X POST "http://localhost:8000/agent/message" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "I applied to this job: https://linkedin.com/jobs/view/123456"
     }'
```

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

## 🗄️ Database Schema

The application uses a single `jobs` table with the following structure:

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

### Development Settings

```bash
# Enable debug mode
export DEBUG=true

# Set log level
export LOG_LEVEL=DEBUG

# Enable verbose logging
export VERBOSE_LOGGING=true
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app

# Run specific test file
uv run pytest tests/test_agent.py

# Run with verbose output
uv run pytest -v
```

## 📝 Development

### Code Quality

```bash
# Format code
uv run black .

# Sort imports
uv run isort .

# Lint code
uv run flake8

# Type checking
uv run mypy .
```

### Project Structure

```
job-watch/
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

### Docker

```bash
# Build image
docker build -t jobtrackai .

# Run container
docker run -p 8000:8000 --env-file .env jobtrackai
```

### Production Considerations

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the [API docs](http://localhost:8000/docs) when running locally
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Join the conversation in GitHub Discussions

## 🔮 Roadmap

### MVP Features (Current)
- ✅ Intent classification (new job vs. status update)
- ✅ Job parsing from LinkedIn (basic HTML scraping)
- ✅ Supabase integration (insert/update records)
- ✅ Clarification prompts for ambiguity
- ✅ Robust error handling & logging

### Future Enhancements
- 🔄 WhatsApp integration
- 🔄 Resume tailoring for ATS
- 🔄 Keyword matching between job description and resume
- 🔄 Multi-user authentication for personal dashboards
- 🔄 Automatic company research summaries
- 🔄 Advanced analytics and reporting

---

**Built with ❤️ using FastAPI, OpenAI, and Supabase**
