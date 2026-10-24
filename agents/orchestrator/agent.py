"""FinPilot Orchestrator Agent - Central coordinator for FinancePilot AI."""
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.models import Model

from config.settings import get_settings
from config.logging_config import setup_logging, get_logger
from schemas.common import (
    CorrelationContext,
    ErrorResponse,
    InvestmentHorizon,
    RiskProfile,
    AgentStatus,
)
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse
from schemas.screening import ScreeningRequest, RankedShortlistResponse, ScreeningFilters
from schemas.research import ResearchRequest, AgenticThesisResponse
from schemas.chat import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from agents.orchestrator.schemas import (
    OrchestratorConfig,
    OrchestratorStatus,
    AgentCoordinationRequest,
    AgentCoordinationResponse,
)
from agents.risk_manager.schemas import RiskAnalysisRequest, RiskAnalysisResponse
from services.portfolio_service import get_portfolio_service
from services.gemini_client import get_gemini_client
from services.report_service import get_report_service
from shared.errors import (
    ConfigurationError,
    AgentUnavailableError,
    AgentCommunicationError,
    ValidationError,
    GeminiAPIError,
)
from shared.protocol import (
    ORCHESTRATOR_PROTOCOL,
    CHAT_PROTOCOL,
    QUANT_SCREENER_PROTOCOL,
    RISK_MANAGER_PROTOCOL,
    DEEP_RESEARCHER_PROTOCOL,
)

setup_logging()
logger = get_logger(__name__)

settings = get_settings()

# Create orchestrator agent
orchestrator = Agent(
    name="finpilot-orchestrator",
    seed=settings.orchestrator_seed,
    port=8001,
    mailbox=settings.orchestrator_mailbox_key,
)

# Protocols
orchestrator_protocol = Protocol(name=ORCHESTRATOR_PROTOCOL, version="1.0.0")
chat_protocol = Protocol(name=CHAT_PROTOCOL, version="1.0.0")

# Service instances
portfolio_service = get_portfolio_service()
gemini_client = get_gemini_client()
report_service = get_report_service()

# Configuration
config = OrchestratorConfig(
    gemini_enabled=settings.validate_gemini_key(),
    quant_screener_address=settings.quant_screener_address,
    risk_manager_address=settings.risk_manager_address,
    deep_researcher_address=settings.deep_researcher_address,
    enable_agent_communication=bool(
        settings.quant_screener_address
        and settings.risk_manager_address
        and settings.deep_researcher_address
    ),
)

# In-memory state
conversation_histories: Dict[str, ConversationHistory] = {}
active_requests: Dict[str, Dict[str, Any]] = {}
agent_statuses: Dict[str, AgentStatus] = {
    "quant_screener": AgentStatus.UNAVAILABLE,
    "risk_manager": AgentStatus.UNAVAILABLE,
    "deep_researcher": AgentStatus.UNAVAILABLE,
}


# ============================================================================
# Helper Functions
# ============================================================================

def classify_request(message: str) -> Dict[str, Any]:
    """
    Classify user request into action type.
    Returns dict with action, confidence, and extracted info.
    """
    message_lower = message.lower()

    # Portfolio analysis keywords
    portfolio_keywords = [
        "portfolio", "holdings", "my stocks", "analyze my", "my investments",
        "profit", "loss", "pnl", "gain", "worth", "value", "shares",
        "bought", "purchased", "invested",
    ]

    # Screening keywords
    screening_keywords = [
        "screen", "find stocks", "stocks under", "stocks below", "filter",
        "undervalued", "low pe", "high growth", "momentum", "52 week",
        "screener", "scan",
    ]

    # Research keywords
    research_keywords = [
        "research", "analyze", "bull case", "bear case", "thesis",
        "fundamental", "deep dive", "company analysis", "should i buy",
        "investment case", "pros and cons",
    ]

    # Risk keywords
    risk_keywords = [
        "risk", "concentration", "diversification", "volatile", "drawdown",
        "correlation", "sector exposure",
    ]

    # Education keywords
    education_keywords = [
        "what is", "explain", "define", "meaning", "how does",
        "difference between", "compare", "vs", "versus",
        "pe ratio", "p/e", "eps", "market cap", "dividend",
    ]

    scores = {
        "portfolio_analysis": sum(1 for k in portfolio_keywords if k in message_lower),
        "screening": sum(1 for k in screening_keywords if k in message_lower),
        "research": sum(1 for k in research_keywords if k in message_lower),
        "risk_analysis": sum(1 for k in risk_keywords if k in message_lower),
        "education": sum(1 for k in education_keywords if k in message_lower),
    }

    # Determine primary action
    action = max(scores, key=scores.get)
    confidence = scores[action] / max(sum(scores.values()), 1)

    # Override for explicit portfolio mentions with numbers
    if any(word in message_lower for word in ["shares", "bought at", "purchased at", "@"]):
        if scores["portfolio_analysis"] > 0 or scores["education"] == 0:
            action = "portfolio_analysis"
            confidence = 0.9

    return {
        "action": action,
        "confidence": confidence,
        "scores": scores,
    }


