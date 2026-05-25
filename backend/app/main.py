from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import router as invoice_router
from app.config import get_settings
from app.database import run_migrations
from app.logging_config import configure_logging
import logging

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup started")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Upload directory ready path=%s", settings.upload_dir)
    logger.info("Running database migrations")
    run_migrations()
    logger.info("Database migrations completed")
    yield
    logger.info("Application shutdown completed")

settings.upload_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.include_router(invoice_router)
