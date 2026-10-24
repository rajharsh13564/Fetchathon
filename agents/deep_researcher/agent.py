"""DeepResearcher Agent - AI-powered fundamental research."""
import asyncio
from typing import Optional, Dict, Any

from uagents import Agent, Context, Protocol
from uagents_core.models import Model

from config.settings import get_settings
from config.logging_config import setup_logging, get_logger
from schemas.common import CorrelationContext, ErrorResponse
from schemas.research import ResearchRequest, AgenticThesisResponse
from agents.deep_researcher.schemas import DeepResearcherStatus, DeepResearcherConfig
from services.research_service import get_research_service, ResearchService
from services.gemini_client import get_gemini_client
from shared.protocol import DEEP_RESEARCHER_PROTOCOL
from shared.errors import ConfigurationError, GeminiAPIError

setup_logging()
logger = get_logger(__name__)

settings = get_settings()

# Create DeepResearcher agent
deep_researcher = Agent(
    name="finpilot-deep-researcher",
    seed=settings.deep_researcher_seed,
    port=8004,
    mailbox=settings.deep_researcher_mailbox_key,
)

# Protocol
deep_researcher_protocol = Protocol(name=DEEP_RESEARCHER_PROTOCOL, version="1.0.0")

# Services
gemini_client = get_gemini_client()
research_service = get_research_service()

# Configuration
config = DeepResearcherConfig(
    model=settings.gemini_model,
    max_retries=3,
    timeout_seconds=60,
    temperature=0.3,
    max_tokens=8192,
)


# ============================================================================
# Message Handlers
# ============================================================================

@deep_researcher_protocol.on_message(model=ResearchRequest, replies=AgenticThesisResponse)
async def handle_research_request(ctx: Context, sender: str, msg: ResearchRequest):
    """Handle research request."""
    logger.info(f"Research request from {sender} for {msg.ticker}")

    if not gemini_client:
        logger.error("Gemini client not configured")
        error_resp = ErrorResponse(
            error="Gemini API key not configured. Cannot perform research.",
            code="CONFIGURATION_ERROR",
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)
        return

    try:
        result = await research_service.research_company(msg, msg.correlation_context)
        await ctx.send(sender, result)
        logger.info(f"Research completed for {msg.ticker}")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        error_resp = ErrorResponse(
            error=str(e),
            code="CONFIGURATION_ERROR",
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)
    except GeminiAPIError as e:
        logger.error(f"Gemini API error: {e}")
        error_resp = ErrorResponse(
            error=str(e),
            code="GEMINI_API_ERROR",
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)
    except Exception as e:
        logger.error(f"Research error: {e}")
        error_resp = ErrorResponse(
            error=f"Research failed: {str(e)}",
            code="RESEARCH_ERROR",
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)


# ============================================================================
# Startup/Shutdown
# ============================================================================

@deep_researcher.on_event("startup")
async def startup(ctx: Context):
    """Agent startup."""
    logger.info(f"DeepResearcher started at {deep_researcher.address}")
    logger.info(f"Model: {config.model}")
    logger.info(f"Gemini configured: {gemini_client is not None}")


@deep_researcher.on_event("shutdown")
async def shutdown(ctx: Context):
    """Agent shutdown."""
    logger.info("DeepResearcher shutting down")


# Include protocol
deep_researcher.include(deep_researcher_protocol)


if __name__ == "__main__":
    deep_researcher.run()