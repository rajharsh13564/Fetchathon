"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from config.logging_config import setup_logging, get_logger
from backend.api import health, chat

setup_logging()
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting FinancePilot AI Backend")
    logger.info(f"Gemini configured: {settings.validate_gemini_key()}")
    logger.info(f"Model: {settings.gemini_model}")
    yield
    logger.info("Shutting down FinancePilot AI Backend")


app = FastAPI(
    title="FinancePilot AI",
    description="Multi-agent financial research platform for Indian equity portfolios",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "FinancePilot AI",
        "version": "2.0.0",
        "description": "Multi-agent financial research platform for Indian equity portfolios",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )