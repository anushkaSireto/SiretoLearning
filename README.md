# Invoice Recognition System

MVP implementation: upload invoice files, extract structured invoice data with an LLM service, store records, and review/correct results in a React dashboard.

## Stack

- Frontend: React + Vite
- Backend: Python + FastAPI
- Database: PostgreSQL + Alembic migrations
- Auth: Keycloak JWT validation, enabled by default
- Storage: local `backend/uploads`
- AI extraction: Gemini when `LLM_PROVIDER=gemini` and `GEMINI_API_KEY` are configured, with a mock fallback for local testing

## Quick Start

1. Start infrastructure:

```bash
docker compose up -d postgres keycloak
```

2. Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

3. Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and the API docs are at `http://localhost:8000/docs`.

## Database Migrations

The backend runs Alembic migrations automatically during FastAPI startup.

Useful commands:

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "describe schema change"
```

The initial migration is safe for an existing local database: it records the current schema in `alembic_version` without recreating tables that already exist.

