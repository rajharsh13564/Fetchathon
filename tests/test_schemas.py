"""Test schemas validation and serialization."""
import pytest
from decimal import Decimal
from datetime import datetime

from schemas.common import (
    InvestmentHorizon,
    RiskProfile,
    AgentStatus,
    ErrorResponse,
    CorrelationContext,
)
from schemas.portfolio import (
    HoldingItem,
    PortfolioInput,
    HoldingSnapshot,
    PortfolioSnapshot,
    PortfolioAnalysisResponse,
)
from schemas.screening import (
    ScreeningFilters,
    ScreeningRequest,
    ScreenedStock,
    RankedShortlistResponse,
)
from schemas.research import (
    ResearchRequest,
    AgenticThesisResponse,
    ThesisSection,
    EvidenceSource,
)
from schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ConversationHistory,
)


class TestCommonSchemas:
    """Test common schemas."""

    def test_investment_horizon_enum(self):
        assert InvestmentHorizon.SHORT == "short"
        assert InvestmentHorizon.MEDIUM == "medium"
        assert InvestmentHorizon.LONG == "long"

    def test_risk_profile_enum(self):
        assert RiskProfile.CONSERVATIVE == "conservative"
        assert RiskProfile.MODERATE == "moderate"
        assert RiskProfile.AGGRESSIVE == "aggressive"

    def test_error_response(self):
        err = ErrorResponse(error="Test error", code="TEST_ERROR")
        assert err.error == "Test error"
        assert err.code == "TEST_ERROR"
        assert err.request_id is not None

    def test_correlation_context(self):
        ctx = CorrelationContext(conversation_id="conv-123", user_id="user-456")
        assert ctx.conversation_id == "conv-123"
        assert ctx.user_id == "user-456"
        assert ctx.request_id is not None

        new_ctx = ctx.with_new_request_id()
        assert new_ctx.request_id != ctx.request_id
        assert new_ctx.conversation_id == ctx.conversation_id


class TestPortfolioSchemas:
    """Test portfolio schemas."""

    def test_holding_item_valid(self):
        holding = HoldingItem(
            ticker="RELIANCE.NS",
            shares=Decimal("10"),
            avg_purchase_price=Decimal("2450.00"),
        )
        assert holding.ticker == "RELIANCE.NS"
        assert holding.shares == Decimal("10")
        assert holding.investment_value() == Decimal("24500.00")

    def test_holding_item_ticker_normalization(self):
        holding = HoldingItem(
            ticker="reliance",
            shares=Decimal("10"),
            avg_purchase_price=Decimal("2450.00"),
        )
        assert holding.ticker == "RELIANCE.NS"

    def test_holding_item_invalid_ticker(self):
        with pytest.raises(ValueError):
            HoldingItem(ticker="", shares=Decimal("10"), avg_purchase_price=Decimal("2450"))

    def test_holding_item_negative_shares(self):
        with pytest.raises(ValueError):
            HoldingItem(ticker="RELIANCE.NS", shares=Decimal("-10"), avg_purchase_price=Decimal("2450"))

    def test_portfolio_input_valid(self):
        portfolio = PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                HoldingItem(ticker="TCS.NS", shares=Decimal("5"), avg_purchase_price=Decimal("3800")),
            ],
            investment_horizon=InvestmentHorizon.MEDIUM,
            risk_profile=RiskProfile.MODERATE,
        )
        assert len(portfolio.holdings) == 2
        assert portfolio.total_invested() == Decimal("43500.00")

    def test_portfolio_input_duplicate_tickers(self):
        with pytest.raises(ValueError):
            PortfolioInput(
                holdings=[
                    HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                    HoldingItem(ticker="RELIANCE.NS", shares=Decimal("5"), avg_purchase_price=Decimal("2500")),
                ]
            )

    def test_portfolio_input_empty(self):
        with pytest.raises(ValueError):
            PortfolioInput(holdings=[])

    def test_holding_snapshot_calculations(self):
        snapshot = HoldingSnapshot(
            ticker="RELIANCE.NS",
            shares=Decimal("10"),
            avg_purchase_price=Decimal("2450"),
            current_price=Decimal("2600"),
        )
        snapshot.calculate_metrics(Decimal("26000"))
        assert snapshot.market_value == Decimal("26000")
        assert snapshot.unrealized_pnl == Decimal("1500")
        assert snapshot.unrealized_pnl_pct == pytest.approx(6.12, rel=0.01)
        assert snapshot.weight_pct == pytest.approx(100.0, rel=0.01)

    def test_portfolio_snapshot_totals(self):
        holdings = [
            HoldingSnapshot(
                ticker="RELIANCE.NS",
                shares=Decimal("10"),
                avg_purchase_price=Decimal("2450"),
                current_price=Decimal("2600"),
                market_value=Decimal("26000"),
                unrealized_pnl=Decimal("1500"),
                unrealized_pnl_pct=6.12,
                weight_pct=60.0,
                price_available=True,
            ),
            HoldingSnapshot(
                ticker="TCS.NS",
                shares=Decimal("5"),
                avg_purchase_price=Decimal("3800"),
                current_price=Decimal("3900"),
                market_value=Decimal("19500"),
                unrealized_pnl=Decimal("500"),
                unrealized_pnl_pct=2.63,
                weight_pct=40.0,
                price_available=True,
            ),
        ]
        snapshot = PortfolioSnapshot(
            holdings=holdings,
            total_invested=Decimal("43500"),
        )
        snapshot.calculate_totals()
        assert snapshot.total_market_value == Decimal("45500")
        assert snapshot.total_unrealized_pnl == Decimal("2000")
        assert snapshot.total_unrealized_pnl_pct == pytest.approx(4.60, rel=0.01)
        assert snapshot.holdings_with_prices == 2
        assert snapshot.holdings_without_prices == 0


