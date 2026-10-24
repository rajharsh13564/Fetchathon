"""FastAPI dependencies."""
from typing import Optional
from fastapi import Depends, HTTPException, Header
from pydantic import BaseModel

from config.settings import get_settings, Settings
from schemas.common import CorrelationContext


class APIKeyDep(BaseModel):
    """API key dependency (for future auth)."""
    api_key: Optional[str] = None


def get_settings_dep() -> Settings:
    """Get settings dependency."""
    return get_settings()


def get_correlation_context(
    x_request_id: Optional[str] = Header(None),
    x_conversation_id: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
) -> CorrelationContext:
    """Extract correlation context from headers."""
    return CorrelationContext(
        request_id=x_request_id or "",
        conversation_id=x_conversation_id,
        user_id=x_user_id,
    )


async def verify_gemini_configured(settings: Settings = Depends(get_settings_dep)) -> bool:
    """Verify Gemini is configured."""
    if not settings.validate_gemini_key():
        raise HTTPException(
            status_code=503,
            detail="Gemini API not configured. Set GEMINI_API_KEY in environment.",
        )
    return True