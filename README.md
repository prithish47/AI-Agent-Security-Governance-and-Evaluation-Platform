# AgentGuard

## AI Agent Security, Governance & Reliability Platform

AgentGuard is a developer-facing platform that provides a centralized security and governance layer between AI agents and the tools they execute.

**Foundational Principle:** LLMs propose actions. AgentGuard authorizes, controls, executes, and audits them.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone and configure

```bash
git clone <repository-url>
cd Agent_Guard
cp .env.example .env
```

### 2. Start all services

```bash
docker compose up --build
```

### 3. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Access the application

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

---

## Local Development (Without Docker)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Database

Requires PostgreSQL 17 running locally. Update `DATABASE_URL` in `.env`.

---

## Project Structure

```
Agent_Guard/
├── backend/           # FastAPI application
├── frontend/          # Next.js dashboard
├── docs/              # Architecture & design documentation
├── docker-compose.yml # Service orchestration
├── .env.example       # Environment variable template
└── BUILD-STATUS.md    # Implementation progress tracker
```

---

## Documentation

- [Architecture](docs/architecture.md)
- [Database Design](docs/database-design.md)
- [Security Model](docs/security-model.md)
- [API Reference](docs/api-reference.md)
- [Development Guide](docs/development-guide.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Phase Details](docs/phases.md)

---

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| Database | PostgreSQL 17 |
| Auth | JWT (PyJWT) + Argon2id |
| AI Providers | OpenAI, Gemini, Ollama, Mock |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

---

## License

MIT