class TestScreeningSchemas:
    """Test screening schemas."""

    def test_screening_filters(self):
        filters = ScreeningFilters(
            min_market_cap=Decimal("10000000000"),
            max_pe_ratio=20.0,
        )
        assert filters.min_market_cap == Decimal("10000000000")
        assert filters.max_pe_ratio == 20.0

    def test_screening_request(self):
        request = ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=15.0),
            max_results=10,
        )
        assert request.filters.max_pe_ratio == 15.0
        assert request.max_results == 10

    def test_screened_stock(self):
        stock = ScreenedStock(
            ticker="RELIANCE.NS",
            name="Reliance Industries",
            sector="Energy",
            current_price=Decimal("2600"),
            pe_ratio=15.5,
            score=85.5,
        )
        assert stock.ticker == "RELIANCE.NS"
        assert stock.score == 85.5

    def test_ranked_shortlist_response(self):
        ctx = CorrelationContext()
        response = RankedShortlistResponse(
            stocks=[
                ScreenedStock(ticker="RELIANCE.NS", score=85.5),
                ScreenedStock(ticker="TCS.NS", score=82.0),
            ],
            filters_applied=ScreeningFilters(),
            total_screened=100,
            total_returned=2,
            correlation_context=ctx,
        )
        assert response.total_screened == 100
        assert response.total_returned == 2
        assert len(response.stocks) == 2


class TestResearchSchemas:
    """Test research schemas."""

    def test_research_request(self):
        request = ResearchRequest(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            investment_horizon=InvestmentHorizon.LONG,
            risk_profile=RiskProfile.MODERATE,
        )
        assert request.ticker == "RELIANCE.NS"
        assert request.company_name == "Reliance Industries"

    def test_thesis_section(self):
        section = ThesisSection(
            title="Bull Case",
            content="Strong growth prospects...",
            confidence=0.8,
            evidence=[EvidenceSource(type="financial_data", description="Revenue growth 20% YoY")],
            key_metrics={"revenue_growth": "20%"},
        )
        assert section.title == "Bull Case"
        assert section.confidence == 0.8
        assert len(section.evidence) == 1

    def test_agentic_thesis_response(self):
        ctx = CorrelationContext()
        thesis = AgenticThesisResponse(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            company_overview=ThesisSection(title="Overview", content="...", confidence=0.9),
            bull_thesis=ThesisSection(title="Bull", content="...", confidence=0.7),
            bear_thesis=ThesisSection(title="Bear", content="...", confidence=0.6),
            financial_strengths=ThesisSection(title="Strengths", content="...", confidence=0.8),
            risks_and_uncertainties=ThesisSection(title="Risks", content="...", confidence=0.75),
            model_used="gemini-1.5-flash",
            correlation_context=ctx,
        )
        assert thesis.ticker == "RELIANCE.NS"
        summary = thesis.get_summary()
        assert "Reliance Industries" in summary
        assert "RELIANCE.NS" in summary


class TestChatSchemas:
    """Test chat schemas."""

    def test_chat_request(self):
        request = ChatRequest(
            message="Analyze my portfolio",
            conversation_id="conv-123",
        )
        assert request.message == "Analyze my portfolio"
        assert request.conversation_id == "conv-123"

    def test_chat_request_auto_conversation_id(self):
        request = ChatRequest(message="Hello")
        conv_id = request.get_or_create_conversation_id()
        assert conv_id is not None
        assert request.conversation_id == conv_id

    def test_chat_response(self):
        ctx = CorrelationContext()
        response = ChatResponse(
            message="Hello! How can I help?",
            conversation_id="conv-123",
            message_type="text",
            correlation_context=ctx,
        )
        assert response.message == "Hello! How can I help?"
        assert response.conversation_id == "conv-123"

    def test_conversation_history(self):
        history = ConversationHistory(
            conversation_id="conv-123",
            messages=[
                ChatMessage(role="user", content="Hello"),
                ChatMessage(role="assistant", content="Hi there!"),
            ],
        )
        assert len(history.messages) == 2
        assert history.messages[0].role == "user"
        assert history.messages[1].role == "assistant"


class TestSchemaSerialization:
    """Test JSON serialization/deserialization."""

    def test_portfolio_input_json_roundtrip(self):
        portfolio = PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
            ],
        )
        json_data = portfolio.model_dump(mode="json")
        restored = PortfolioInput.model_validate(json_data)
        assert restored.holdings[0].ticker == "RELIANCE.NS"
        assert restored.holdings[0].shares == Decimal("10")

    def test_screening_request_json_roundtrip(self):
        request = ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=15.0),
            max_results=20,
        )
        json_data = request.model_dump(mode="json")
        restored = ScreeningRequest.model_validate(json_data)
        assert restored.filters.max_pe_ratio == 15.0
        assert restored.max_results == 20

    def test_research_request_json_roundtrip(self):
        request = ResearchRequest(ticker="RELIANCE.NS", company_name="Reliance")
        json_data = request.model_dump(mode="json")
        restored = ResearchRequest.model_validate(json_data)
        assert restored.ticker == "RELIANCE.NS"
        assert restored.company_name == "Reliance"

    def test_chat_request_json_roundtrip(self):
        request = ChatRequest(message="Test message", conversation_id="conv-123")
        json_data = request.model_dump(mode="json")
        restored = ChatRequest.model_validate(json_data)
        assert restored.message == "Test message"
        assert restored.conversation_id == "conv-123"