async def extract_portfolio_from_text(text: str) -> Optional[PortfolioInput]:
    """Extract portfolio from natural language using portfolio service."""
    return portfolio_service.extract_portfolio_from_text(text)


async def generate_chat_response(
    message: str,
    conversation_history: ConversationHistory,
    portfolio_context: Optional[Dict[str, Any]] = None,
) -> ChatResponse:
    """Generate conversational response using Gemini."""
    correlation_context = CorrelationContext(conversation_id=conversation_history.conversation_id)

    if not gemini_client or not config.gemini_enabled:
        # Fallback response without Gemini
        classification = classify_request(message)

        if classification["action"] == "portfolio_analysis":
            return ChatResponse(
                message=(
                    "I'd be happy to analyze your portfolio! Please provide your holdings in this format:\n\n"
                    "**Example:**\n"
                    "• 10 RELIANCE.NS shares bought at ₹2,450\n"
                    "• 5 TCS.NS shares bought at ₹3,800\n\n"
                    "Also let me know your investment horizon (short/medium/long) and risk profile (conservative/moderate/aggressive)."
                ),
                conversation_id=conversation_history.conversation_id,
                message_type="clarification",
                requires_clarification=True,
                clarification_questions=[
                    "What are your holdings (ticker, shares, purchase price)?",
                    "What is your investment horizon?",
                    "What is your risk profile?",
                ],
                correlation_context=correlation_context,
            )

        elif classification["action"] == "education":
            return ChatResponse(
                message=(
                    "I can explain financial concepts! However, I need a Gemini API key to provide detailed explanations. "
                    "Please configure GEMINI_API_KEY in your .env file for full AI-powered responses.\n\n"
                    "In the meantime, I can help with:\n"
                    "• Portfolio analysis (deterministic calculations)\n"
                    "• Quantitative screening (rule-based)\n"
                    "• Risk metrics (concentration, weights)"
                ),
                conversation_id=conversation_history.conversation_id,
                message_type="text",
                correlation_context=correlation_context,
            )

        return ChatResponse(
            message=(
                "I'm FinancePilot AI, your financial research assistant. I can help with:\n\n"
                "📊 **Portfolio Analysis** - Share your holdings and I'll calculate P&L, weights, concentration\n"
                "🔍 **Stock Screening** - Find stocks matching quantitative criteria\n"
                "📈 **Deep Research** - Get bull/bear cases and fundamental analysis\n"
                "⚠️ **Risk Analysis** - Concentration, diversification, volatility\n"
                "💬 **Financial Education** - Explain concepts like P/E, market cap, etc.\n\n"
                "How can I help you today?"
            ),
            conversation_id=conversation_history.conversation_id,
            message_type="text",
            correlation_context=correlation_context,
        )

    # Build context for Gemini
    history_text = ""
    for msg in conversation_history.messages[-6:]:  # Last 6 messages
        history_text += f"{msg.role}: {msg.content}\n"

    system_prompt = settings.finpilot_system_prompt

    prompt = f"""
Conversation History:
{history_text}

User's Latest Message: {message}

Portfolio Context: {json.dumps(portfolio_context) if portfolio_context else 'None'}

Respond naturally and helpfully. If the user asks for portfolio analysis but hasn't provided holdings, ask for them.
If they ask for education, explain clearly. If they want screening/research, ask for specifics.
Keep responses concise but complete.
"""

    try:
        response_text = await gemini_client.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=2048,
        )

        # Check if response suggests an action
        suggested_actions = []
        if "portfolio" in response_text.lower() and "analyze" in response_text.lower():
            suggested_actions.append("portfolio_analysis")
        if "screen" in response_text.lower() or "find stocks" in response_text.lower():
            suggested_actions.append("screening")
        if "research" in response_text.lower() or "analyze" in response_text.lower():
            suggested_actions.append("research")

        return ChatResponse(
            message=response_text,
            conversation_id=conversation_history.conversation_id,
            message_type="text",
            metadata={"classification": classify_request(message)},
            correlation_context=correlation_context,
            suggested_actions=suggested_actions,
        )
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        return ChatResponse(
            message=f"I encountered an error: {str(e)}. Please try again.",
            conversation_id=conversation_history.conversation_id,
            message_type="error",
            correlation_context=correlation_context,
        )


