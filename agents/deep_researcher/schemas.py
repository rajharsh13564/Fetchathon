"""DeepResearcher-specific message schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from schemas.common import CorrelationContext, AgentStatus
from schemas.research import ResearchRequest, AgenticThesisResponse


class DeepResearcherStatus(BaseModel):
    """DeepResearcher agent status."""
    status: AgentStatus = AgentStatus.HEALTHY
    model: str = "gemini-1.5-flash"
    last_research: Optional[float] = None
    requests_served: int = 0


class DeepResearcherConfig(BaseModel):
    """Configuration for DeepResearcher agent."""
    model: str = "gemini-1.5-flash"
    max_retries: int = 3
    timeout_seconds: int = 60
    temperature: float = 0.3
    max_tokens: int = 8192