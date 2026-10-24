"""QuantScreener-specific message schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from schemas.common import CorrelationContext, AgentStatus
from schemas.screening import ScreeningRequest, RankedShortlistResponse, ScreeningFilters


class QuantScreenerStatus(BaseModel):
    """QuantScreener agent status."""
    status: AgentStatus = AgentStatus.HEALTHY
    universe_size: int = 0
    last_screening: Optional[float] = None
    cache_stats: Dict[str, int] = Field(default_factory=dict)


class QuantScreenerConfig(BaseModel):
    """Configuration for QuantScreener agent."""
    default_universe: List[str] = Field(default_factory=list)
    max_concurrent_fetches: int = 10
    default_max_results: int = 20
    enable_caching: bool = True
    cache_ttl_seconds: int = 60