"""Orchestrator-specific message schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import uuid4
from schemas.common import CorrelationContext, AgentStatus
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse
from schemas.screening import ScreeningRequest, RankedShortlistResponse
from schemas.research import ResearchRequest, AgenticThesisResponse
from schemas.chat import ChatRequest, ChatResponse


class OrchestratorStatus(BaseModel):
    """Orchestrator agent status."""
    status: AgentStatus = AgentStatus.HEALTHY
    downstream_agents: Dict[str, AgentStatus] = Field(default_factory=dict)
    active_requests: int = 0
    last_activity: Optional[float] = None


class AgentCoordinationRequest(BaseModel):
    """Request to coordinate with downstream agents."""
    request_type: str  # "portfolio_analysis", "screening", "research", "risk_analysis"
    payload: Dict[str, Any]
    target_agents: List[str] = Field(default_factory=list)
    correlation_context: CorrelationContext
    timeout_seconds: int = 30


class AgentCoordinationResponse(BaseModel):
    """Response from agent coordination."""
    request_type: str
    results: Dict[str, Any] = Field(default_factory=dict)
    errors: Dict[str, str] = Field(default_factory=dict)
    completed_agents: List[str] = Field(default_factory=list)
    failed_agents: List[str] = Field(default_factory=list)
    correlation_context: CorrelationContext


class OrchestratorConfig(BaseModel):
    """Configuration for orchestrator agent."""
    gemini_enabled: bool = True
    default_timeout: int = 30
    max_concurrent_requests: int = 10
    quant_screener_address: Optional[str] = None
    risk_manager_address: Optional[str] = None
    deep_researcher_address: Optional[str] = None
    enable_agent_communication: bool = False  # Set true when agents are deployed