async def send_to_agent(
    ctx: Context,
    agent_address: str,
    message: Model,
    timeout: int = 30,
) -> Optional[Model]:
    """Send message to another agent and wait for response."""
    if not agent_address:
        return None

    try:
        response = await ctx.send(agent_address, message, timeout=timeout)
        return response
    except asyncio.TimeoutError:
        logger.error(f"Timeout sending to {agent_address}")
        raise AgentCommunicationError(agent_address, "Timeout")
    except Exception as e:
        logger.error(f"Error sending to {agent_address}: {e}")
        raise AgentCommunicationError(agent_address, str(e))


async def _send_and_validate(
    ctx: Context,
    agent_name: str,
    agent_address: str,
    request: Model,
    expected_response_type: type,
    timeout: int = 30,
    correlation_context: Optional[CorrelationContext] = None,
) -> Optional[Model]:
    """
    Send a request to a downstream agent and validate the response.
    Returns the validated response or None on failure.
    """
    if not agent_address:
        logger.warning(f"{agent_name} address not configured")
        return None

    try:
        response = await send_to_agent(ctx, agent_address, request, timeout=timeout)
        if response is None:
            logger.warning(f"{agent_name} returned no response")
            return None
        
        # Validate response type
        if not isinstance(response, expected_response_type):
            logger.error(
                f"{agent_name} returned unexpected type: "
                f"expected {expected_response_type.__name__}, got {type(response).__name__}"
            )
            return None
        
        logger.info(f"{agent_name} responded successfully")
        return response
        
    except AgentCommunicationError as e:
        logger.error(f"{agent_name} communication error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error communicating with {agent_name}: {e}")
        return None


