"""Health check endpoint."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime

from config.settings import get_settings, Settings
from backend.dependencies import get_settings_dep

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str
    gemini_configured: bool
    settings: dict


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings_dep)):
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="2.0.0",
        gemini_configured=settings.validate_gemini_key(),
        settings={
            "gemini_model": settings.gemini_model,
            "market_data_cache_ttl": settings.market_data_cache_ttl,
            "api_host": settings.api_host,
            "api_port": settings.api_port,
        },
    )


@router.get("/ready")
async def readiness_check(settings: Settings = Depends(get_settings_dep)):
    """Readiness check endpoint."""
    checks = {
        "config": True,
        "gemini": settings.validate_gemini_key(),
    }
    all_ready = all(checks.values())
    return {
        "ready": all_ready,
        "checks": checks,
    }