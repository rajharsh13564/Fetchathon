"""Agent communication protocols for FinancePilot AI."""
from uagents import Protocol
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse
from schemas.screening import ScreeningRequest, RankedShortlistResponse
from schemas.research import ResearchRequest, AgenticThesisResponse
from schemas.chat import ChatRequest, ChatResponse
from schemas.common import ErrorResponse


# Protocol names
ORCHESTRATOR_PROTOCOL = "finpilot.orchestrator.v1"
QUANT_SCREENER_PROTOCOL = "finpilot.quant_screener.v1"
RISK_MANAGER_PROTOCOL = "finpilot.risk_manager.v1"
DEEP_RESEARCHER_PROTOCOL = "finpilot.deep_researcher.v1"
CHAT_PROTOCOL = "finpilot.chat.v1"


# Orchestrator Protocol - receives chat requests, coordinates other agents
orchestrator_protocol = Protocol(name=ORCHESTRATOR_PROTOCOL, version="1.0.0")

# Quant Screener Protocol - receives screening requests, returns ranked results
quant_screener_protocol = Protocol(name=QUANT_SCREENER_PROTOCOL, version="1.0.0")

# Risk Manager Protocol - receives portfolio, returns risk analysis
risk_manager_protocol = Protocol(name=RISK_MANAGER_PROTOCOL, version="1.0.0")

# Deep Researcher Protocol - receives research requests, returns thesis
deep_researcher_protocol = Protocol(name=DEEP_RESEARCHER_PROTOCOL, version="1.0.0")

# Chat Protocol - for direct chat with orchestrator
chat_protocol = Protocol(name=CHAT_PROTOCOL, version="1.0.0")


# Message type mappings for each protocol
ORCHESTRATOR_MESSAGES = {
    "chat_request": ChatRequest,
    "chat_response": ChatResponse,
    "portfolio_analysis_request": PortfolioInput,
    "portfolio_analysis_response": PortfolioAnalysisResponse,
    "screening_request": ScreeningRequest,
    "screening_response": RankedShortlistResponse,
    "research_request": ResearchRequest,
    "research_response": AgenticThesisResponse,
    "error": ErrorResponse,
}

QUANT_SCREENER_MESSAGES = {
    "screening_request": ScreeningRequest,
    "screening_response": RankedShortlistResponse,
    "error": ErrorResponse,
}

RISK_MANAGER_MESSAGES = {
    "risk_analysis_request": PortfolioInput,
    "risk_analysis_response": PortfolioAnalysisResponse,  # Reuse portfolio response with risk focus
    "error": ErrorResponse,
}

DEEP_RESEARCHER_MESSAGES = {
    "research_request": ResearchRequest,
    "research_response": AgenticThesisResponse,
    "error": ErrorResponse,
}

CHAT_MESSAGES = {
    "chat_request": ChatRequest,
    "chat_response": ChatResponse,
    "error": ErrorResponse,
}