async def coordinate_agents(
    ctx: Context,
    request_type: str,
    payload: Dict[str, Any],
    correlation_context: CorrelationContext,
) -> AgentCoordinationResponse:
    """Coordinate with downstream agents via genuine inter-agent communication."""
    results = {}
    errors = {}
    completed = []
    failed = []

    # Portfolio analysis - always done locally
    if request_type == "portfolio_analysis":
        try:
            portfolio_input = PortfolioInput(**payload)
            result = await portfolio_service.analyze_portfolio(portfolio_input, correlation_context)
            results["portfolio_analysis"] = result.model_dump(mode="json")
            completed.append("portfolio_analysis")
        except Exception as e:
            errors["portfolio_analysis"] = str(e)
            failed.append("portfolio_analysis")

    # Screening - via QuantScreener agent
    if request_type in ("screening", "full_analysis"):
        if config.enable_agent_communication and config.quant_screener_address:
            try:
                screening_request = ScreeningRequest(**payload)
                response = await _send_and_validate(
                    ctx=ctx,
                    agent_name="quant_screener",
                    agent_address=config.quant_screener_address,
                    request=screening_request,
                    expected_response_type=RankedShortlistResponse,
                    timeout=30,
                    correlation_context=correlation_context,
                )
                if response:
                    results["screening"] = response.model_dump(mode="json")
                    completed.append("screening")
                else:
                    errors["screening"] = "QuantScreener agent returned no valid response"
                    failed.append("screening")
            except Exception as e:
                errors["screening"] = str(e)
                failed.append("screening")
        elif not config.enable_agent_communication:
            # Fallback to local service when agent communication is disabled
            try:
                from services.screening_service import get_screening_service
                screening_service = get_screening_service()
                screening_request = ScreeningRequest(**payload)
                result = await screening_service.run_screening(screening_request, correlation_context)
                results["screening"] = result.model_dump(mode="json")
                completed.append("screening")
            except Exception as e:
                errors["screening"] = str(e)
                failed.append("screening")

    # Research - via DeepResearcher agent
    if request_type in ("research", "full_analysis"):
        if config.enable_agent_communication and config.deep_researcher_address:
            try:
                research_request = ResearchRequest(**payload)
                response = await _send_and_validate(
                    ctx=ctx,
                    agent_name="deep_researcher",
                    agent_address=config.deep_researcher_address,
                    request=research_request,
                    expected_response_type=AgenticThesisResponse,
                    timeout=60,  # Research takes longer
                    correlation_context=correlation_context,
                )
                if response:
                    results["research"] = response.model_dump(mode="json")
                    completed.append("research")
                else:
                    errors["research"] = "DeepResearcher agent returned no valid response"
                    failed.append("research")
            except Exception as e:
                errors["research"] = str(e)
                failed.append("research")
        elif not config.enable_agent_communication and gemini_client:
            # Fallback to local service when agent communication is disabled
            try:
                from services.research_service import get_research_service
                research_service = get_research_service()
                research_request = ResearchRequest(**payload)
                result = await research_service.research_company(research_request, correlation_context)
                results["research"] = result.model_dump(mode="json")
                completed.append("research")
            except Exception as e:
                errors["research"] = str(e)
                failed.append("research")
        elif not gemini_client:
            errors["research"] = "Gemini not configured and no remote DeepResearcher available"
            failed.append("research")

    # Risk Analysis - via RiskManager agent
    if request_type in ("risk_analysis", "full_analysis"):
        if config.enable_agent_communication and config.risk_manager_address:
            try:
                risk_request = RiskAnalysisRequest(**payload)
                response = await _send_and_validate(
                    ctx=ctx,
                    agent_name="risk_manager",
                    agent_address=config.risk_manager_address,
                    request=risk_request,
                    expected_response_type=RiskAnalysisResponse,
                    timeout=60,  # Risk analysis takes longer
                    correlation_context=correlation_context,
                )
                if response:
                    results["risk_analysis"] = response.model_dump(mode="json")
                    completed.append("risk_analysis")
                else:
                    errors["risk_analysis"] = "RiskManager agent returned no valid response"
                    failed.append("risk_analysis")
            except Exception as e:
                errors["risk_analysis"] = str(e)
                failed.append("risk_analysis")
        elif not config.enable_agent_communication:
            # Fallback to local portfolio service for basic risk metrics
            try:
                portfolio_input = PortfolioInput(**payload)
                # Use portfolio service which includes basic risk metrics
                result = await portfolio_service.analyze_portfolio(portfolio_input, correlation_context)
                results["risk_analysis"] = {
                    "portfolio_snapshot": result.model_dump(mode="json"),
                    "note": "Full risk analysis requires RiskManager agent"
                }
                completed.append("risk_analysis")
            except Exception as e:
                errors["risk_analysis"] = str(e)
                failed.append("risk_analysis")

    return AgentCoordinationResponse(
        request_type=request_type,
        results=results,
        errors=errors,
        completed_agents=completed,
        failed_agents=failed,
        correlation_context=correlation_context,
    )


# ============================================================================
# Message Handlers
# ============================================================================

