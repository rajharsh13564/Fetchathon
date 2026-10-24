"""QuantScreener Agent - Quantitative stock screening."""
import asyncio
from typing import Optional, Dict, Any, List

from uagents import Agent, Context, Protocol
from uagents_core.models import Model

from config.settings import get_settings
from config.logging_config import setup_logging, get_logger
from schemas.common import CorrelationContext, ErrorResponse
from schemas.screening import (
    ScreeningRequest,
    RankedShortlistResponse,
    ScreeningFilters,
)
from agents.quant_screener.schemas import QuantScreenerConfig, QuantScreenerStatus
from services.screening_service import get_screening_service, ScreeningService
from shared.protocol import QUANT_SCREENER_PROTOCOL
from shared.errors import ValidationError, MarketDataError

setup_logging()
logger = get_logger(__name__)

settings = get_settings()

# Create QuantScreener agent
quant_screener = Agent(
    name="finpilot-quant-screener",
    seed=settings.quant_screener_seed,
    port=8002,
    mailbox=settings.quant_screener_mailbox_key,
)

# Protocol
quant_screener_protocol = Protocol(name=QUANT_SCREENER_PROTOCOL, version="1.0.0")

# Service instance
screening_service = get_screening_service()

# Configuration
config = QuantScreenerConfig(
    default_universe=screening_service.universe,
    max_concurrent_fetches=10,
    default_max_results=20,
    enable_caching=True,
    cache_ttl_seconds=settings.market_data_cache_ttl,
)


# ============================================================================
# Message Handlers
# ============================================================================

@quant_screener_protocol.on_message(model=ScreeningRequest, replies=RankedShortlistResponse)
async def handle_screening_request(ctx: Context, sender: str, msg: ScreeningRequest):
    """Handle screening request."""
    logger.info(f"Screening request from {sender} with filters: {msg.filters.model_dump(exclude_none=True)}")

    try:
        result = await screening_service.run_screening(msg, msg.correlation_context)
        await ctx.send(sender, result)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        error_resp = ErrorResponse(
            error=str(e),
            code="VALIDATION_ERROR",
            details=e.details,
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)
    except MarketDataError as e:
        logger.error(f"Market data error: {e}")
        error_resp = ErrorResponse(
            error=str(e),
            code="MARKET_DATA_ERROR",
            details=e.details,
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)
    except Exception as e:
        logger.error(f"Screening error: {e}")
        error_resp = ErrorResponse(
            error=f"Screening failed: {str(e)}",
            code="SCREENING_ERROR",
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)


# ============================================================================
# Startup/Shutdown
# ============================================================================

@quant_screener.on_event("startup")
async def startup(ctx: Context):
    """Agent startup."""
    logger.info(f"QuantScreener started at {quant_screener.address}")
    logger.info(f"Universe size: {len(config.default_universe)}")
    logger.info(f"Max concurrent fetches: {config.max_concurrent_fetches}")


@quant_screener.on_event("shutdown")
async def shutdown(ctx: Context):
    """Agent shutdown."""
    logger.info("QuantScreener shutting down")


# Include protocol
quant_screener.include(quant_screener_protocol)


if __name__ == "__main__":
    quant_screener.run()