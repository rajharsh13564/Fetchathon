"""Chat API endpoints."""
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from config.settings import get_settings, Settings
from backend.dependencies import get_settings_dep, get_correlation_context
from schemas.chat import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse
from schemas.screening import ScreeningRequest, RankedShortlistResponse
from schemas.research import ResearchRequest, AgenticThesisResponse
from schemas.common import CorrelationContext
from services.portfolio_service import get_portfolio_service
from services.screening_service import get_screening_service
from services.research_service import get_research_service
from services.gemini_client import get_gemini_client
from services.report_service import get_report_service
from shared.errors import ConfigurationError, ValidationError

router = APIRouter(prefix="/api", tags=["chat"])

# In-memory conversation storage (use Redis in production)
conversations: dict[str, ConversationHistory] = {}


class ChatRequestAPI(BaseModel):
    """API chat request."""
    message: str
    conversation_id: Optional[str] = None
    portfolio_context: Optional[dict] = None
    investment_horizon: Optional[str] = None
    risk_profile: Optional[str] = None


class PortfolioAnalysisRequestAPI(BaseModel):
    """API portfolio analysis request."""
    holdings: list[dict]
    investment_horizon: str = "medium"
    risk_profile: str = "moderate"


class ScreeningRequestAPI(BaseModel):
    """API screening request."""
    filters: dict = {}
    max_results: int = 20


class ResearchRequestAPI(BaseModel):
    """API research request."""
    ticker: str
    company_name: Optional[str] = None
    include_quant_data: Optional[dict] = None
    investment_horizon: str = "medium"
    risk_profile: str = "moderate"


def classify_request(message: str) -> dict:
    """Classify user request."""
    message_lower = message.lower()

    portfolio_keywords = [
        "portfolio", "holdings", "my stocks", "analyze my", "my investments",
        "profit", "loss", "pnl", "gain", "worth", "value", "shares",
        "bought", "purchased", "invested",
    ]

    screening_keywords = [
        "screen", "find stocks", "stocks under", "stocks below", "filter",
        "undervalued", "low pe", "high growth", "momentum", "52 week",
        "screener", "scan",
    ]

    research_keywords = [
        "research", "analyze", "bull case", "bear case", "thesis",
        "fundamental", "deep dive", "company analysis", "should i buy",
        "investment case", "pros and cons",
    ]

    risk_keywords = [
        "risk", "concentration", "diversification", "volatile", "drawdown",
        "correlation", "sector exposure",
    ]

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

    action = max(scores, key=scores.get)
    confidence = scores[action] / max(sum(scores.values()), 1)

    if any(word in message_lower for word in ["shares", "bought at", "purchased at", "@"]):
        if scores["portfolio_analysis"] > 0 or scores["education"] == 0:
            action = "portfolio_analysis"
            confidence = 0.9

    return {
        "action": action,
        "confidence": confidence,
        "scores": scores,
    }


async def generate_chat_response(
    message: str,
    history: ConversationHistory,
    settings: Settings,
    correlation_context: CorrelationContext,
) -> ChatResponse:
    """Generate chat response using Gemini or fallback."""
    gemini_client = get_gemini_client()

    if not gemini_client or not settings.validate_gemini_key():
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
                conversation_id=history.conversation_id,
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
                conversation_id=history.conversation_id,
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
            conversation_id=history.conversation_id,
            message_type="text",
            correlation_context=correlation_context,
        )

    # Build context for Gemini
    history_text = ""
    for msg in history.messages[-6:]:
        history_text += f"{msg.role}: {msg.content}\n"

    system_prompt = settings.finpilot_system_prompt

    prompt = f"""
Conversation History:
{history_text}

User's Latest Message: {message}

Portfolio Context: {history.portfolio_context}

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

        suggested_actions = []
        if "portfolio" in response_text.lower() and "analyze" in response_text.lower():
            suggested_actions.append("portfolio_analysis")
        if "screen" in response_text.lower() or "find stocks" in response_text.lower():
            suggested_actions.append("screening")
        if "research" in response_text.lower() or "analyze" in response_text.lower():
            suggested_actions.append("research")

        return ChatResponse(
            message=response_text,
            conversation_id=history.conversation_id,
            message_type="text",
            metadata={"classification": classify_request(message)},
            correlation_context=correlation_context,
            suggested_actions=suggested_actions,
        )
    except Exception as e:
        return ChatResponse(
            message=f"I encountered an error: {str(e)}. Please try again.",
            conversation_id=history.conversation_id,
            message_type="error",
            correlation_context=correlation_context,
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequestAPI,
    background_tasks: BackgroundTasks,
    correlation_context: CorrelationContext = Depends(get_correlation_context),
    settings: Settings = Depends(get_settings_dep),
):
    """Main chat endpoint for natural language interaction."""
    # Get or create conversation
    conv_id = request.conversation_id or correlation_context.conversation_id
    if not conv_id:
        import uuid
        conv_id = str(uuid.uuid4())

    if conv_id not in conversations:
        conversations[conv_id] = ConversationHistory(
            conversation_id=conv_id,
            portfolio_context=request.portfolio_context,
        )

    history = conversations[conv_id]

    # Add user message
    history.messages.append(ChatMessage(role="user", content=request.message))
    history.updated_at = __import__('datetime').datetime.now()

    # Update correlation context
    correlation_context.conversation_id = conv_id

    # Generate response
    response = await generate_chat_response(
        message=request.message,
        history=history,
        settings=settings,
        correlation_context=correlation_context,
    )

    # Add assistant message
    history.messages.append(ChatMessage(
        role="assistant",
        content=response.message,
        message_type=response.message_type,
        metadata=response.metadata,
    ))

    return response


@router.post("/portfolio/analyze", response_model=PortfolioAnalysisResponse)
async def analyze_portfolio_endpoint(
    request: PortfolioAnalysisRequestAPI,
    correlation_context: CorrelationContext = Depends(get_correlation_context),
    settings: Settings = Depends(get_settings_dep),
):
    """Analyze portfolio with current market data."""
    try:
        # Convert holdings
        holdings = []
        for h in request.holdings:
            holdings.append({
                "ticker": h["ticker"],
                "shares": h["shares"],
                "avg_purchase_price": h["avg_purchase_price"],
                "purchase_date": h.get("purchase_date"),
            })

        portfolio_input = PortfolioInput(
            holdings=holdings,
            investment_horizon=request.investment_horizon,
            risk_profile=request.risk_profile,
            correlation_context=correlation_context,
        )

        portfolio_service = get_portfolio_service()
        result = await portfolio_service.analyze_portfolio(portfolio_input, correlation_context)
        return result

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        # Check if it's a Pydantic validation error
        if "validation" in str(e).lower() or "ValidationError" in type(e).__name__:
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/screening/run", response_model=RankedShortlistResponse)
async def run_screening_endpoint(
    request: ScreeningRequestAPI,
    correlation_context: CorrelationContext = Depends(get_correlation_context),
    settings: Settings = Depends(get_settings_dep),
):
    """Run quantitative screening."""
    try:
        from schemas.screening import ScreeningFilters

        filters = ScreeningFilters(**request.filters)
        screening_request = ScreeningRequest(
            filters=filters,
            max_results=request.max_results,
            correlation_context=correlation_context,
        )

        screening_service = get_screening_service()
        result = await screening_service.run_screening(screening_request, correlation_context)
        return result

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research/run", response_model=AgenticThesisResponse)
async def run_research_endpoint(
    request: ResearchRequestAPI,
    correlation_context: CorrelationContext = Depends(get_correlation_context),
    settings: Settings = Depends(get_settings_dep),
):
    """Run deep research on a company."""
    if not settings.validate_gemini_key():
        raise HTTPException(
            status_code=503,
            detail="Gemini API not configured. Set GEMINI_API_KEY in environment.",
        )

    try:
        from schemas.common import InvestmentHorizon, RiskProfile

        research_request = ResearchRequest(
            ticker=request.ticker,
            company_name=request.company_name,
            include_quant_data=request.include_quant_data,
            investment_horizon=InvestmentHorizon(request.investment_horizon),
            risk_profile=RiskProfile(request.risk_profile),
            correlation_context=correlation_context,
        )

        research_service = get_research_service()
        result = await research_service.research_company(research_request, correlation_context)
        return result

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversations[conversation_id]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete conversation history."""
    if conversation_id in conversations:
        del conversations[conversation_id]
    return {"status": "deleted"}