@chat_protocol.on_message(model=ChatRequest, replies=ChatResponse)
async def handle_chat_request(ctx: Context, sender: str, msg: ChatRequest):
    """Handle incoming chat request."""
    logger.info(f"Chat request from {sender}: {msg.message[:100]}")

    # Get or create conversation history
    conv_id = msg.get_or_create_conversation_id()
    if conv_id not in conversation_histories:
        conversation_histories[conv_id] = ConversationHistory(
            conversation_id=conv_id,
            portfolio_context=msg.portfolio_context,
        )

    history = conversation_histories[conv_id]
    history.messages.append(ChatMessage(role="user", content=msg.message))
    history.updated_at = datetime.now()

    # Generate response
    response = await generate_chat_response(
        message=msg.message,
        conversation_history=history,
        portfolio_context=msg.portfolio_context,
    )

    # Add to history
    history.messages.append(ChatMessage(
        role="assistant",
        content=response.message,
        message_type=response.message_type,
        metadata=response.metadata,
    ))

    # Check if we need to trigger analysis
    classification = classify_request(msg.message)

    if classification["action"] == "portfolio_analysis" and classification["confidence"] > 0.7:
        # Try to extract portfolio
        portfolio = await extract_portfolio_from_text(msg.message)
        if portfolio:
            # Run analysis
            try:
                analysis = await portfolio_service.analyze_portfolio(
                    portfolio, msg.correlation_context
                )
                report = report_service.generate_portfolio_report(analysis)
                response.message += f"\n\n---\n\n{report}"
                response.message_type = "portfolio_analysis"
                response.metadata["portfolio_analysis"] = analysis.model_dump(mode="json")
            except Exception as e:
                logger.error(f"Portfolio analysis error: {e}")
                response.message += f"\n\n⚠️ Analysis failed: {str(e)}"

    elif classification["action"] == "screening" and classification["confidence"] > 0.6:
        response.message += "\n\n💡 For stock screening, please use the screening interface or specify criteria like: 'Find stocks with P/E under 15 and market cap over 10000 crores'"

    elif classification["action"] == "research" and classification["confidence"] > 0.6:
        # Try to extract ticker from message for research
        import re
        ticker_match = re.search(r'\b([A-Z]{2,10}(?:\.NS|\.BO)?)\b', msg.message.upper())
        if ticker_match:
            ticker = ticker_match.group(1)
            if not (ticker.endswith(".NS") or ticker.endswith(".BO")):
                ticker = f"{ticker}.NS"
            
            # Trigger research via coordinate_agents
            try:
                research_payload = {
                    "ticker": ticker,
                    "investment_horizon": "medium",
                    "risk_profile": "moderate",
                    "correlation_context": msg.correlation_context.model_dump(),
                }
                coordination = await coordinate_agents(
                    ctx=ctx,
                    request_type="research",
                    payload=research_payload,
                    correlation_context=msg.correlation_context,
                )
                if "research" in coordination.results:
                    research_data = coordination.results["research"]
                    response.message += f"\n\n📊 **Research for {ticker}:**\n"
                    response.message += f"Bull: {research_data.get('bull_thesis', {}).get('content', 'N/A')[:200]}...\n"
                    response.message += f"Bear: {research_data.get('bear_thesis', {}).get('content', 'N/A')[:200]}..."
                    response.message_type = "research_report"
                    response.metadata["research"] = research_data
                elif coordination.errors.get("research"):
                    response.message += f"\n\n⚠️ Research unavailable: {coordination.errors['research']}"
            except Exception as e:
                logger.error(f"Research coordination error: {e}")
                response.message += f"\n\n⚠️ Research failed: {str(e)}"

    elif classification["action"] == "risk_analysis" and classification["confidence"] > 0.6:
        # Try to extract portfolio for risk analysis
        portfolio = await extract_portfolio_from_text(msg.message)
        if portfolio:
            try:
                risk_payload = {
                    "portfolio": portfolio.model_dump(mode="json"),
                    "include_historical": True,
                    "lookback_days": 252,
                    "correlation_context": msg.correlation_context.model_dump(),
                }
                coordination = await coordinate_agents(
                    ctx=ctx,
                    request_type="risk_analysis",
                    payload=risk_payload,
                    correlation_context=msg.correlation_context,
                )
                if "risk_analysis" in coordination.results:
                    risk_data = coordination.results["risk_analysis"]
                    response.message += f"\n\n⚠️ **Risk Analysis:**\n"
                    if "overall_risk_score" in risk_data:
                        response.message += f"Overall Risk Score: {risk_data['overall_risk_score']}/100 ({risk_data.get('risk_level', 'N/A')})\n"
                    if "recommendations" in risk_data:
                        for rec in risk_data["recommendations"][:3]:
                            response.message += f"• {rec}\n"
                    response.message_type = "risk_analysis"
                    response.metadata["risk_analysis"] = risk_data
                elif coordination.errors.get("risk_analysis"):
                    response.message += f"\n\n⚠️ Risk analysis unavailable: {coordination.errors['risk_analysis']}"
            except Exception as e:
                logger.error(f"Risk coordination error: {e}")
                response.message += f"\n\n⚠️ Risk analysis failed: {str(e)}"

    await ctx.send(sender, response)


