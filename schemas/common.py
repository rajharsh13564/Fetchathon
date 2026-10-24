from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
from uuid import uuid4


class InvestmentHorizon(str, Enum):
    """Investment time horizon options."""
    SHORT = "short"      # < 1 year
    MEDIUM = "medium"    # 1-3 years
    LONG = "long"        # > 3 years


class RiskProfile(str, Enum):
    """Risk tolerance profiles."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class AgentStatus(str, Enum):
    """Agent operational status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    code: str
    details: Optional[dict] = None
    request_id: str = Field(default_factory=lambda: str(uuid4()))


class CorrelationContext(BaseModel):
    """Context for correlating related messages across agents."""
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: float = Field(default_factory=lambda: __import__('time').time())

    def with_new_request_id(self) -> "CorrelationContext":
        """Create new context with new request ID but same conversation."""
        return CorrelationContext(
            request_id=str(uuid4()),
            conversation_id=self.conversation_id,
            user_id=self.user_id,
        )


class AgentInfo(BaseModel):
    """Information about an agent."""
    name: str
    address: str
    status: AgentStatus = AgentStatus.HEALTHY
    capabilities: list[str] = Field(default_factory=list)
    last_seen: Optional[float] = None


class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool