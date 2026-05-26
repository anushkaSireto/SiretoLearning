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

## Discord Invoice Bot

The backend includes a simple Discord bot that uses the same Gemini invoice extractor as the API.

1. Create a Discord application and bot in the Discord Developer Portal.
2. Enable the bot's Message Content Intent.
3. Add the bot token to `backend/.env`:

```bash
DISCORD_BOT_TOKEN=your_discord_bot_token
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_google_ai_studio_api_key
GEMINI_MODEL=gemini-2.5-flash
```

4. Install backend dependencies and run the bot:

```bash
cd backend
pip install -r requirements.txt
python -m app.discord_bot
```

Bot commands:

```text
!ping
!invoice      Upload an invoice image or PDF with this command.
!ask <text>   Ask a question about the last invoice uploaded in the channel.
!invoice_json Show the extracted invoice JSON for review.
!clear_invoice Forget the stored invoice for the current channel.
!help_invoice Show bot usage help in Discord.
```

After an invoice is uploaded, users can also ask normal follow-up questions without `!ask`:

```text
What is the total amount?
Who is the seller?
Summarize this invoice.
```

Demo flow:

```text
1. Start the bot locally with python -m app.discord_bot.
2. In Discord, run !ping to confirm the bot is online.
3. Upload an invoice image or PDF with !invoice.
4. Review the formatted invoice summary embed.
5. Ask follow-up questions with !ask or normal language, for example:
   !ask what is the total amount?
   What is the total amount?
   !ask who is the seller?
   !ask summarize this invoice
6. Use !invoice_json to inspect the extracted structured data.
7. Use !clear_invoice before testing another invoice in the same channel.
```

Run with Docker Compose:

```bash
docker compose up --build discord-bot
```

Run the whole local stack:

```bash
docker compose up --build
```