@orchestrator_protocol.on_message(model=PortfolioInput, replies=PortfolioAnalysisResponse)
async def handle_portfolio_analysis(ctx: Context, sender: str, msg: PortfolioInput):
    """Handle portfolio analysis request."""
    logger.info(f"Portfolio analysis request from {sender} with {len(msg.holdings)} holdings")

    try:
        result = await portfolio_service.analyze_portfolio(msg, msg.correlation_context)
        await ctx.send(sender, result)
    except Exception as e:
        logger.error(f"Portfolio analysis error: {e}")
        error_resp = ErrorResponse(
            error=str(e),
            code="PORTFOLIO_ANALYSIS_ERROR",
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)


@orchestrator_protocol.on_message(model=ScreeningRequest, replies=RankedShortlistResponse)
async def handle_screening_request(ctx: Context, sender: str, msg: ScreeningRequest):
    """Handle screening request - delegate to QuantScreener agent if available."""
    logger.info(f"Screening request from {sender}")

    if config.enable_agent_communication and config.quant_screener_address:
        # Delegate to QuantScreener agent
        response = await _send_and_validate(
            ctx=ctx,
            agent_name="quant_screener",
            agent_address=config.quant_screener_address,
            request=msg,
            expected_response_type=RankedShortlistResponse,
            timeout=30,
            correlation_context=msg.correlation_context,
        )
        if response:
            await ctx.send(sender, response)
        else:
            error_resp = ErrorResponse(
                error="QuantScreener agent unavailable or returned invalid response",
                code="QUANT_SCREENER_UNAVAILABLE",
                request_id=msg.correlation_context.request_id,
            )
            await ctx.send(sender, error_resp)
    else:
        # Fallback to local service
        try:
            from services.screening_service import get_screening_service
            screening_service = get_screening_service()
            result = await screening_service.run_screening(msg, msg.correlation_context)
            await ctx.send(sender, result)
        except Exception as e:
            logger.error(f"Screening error: {e}")
            error_resp = ErrorResponse(
                error=str(e),
                code="SCREENING_ERROR",
                request_id=msg.correlation_context.request_id,
            )
            await ctx.send(sender, error_resp)


@orchestrator_protocol.on_message(model=ResearchRequest, replies=AgenticThesisResponse)
async def handle_research_request(ctx: Context, sender: str, msg: ResearchRequest):
    """Handle research request - delegate to DeepResearcher agent if available."""
    logger.info(f"Research request from {sender} for {msg.ticker}")

    if config.enable_agent_communication and config.deep_researcher_address:
        # Delegate to DeepResearcher agent
        response = await _send_and_validate(
            ctx=ctx,
            agent_name="deep_researcher",
            agent_address=config.deep_researcher_address,
            request=msg,
            expected_response_type=AgenticThesisResponse,
            timeout=60,
            correlation_context=msg.correlation_context,
        )
        if response:
            await ctx.send(sender, response)
        else:
            error_resp = ErrorResponse(
                error="DeepResearcher agent unavailable or returned invalid response",
                code="DEEP_RESEARCHER_UNAVAILABLE",
                request_id=msg.correlation_context.request_id,
            )
            await ctx.send(sender, error_resp)
    else:
        # Fallback to local service
        try:
            if not gemini_client:
                raise ConfigurationError("Gemini API key not configured")

            from services.research_service import get_research_service
            research_service = get_research_service()
            result = await research_service.research_company(msg, msg.correlation_context)
            await ctx.send(sender, result)
        except Exception as e:
            logger.error(f"Research error: {e}")
            error_resp = ErrorResponse(
                error=str(e),
                code="RESEARCH_ERROR",
                request_id=msg.correlation_context.request_id,
            )
            await ctx.send(sender, error_resp)


@orchestrator_protocol.on_message(model=RiskAnalysisRequest, replies=RiskAnalysisResponse)
async def handle_risk_analysis_request(ctx: Context, sender: str, msg: RiskAnalysisRequest):
    """Handle risk analysis request - delegate to RiskManager agent if available."""
    logger.info(f"Risk analysis request from {sender} for {len(msg.portfolio.holdings)} holdings")

    if config.enable_agent_communication and config.risk_manager_address:
        # Delegate to RiskManager agent
        response = await _send_and_validate(
            ctx=ctx,
            agent_name="risk_manager",
            agent_address=config.risk_manager_address,
            request=msg,
            expected_response_type=RiskAnalysisResponse,
            timeout=60,
            correlation_context=msg.correlation_context,
        )
        if response:
            await ctx.send(sender, response)
        else:
            error_resp = ErrorResponse(
                error="RiskManager agent unavailable or returned invalid response",
                code="RISK_MANAGER_UNAVAILABLE",
                request_id=msg.correlation_context.request_id,
            )
            await ctx.send(sender, error_resp)
    else:
        # Fallback to local portfolio service for basic risk metrics
        try:
            portfolio_analysis = await portfolio_service.analyze_portfolio(msg.portfolio, msg.correlation_context)
            # Return basic risk info wrapped in a compatible response
            fallback_response = RiskAnalysisResponse(
                portfolio_snapshot=portfolio_analysis,
                concentration_risk=msg.portfolio.model_dump() if hasattr(msg.portfolio, 'model_dump') else {},
                volatility_risk={"note": "Full risk analysis requires RiskManager agent"},
                correlation_risk={"note": "Full risk analysis requires RiskManager agent"},
                overall_risk_score=0.0,
                risk_level="Unknown",
                recommendations=["Configure RiskManager agent for full risk analysis"],
                correlation_context=msg.correlation_context,
            )
            await ctx.send(sender, fallback_response)
        except Exception as e:
            logger.error(f"Risk analysis error: {e}")
            error_resp = ErrorResponse(
                error=str(e),
                code="RISK_ANALYSIS_ERROR",
                request_id=msg.correlation_context.request_id,
            )
            await ctx.send(sender, error_resp)

@orchestrator.on_event("startup")
async def startup(ctx: Context):
    """Agent startup."""
    logger.info(f"Orchestrator started at {orchestrator.address}")
    logger.info(f"Gemini enabled: {config.gemini_enabled}")
    logger.info(f"Agent communication: {config.enable_agent_communication}")
    if config.enable_agent_communication:
        logger.info(f"Quant Screener: {config.quant_screener_address}")
        logger.info(f"Risk Manager: {config.risk_manager_address}")
        logger.info(f"Deep Researcher: {config.deep_researcher_address}")


@orchestrator.on_event("shutdown")
async def shutdown(ctx: Context):
    """Agent shutdown."""
    logger.info("Orchestrator shutting down")


# Include protocols
orchestrator.include(orchestrator_protocol)
orchestrator.include(chat_protocol)


if __name__ == "__main__":
    orchestrator.run()