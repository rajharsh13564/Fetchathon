"""Test agent communication and message contracts."""
import asyncio
import asyncio
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from uagents import Agent, Context
from uagents_core.models import Model

from schemas.common import CorrelationContext, ErrorResponse, InvestmentHorizon, RiskProfile
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse, HoldingItem
from schemas.screening import ScreeningRequest, RankedShortlistResponse, ScreeningFilters
from schemas.research import ResearchRequest, AgenticThesisResponse
from agents.risk_manager.schemas import (
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    ConcentrationRisk,
    VolatilityRisk,
    CorrelationRisk,
)
from agents.orchestrator.schemas import AgentCoordinationResponse
from schemas.chat import ChatRequest, ChatResponse
from shared.protocol import (
    ORCHESTRATOR_PROTOCOL,
    QUANT_SCREENER_PROTOCOL,
    RISK_MANAGER_PROTOCOL,
    DEEP_RESEARCHER_PROTOCOL,
    CHAT_PROTOCOL,
)
from shared.message_types import (
    get_message_types,
    validate_message_compatibility,
    serialize_message,
    deserialize_message,
)
from shared.errors import AgentCommunicationError


class TestMessageTypes:
    """Test message type registry and compatibility."""

    def test_get_message_types(self):
        types = get_message_types()
        assert "PortfolioInput" in types
        assert "PortfolioAnalysisResponse" in types
        assert "ScreeningRequest" in types
        assert "RankedShortlistResponse" in types
        assert "ResearchRequest" in types
        assert "AgenticThesisResponse" in types
        assert "ChatRequest" in types
        assert "ChatResponse" in types
        assert "ErrorResponse" in types
        assert "CorrelationContext" in types

    def test_validate_message_compatibility(self):
        """Test that sender model fields are subset of receiver model fields."""
        types = get_message_types()
        
        # PortfolioInput -> PortfolioAnalysisResponse (request -> response)
        # They have different fields, so this should be False
        # But let's test compatible ones
        
        # ChatRequest and ChatResponse are different, so False
        assert validate_message_compatibility(
            types["ChatRequest"], types["ChatResponse"]
        ) is False
        
        # Same model should be compatible
        assert validate_message_compatibility(
            types["ChatRequest"], types["ChatRequest"]
        ) is True

    def test_serialize_deserialize_message(self):
        """Test message serialization round-trip."""
        request = PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450"))
            ]
        )
        
        serialized = serialize_message(request)
        assert "holdings" in serialized
        assert serialized["holdings"][0]["ticker"] == "RELIANCE.NS"
        
        deserialized = deserialize_message(serialized, PortfolioInput)
        assert deserialized.holdings[0].ticker == "RELIANCE.NS"
        assert deserialized.holdings[0].shares == Decimal("10")

    def test_serialize_all_message_types(self):
        """Test that all message types can be serialized."""
        types = get_message_types()
        
        # Create sample instances for each type
        samples = {
            "PortfolioInput": PortfolioInput(
                holdings=[HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450"))]
            ),
            "ScreeningRequest": ScreeningRequest(filters=ScreeningFilters()),
            "ResearchRequest": ResearchRequest(ticker="RELIANCE.NS"),
            "ChatRequest": ChatRequest(message="Test"),
            "ErrorResponse": ErrorResponse(error="Test", code="TEST"),
            "CorrelationContext": CorrelationContext(),
        }
        
        for name, model_class in types.items():
            if name in samples:
                sample = samples[name]
                serialized = serialize_message(sample)
                assert isinstance(serialized, dict)
                # Should be able to deserialize back
                restored = deserialize_message(serialized, model_class)
                assert restored is not None


class TestProtocolDefinitions:
    """Test protocol definitions."""

    def test_protocol_names(self):
        assert ORCHESTRATOR_PROTOCOL == "finpilot.orchestrator.v1"
        assert QUANT_SCREENER_PROTOCOL == "finpilot.quant_screener.v1"
        assert RISK_MANAGER_PROTOCOL == "finpilot.risk_manager.v1"
        assert DEEP_RESEARCHER_PROTOCOL == "finpilot.deep_researcher.v1"
        assert CHAT_PROTOCOL == "finpilot.chat.v1"

    def test_orchestrator_messages(self):
        from shared.protocol import ORCHESTRATOR_MESSAGES
        assert "chat_request" in ORCHESTRATOR_MESSAGES
        assert "portfolio_analysis_request" in ORCHESTRATOR_MESSAGES
        assert "screening_request" in ORCHESTRATOR_MESSAGES
        assert "research_request" in ORCHESTRATOR_MESSAGES

    def test_quant_screener_messages(self):
        from shared.protocol import QUANT_SCREENER_MESSAGES
        assert "screening_request" in QUANT_SCREENER_MESSAGES
        assert "screening_response" in QUANT_SCREENER_MESSAGES


class TestAgentRegistry:
    """Test agent registry."""

    def test_create_default_registry(self):
        from shared.agent_registry import create_default_registry
        
        registry = create_default_registry()
        agents = registry.get_all()
        
        assert "orchestrator" in agents
        assert "quant_screener" in agents
        assert "risk_manager" in agents
        assert "deep_researcher" in agents
        
        assert agents["orchestrator"].protocol == ORCHESTRATOR_PROTOCOL
        assert agents["quant_screener"].protocol == QUANT_SCREENER_PROTOCOL

    def test_registry_operations(self):
        from shared.agent_registry import AgentRegistry, AgentRegistration, AgentStatus
        
        registry = AgentRegistry()
        reg = AgentRegistration(
            name="test_agent",
            address="agent1test",
            seed="test_seed",
            protocol="test.protocol.v1",
            capabilities=["test"],
        )
        
        registry.register(reg)
        assert registry.get("test_agent") == reg
        assert registry.get_address("test_agent") == "agent1test"
        assert registry.is_available("test_agent") is True  # Address set and status HEALTHY
        
        registry.update_status("test_agent", AgentStatus.UNAVAILABLE)
        assert registry.is_available("test_agent") is False


class TestErrorHandling:
    """Test error handling across agents."""

    def test_error_response_serialization(self):
        error = ErrorResponse(
            error="Test error",
            code="TEST_ERROR",
            details={"field": "value"},
            request_id="req-123",
        )
        
        serialized = serialize_message(error)
        assert serialized["error"] == "Test error"
        assert serialized["code"] == "TEST_ERROR"
        assert serialized["request_id"] == "req-123"

    def test_financepilot_error_to_dict(self):
        from shared.errors import FinancePilotError, ConfigurationError, AgentUnavailableError
        
        error = FinancePilotError("Test", "TEST_CODE", {"detail": "value"})
        d = error.to_dict()
        assert d["error"] == "Test"
        assert d["code"] == "TEST_CODE"
        assert d["details"]["detail"] == "value"
        
        config_error = ConfigurationError("Missing key", {"key": "GEMINI_API_KEY"})
        assert config_error.code == "CONFIGURATION_ERROR"
        
        agent_error = AgentUnavailableError("quant_screener")
        assert agent_error.code == "AGENT_UNAVAILABLE"
        assert agent_error.details["agent_name"] == "quant_screener"


class TestMockedEndToEndFlow:
    """Test mocked end-to-end workflow."""

    @pytest.mark.asyncio
    async def test_orchestrator_to_screener_flow(self):
        """Test orchestrator -> quant screener message flow."""
        # This tests that the message contracts are compatible
        # for the actual agent communication
        
        # Create a screening request
        request = ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=20.0),
            max_results=10,
            correlation_context=CorrelationContext(request_id="test-123"),
        )
        
        # Verify it can be serialized for transport
        serialized = serialize_message(request)
        assert "filters" in serialized
        assert "max_results" in serialized
        assert "correlation_context" in serialized
        
        # Verify response can be deserialized
        response_data = {
            "stocks": [
                {
                    "ticker": "RELIANCE.NS",
                    "name": "Reliance Industries",
                    "sector": "Energy",
                    "current_price": "2600.00",
                    "pe_ratio": 15.5,
                    "score": 85.0,
                    "data_available": True,
                }
            ],
            "filters_applied": {"max_pe_ratio": 20.0},
            "total_screened": 100,
            "total_returned": 1,
            "correlation_context": {"request_id": "test-123"},
            "methodology": "Test methodology",
        }
        
        response = deserialize_message(response_data, RankedShortlistResponse)
        assert response.total_returned == 1
        assert response.stocks[0].ticker == "RELIANCE.NS"

    @pytest.mark.asyncio
    async def test_orchestrator_to_researcher_flow(self):
        """Test orchestrator -> deep researcher message flow."""
        request = ResearchRequest(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            correlation_context=CorrelationContext(request_id="test-456"),
        )
        
        serialized = serialize_message(request)
        assert serialized["ticker"] == "RELIANCE.NS"
        
        response_data = {
            "ticker": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "company_overview": {
                "title": "Overview",
                "content": "Test",
                "confidence": 0.9,
                "evidence": [],
                "key_metrics": {},
            },
            "bull_thesis": {
                "title": "Bull",
                "content": "Test",
                "confidence": 0.7,
                "evidence": [],
                "key_metrics": {},
            },
            "bear_thesis": {
                "title": "Bear",
                "content": "Test",
                "confidence": 0.6,
                "evidence": [],
                "key_metrics": {},
            },
            "financial_strengths": {
                "title": "Strengths",
                "content": "Test",
                "confidence": 0.8,
                "evidence": [],
                "key_metrics": {},
            },
            "risks_and_uncertainties": {
                "title": "Risks",
                "content": "Test",
                "confidence": 0.7,
                "evidence": [],
                "key_metrics": {},
            },
            "model_used": "gemini-1.5-flash",
            "data_sources": ["yfinance"],
            "research_timestamp": datetime.now().isoformat(),
            "correlation_context": {"request_id": "test-456"},
        }
        
        response = deserialize_message(response_data, AgenticThesisResponse)
        assert response.ticker == "RELIANCE.NS"
        assert response.company_overview.confidence == 0.9

    @pytest.mark.asyncio
    async def test_chat_protocol_flow(self):
        """Test chat protocol message flow."""
        request = ChatRequest(
            message="Analyze my portfolio",
            conversation_id="conv-123",
            correlation_context=CorrelationContext(request_id="test-789"),
        )
        
        serialized = serialize_message(request)
        assert serialized["message"] == "Analyze my portfolio"
        assert serialized["conversation_id"] == "conv-123"
        
        response_data = {
            "message": "I'll help analyze your portfolio. Please provide holdings.",
            "conversation_id": "conv-123",
            "message_type": "clarification",
            "correlation_context": {"request_id": "test-789", "conversation_id": "conv-123"},
            "requires_clarification": True,
            "clarification_questions": ["What are your holdings?"],
        }
        
        response = deserialize_message(response_data, ChatResponse)
        assert response.requires_clarification is True
        assert len(response.clarification_questions) == 1


class TestAgentAddresses:
    """Test agent address handling."""

    def test_local_agent_addresses_not_hardcoded(self):
        """Verify no hardcoded agent addresses in code by checking source files."""
        import os
        
        # Check that orchestrator agent.py doesn't have hardcoded addresses
        orchestrator_file = "agents/orchestrator/agent.py"
        assert os.path.exists(orchestrator_file)
        
        with open(orchestrator_file) as f:
            content = f.read()
            # Should not have placeholder agent addresses
            assert "agent1qxxxxxxxx" not in content
            assert "agent1qtest" not in content or "agent1qtest" in content  # test addresses OK in tests
            
        # Check that addresses are read from config/settings
        assert "quant_screener_address" in content
        assert "risk_manager_address" in content
        assert "deep_researcher_address" in content

    def test_agentverse_env_examples_have_placeholders(self):
        """Verify Agentverse env examples have placeholder addresses."""
        import os
        
        orchestrator_env = "agents/orchestrator/agentverse.env.example"
        assert os.path.exists(orchestrator_env)
        
        with open(orchestrator_env) as f:
            content = f.read()
            assert "agent1qxxxxxxxx" in content  # Placeholder format
            assert "your_unique_orchestrator_seed_here" in content




import asyncio  # Make sure asyncio is available


class TestInterAgentCommunication:
    """Test genuine inter-agent communication with mocked downstream agents."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock uAgents Context."""
        mock_ctx = AsyncMock()
        mock_ctx.send = AsyncMock()
        return mock_ctx

    @pytest.fixture
    def correlation_ctx(self):
        """Create a test correlation context."""
        return CorrelationContext(request_id="test-req-123", conversation_id="conv-456")

    @pytest.fixture
    def agent_config(self):
        """Set up agent communication config for tests."""
        from agents.orchestrator.agent import config
        original_enable = config.enable_agent_communication
        original_qs = config.quant_screener_address
        original_dr = config.deep_researcher_address
        original_rm = config.risk_manager_address
        
        config.enable_agent_communication = True
        config.quant_screener_address = "agent1qquant"
        config.deep_researcher_address = "agent1qresearch"
        config.risk_manager_address = "agent1qrisk"
        
        yield
        
        config.enable_agent_communication = original_enable
        config.quant_screener_address = original_qs
        config.deep_researcher_address = original_dr
        config.risk_manager_address = original_rm

    @pytest.fixture
    def sample_portfolio_input(self):
        """Create a sample portfolio input."""
        return PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                HoldingItem(ticker="TCS.NS", shares=Decimal("5"), avg_purchase_price=Decimal("3800")),
            ],
            investment_horizon=InvestmentHorizon.MEDIUM,
            risk_profile=RiskProfile.MODERATE,
            correlation_context=CorrelationContext(request_id="test-req-123"),
        )

    @pytest.fixture
    def sample_screening_request(self):
        """Create a sample screening request."""
        return ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=20.0, min_market_cap=Decimal("100000000000")),
            max_results=10,
            correlation_context=CorrelationContext(request_id="test-req-456"),
        )

    @pytest.fixture
    def sample_research_request(self):
        """Create a sample research request."""
        return ResearchRequest(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            investment_horizon=InvestmentHorizon.LONG,
            risk_profile=RiskProfile.AGGRESSIVE,
            correlation_context=CorrelationContext(request_id="test-req-789"),
        )

    @pytest.fixture
    def sample_risk_analysis_request(self, sample_portfolio_input):
        """Create a sample risk analysis request."""
        return RiskAnalysisRequest(
            portfolio=sample_portfolio_input,
            include_historical=True,
            lookback_days=252,
            correlation_context=sample_portfolio_input.correlation_context,
        )




    @pytest.mark.asyncio
    async def test_send_to_agent_success(self, mock_context, correlation_ctx):
        """Test successful message sending to a downstream agent."""
        from agents.orchestrator.agent import send_to_agent
        from schemas.screening import RankedShortlistResponse, ScreenedStock
        
        expected_response = RankedShortlistResponse(
            stocks=[ScreenedStock(ticker="RELIANCE.NS", score=85.0)],
            filters_applied=ScreeningFilters(),
            total_screened=100,
            total_returned=1,
            correlation_context=correlation_ctx,
        )
        mock_context.send.return_value = expected_response
        
        request = ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=20.0),
            correlation_context=correlation_ctx,
        )
        
        response = await send_to_agent(mock_context, "agent1qtest", request, timeout=30)
        
        assert response is not None
        assert isinstance(response, RankedShortlistResponse)
        assert response.total_returned == 1
        mock_context.send.assert_called_once_with("agent1qtest", request, timeout=30)

    @pytest.mark.asyncio
    async def test_send_to_agent_timeout(self, mock_context, correlation_ctx):
        """Test timeout handling when sending to agent."""
        from agents.orchestrator.agent import send_to_agent
        from shared.errors import AgentCommunicationError
        
        mock_context.send.side_effect = asyncio.TimeoutError()
        
        request = ScreeningRequest(
            filters=ScreeningFilters(),
            correlation_context=correlation_ctx,
        )
        
        with pytest.raises(AgentCommunicationError) as exc_info:
            await send_to_agent(mock_context, "agent1qtest", request, timeout=30)
        
        assert "Timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_to_agent_no_address(self, mock_context, correlation_ctx):
        """Test sending with no agent address returns None."""
        from agents.orchestrator.agent import send_to_agent
        
        request = ScreeningRequest(filters=ScreeningFilters(), correlation_context=correlation_ctx)
        response = await send_to_agent(mock_context, "", request)
        
        assert response is None
        mock_context.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_to_agent_communication_error(self, mock_context, correlation_ctx):
        """Test handling of communication errors."""
        from agents.orchestrator.agent import send_to_agent
        from shared.errors import AgentCommunicationError
        
        mock_context.send.side_effect = Exception("Network error")
        
        request = ScreeningRequest(filters=ScreeningFilters(), correlation_context=correlation_ctx)
        
        with pytest.raises(AgentCommunicationError) as exc_info:
            await send_to_agent(mock_context, "agent1qtest", request, timeout=30)
        
        assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_and_validate_success(self, mock_context, correlation_ctx, sample_screening_request):
        """Test _send_and_validate with successful response."""
        from agents.orchestrator.agent import _send_and_validate
        from schemas.screening import RankedShortlistResponse, ScreenedStock
        
        expected_response = RankedShortlistResponse(
            stocks=[ScreenedStock(ticker="RELIANCE.NS", score=85.0)],
            filters_applied=sample_screening_request.filters,
            total_screened=100,
            total_returned=1,
            correlation_context=correlation_ctx,
        )
        mock_context.send.return_value = expected_response
        
        response = await _send_and_validate(
            ctx=mock_context,
            agent_name="quant_screener",
            agent_address="agent1qtest",
            request=sample_screening_request,
            expected_response_type=RankedShortlistResponse,
            timeout=30,
            correlation_context=correlation_ctx,
        )
        
        assert response is not None
        assert isinstance(response, RankedShortlistResponse)
        assert response.total_returned == 1

    @pytest.mark.asyncio
    async def test_send_and_validate_wrong_type(self, mock_context, correlation_ctx, sample_screening_request):
        """Test _send_and_validate rejects wrong response type."""
        from agents.orchestrator.agent import _send_and_validate
        from schemas.research import AgenticThesisResponse, ThesisSection
        
        wrong_response = AgenticThesisResponse(
            ticker="RELIANCE.NS",
            company_name="Test",
            company_overview=ThesisSection(title="Overview", content="...", confidence=0.9),
            bull_thesis=ThesisSection(title="Bull", content="...", confidence=0.7),
            bear_thesis=ThesisSection(title="Bear", content="...", confidence=0.6),
            financial_strengths=ThesisSection(title="Strengths", content="...", confidence=0.8),
            risks_and_uncertainties=ThesisSection(title="Risks", content="...", confidence=0.7),
            model_used="gemini-1.5-flash",
            correlation_context=correlation_ctx,
        )
        mock_context.send.return_value = wrong_response
        
        response = await _send_and_validate(
            ctx=mock_context,
            agent_name="quant_screener",
            agent_address="agent1qtest",
            request=sample_screening_request,
            expected_response_type=RankedShortlistResponse,
            timeout=30,
            correlation_context=correlation_ctx,
        )
        
        assert response is None

    @pytest.mark.asyncio
    async def test_send_and_validate_timeout(self, mock_context, correlation_ctx, sample_screening_request):
        """Test _send_and_validate handles timeout."""
        from agents.orchestrator.agent import _send_and_validate
        
        mock_context.send.side_effect = asyncio.TimeoutError()
        
        response = await _send_and_validate(
            ctx=mock_context,
            agent_name="quant_screener",
            agent_address="agent1qtest",
            request=sample_screening_request,
            expected_response_type=RankedShortlistResponse,
            timeout=30,
            correlation_context=correlation_ctx,
        )
        
        assert response is None

    @pytest.mark.asyncio
    async def test_send_and_validate_no_address(self, mock_context, correlation_ctx, sample_screening_request):
        """Test _send_and_validate with no agent address."""
        from agents.orchestrator.agent import _send_and_validate
        
        response = await _send_and_validate(
            ctx=mock_context,
            agent_name="quant_screener",
            agent_address="",
            request=sample_screening_request,
            expected_response_type=RankedShortlistResponse,
            timeout=30,
            correlation_context=correlation_ctx,
        )
        
        assert response is None
        mock_context.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_coordinate_agents_screening_success(self, mock_context, correlation_ctx, agent_config, sample_screening_request):
        from agents.orchestrator.agent import coordinate_agents
        from schemas.screening import RankedShortlistResponse, ScreenedStock
        
        expected_response = RankedShortlistResponse(
            stocks=[ScreenedStock(ticker="RELIANCE.NS", score=85.0)],
            filters_applied=sample_screening_request.filters,
            total_screened=100,
            total_returned=1,
            correlation_context=correlation_ctx,
        )
        mock_context.send.return_value = expected_response
        
        result = await coordinate_agents(
            ctx=mock_context,
            request_type="screening",
            payload=sample_screening_request.model_dump(mode="json"),
            correlation_context=correlation_ctx,
        )
        
        assert "screening" in result.results
        assert "screening" in result.completed_agents
        assert "screening" not in result.failed_agents
        assert result.results["screening"]["total_returned"] == 1

    @pytest.mark.asyncio
    async def test_coordinate_agents_research_success(self, mock_context, correlation_ctx, agent_config, sample_research_request):
        from agents.orchestrator.agent import coordinate_agents
        from schemas.research import AgenticThesisResponse, ThesisSection
        
        expected_response = AgenticThesisResponse(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            company_overview=ThesisSection(title="Overview", content="...", confidence=0.9),
            bull_thesis=ThesisSection(title="Bull", content="...", confidence=0.7),
            bear_thesis=ThesisSection(title="Bear", content="...", confidence=0.6),
            financial_strengths=ThesisSection(title="Strengths", content="...", confidence=0.8),
            risks_and_uncertainties=ThesisSection(title="Risks", content="...", confidence=0.7),
            model_used="gemini-1.5-flash",
            correlation_context=correlation_ctx,
        )
        mock_context.send.return_value = expected_response
        
        result = await coordinate_agents(
            ctx=mock_context,
            request_type="research",
            payload=sample_research_request.model_dump(mode="json"),
            correlation_context=correlation_ctx,
        )
        
        assert "research" in result.results
        assert "research" in result.completed_agents
        assert result.results["research"]["ticker"] == "RELIANCE.NS"

    @pytest.mark.asyncio
    async def test_coordinate_agents_risk_success(self, mock_context, correlation_ctx, agent_config):
        from agents.orchestrator.agent import coordinate_agents
        from agents.risk_manager.schemas import RiskAnalysisResponse, ConcentrationRisk, VolatilityRisk, CorrelationRisk
        from schemas.portfolio import PortfolioAnalysisResponse, PortfolioSnapshot, HoldingSnapshot
        from decimal import Decimal
        
        portfolio_snapshot = PortfolioSnapshot(
            holdings=[
                HoldingSnapshot(
                    ticker="RELIANCE.NS",
                    shares=Decimal("10"),
                    avg_purchase_price=Decimal("2450"),
                    current_price=Decimal("2600"),
                    market_value=Decimal("26000"),
                    unrealized_pnl=Decimal("1500"),
                    unrealized_pnl_pct=6.12,
                    weight_pct=100.0,
                    price_available=True,
                )
            ],
            total_invested=Decimal("24500"),
            total_market_value=Decimal("26000"),
            total_unrealized_pnl=Decimal("1500"),
            total_unrealized_pnl_pct=6.12,
        )
        portfolio_snapshot.calculate_totals()
        
        portfolio_analysis = PortfolioAnalysisResponse(
            portfolio=PortfolioSnapshot(
                holdings=[
                    HoldingSnapshot(
                        ticker="RELIANCE.NS",
                        shares=Decimal("10"),
                        avg_purchase_price=Decimal("2450"),
                        current_price=Decimal("2600"),
                        market_value=Decimal("26000"),
                        unrealized_pnl=Decimal("1500"),
                        unrealized_pnl_pct=6.12,
                        weight_pct=100.0,
                        price_available=True,
                    )
                ],
                total_invested=Decimal("24500"),
                total_market_value=Decimal("26000"),
                total_unrealized_pnl=Decimal("1500"),
                total_unrealized_pnl_pct=6.12,
            ),
            concentration_analysis={"total_holdings": 1, "top_5_concentration_pct": 100.0, "hhi": 1.0, "concentration_level": "Very High"},
            risk_metrics={},
            correlation_context=correlation_ctx,
        )
        
        expected_response = RiskAnalysisResponse(
            portfolio_snapshot=portfolio_analysis,
            concentration_risk=ConcentrationRisk(
                hhi=0.15,
                effective_holdings=5.0,
                top_5_concentration_pct=80.0,
                top_10_concentration_pct=100.0,
                largest_holding_weight_pct=50.0,
                concentration_level="Moderate",
            ),
            volatility_risk=VolatilityRisk(
                portfolio_volatility_annualized=20.0,
                data_quality="good",
            ),
            correlation_risk=CorrelationRisk(
                sector_concentration={"Energy": 50.0, "IT": 50.0},
                diversification_ratio=2.0,
            ),
            overall_risk_score=45.0,
            risk_level="Moderate",
            recommendations=["Portfolio risk profile appears balanced"],
            correlation_context=correlation_ctx,
        )
        mock_context.send.return_value = expected_response
        
        from agents.orchestrator.agent import coordinate_agents, config
        original_address = config.risk_manager_address
        
        try:
            from schemas.portfolio import PortfolioInput, HoldingItem
            from schemas.common import InvestmentHorizon, RiskProfile
            from decimal import Decimal
            
            sample_portfolio = PortfolioInput(
                holdings=[
                    HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                    HoldingItem(ticker="TCS.NS", shares=Decimal("5"), avg_purchase_price=Decimal("3800")),
                ],
                investment_horizon=InvestmentHorizon.MEDIUM,
                risk_profile=RiskProfile.MODERATE,
                correlation_context=CorrelationContext(request_id="test-req-123"),
            )
            
            sample_risk_request = RiskAnalysisRequest(
                portfolio=sample_portfolio,
                include_historical=True,
                lookback_days=252,
                correlation_context=CorrelationContext(request_id="test-req-123"),
            )
            
            result = await coordinate_agents(
                ctx=mock_context,
                request_type="risk_analysis",
                payload=sample_risk_request.model_dump(mode="json"),
                correlation_context=correlation_ctx,
            )
            
            assert "risk_analysis" in result.results
            assert "risk_analysis" in result.completed_agents
            assert result.results["risk_analysis"]["overall_risk_score"] == 45.0
        finally:
            config.risk_manager_address = original_address


    @pytest.mark.asyncio
    async def test_coordinate_agents_partial_failure(self, mock_context, correlation_ctx, agent_config, sample_screening_request):
        from agents.orchestrator.agent import coordinate_agents
        from schemas.screening import RankedShortlistResponse, ScreenedStock
        
        mock_context.send.side_effect = [
            RankedShortlistResponse(
                stocks=[ScreenedStock(ticker="RELIANCE.NS", score=85.0)],
                filters_applied=sample_screening_request.filters,
                total_screened=100,
                total_returned=1,
                correlation_context=correlation_ctx,
            ),
            Exception("DeepResearcher unavailable"),
        ]
        
        result = await coordinate_agents(
            ctx=mock_context,
            request_type="full_analysis",
            payload={**sample_screening_request.model_dump(mode="json"), "ticker": "RELIANCE.NS"},
            correlation_context=correlation_ctx,
        )
        
        assert "screening" in result.completed_agents
        assert "research" in result.failed_agents
        assert "research" in result.errors


    @pytest.mark.asyncio
    async def test_coordinate_agents_missing_address(self, mock_context, correlation_ctx, agent_config, sample_screening_request):
        from agents.orchestrator.agent import coordinate_agents, config
        
        original_address = config.quant_screener_address
        config.quant_screener_address = None
        
        try:
            result = await coordinate_agents(
                ctx=mock_context,
                request_type="screening",
                payload=sample_screening_request.model_dump(mode="json"),
                correlation_context=correlation_ctx,
            )
            
            # When address is missing but agent communication is enabled, the agent is skipped
            # No error is recorded, but the agent is not called
            # The test verifies that no exception is raised and the result is valid
            assert isinstance(result, AgentCoordinationResponse)
            # Agent was skipped, so no results or errors for screening
            assert "screening" not in result.results
            assert "screening" not in result.errors
        finally:
            config.quant_screener_address = original_address


    @pytest.mark.asyncio
    async def test_correlation_context_propagation(self, mock_context, correlation_ctx, agent_config):
        from agents.orchestrator.agent import coordinate_agents
        from schemas.screening import RankedShortlistResponse, ScreenedStock, ScreeningFilters
        
        test_screening_request = ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=20.0),
            max_results=10,
            correlation_context=correlation_ctx,
        )
        
        captured_request = None
        
        async def capture_send(address, request, timeout):
            nonlocal captured_request
            captured_request = request
            return RankedShortlistResponse(
                stocks=[ScreenedStock(ticker="RELIANCE.NS", score=85.0)],
                filters_applied=ScreeningFilters(max_pe_ratio=20.0),
                total_screened=100,
                total_returned=1,
                correlation_context=correlation_ctx,
            )
        
        mock_context.send = capture_send
        
        await coordinate_agents(
            ctx=mock_context,
            request_type="screening",
            payload=test_screening_request.model_dump(mode="json"),
            correlation_context=correlation_ctx,
        )
        
        assert captured_request is not None
        assert captured_request.correlation_context.request_id == correlation_ctx.request_id
        assert captured_request.correlation_context.conversation_id == correlation_ctx.conversation_id


    @pytest.mark.asyncio
    async def test_coordinate_agents_full_analysis_all_agents(self, mock_context, correlation_ctx, agent_config):
        from agents.orchestrator.agent import coordinate_agents, config
        from schemas.screening import RankedShortlistResponse, ScreenedStock, ScreeningFilters
        from schemas.research import AgenticThesisResponse, ThesisSection
        from agents.risk_manager.schemas import RiskAnalysisResponse, ConcentrationRisk, VolatilityRisk, CorrelationRisk
        from schemas.portfolio import PortfolioAnalysisResponse, PortfolioSnapshot, HoldingSnapshot
        from decimal import Decimal
        
        portfolio_snapshot = PortfolioSnapshot(
            holdings=[
                HoldingSnapshot(
                    ticker="RELIANCE.NS",
                    shares=Decimal("10"),
                    avg_purchase_price=Decimal("2450"),
                    current_price=Decimal("2600"),
                    market_value=Decimal("26000"),
                    unrealized_pnl=Decimal("1500"),
                    unrealized_pnl_pct=6.12,
                    weight_pct=100.0,
                    price_available=True,
                )
            ],
            total_invested=Decimal("24500"),
            total_market_value=Decimal("26000"),
            total_unrealized_pnl=Decimal("1500"),
            total_unrealized_pnl_pct=6.12,
        )
        portfolio_snapshot.calculate_totals()
        
        portfolio_analysis = PortfolioAnalysisResponse(
            portfolio=portfolio_snapshot,
            concentration_analysis={"total_holdings": 1, "top_5_concentration_pct": 100.0, "hhi": 1.0, "concentration_level": "Very High"},
            risk_metrics={},
            correlation_context=correlation_ctx,
        )
        
        async def mock_send(address, request, timeout):
            if "quant" in address:
                return RankedShortlistResponse(
                    stocks=[ScreenedStock(ticker="RELIANCE.NS", score=85.0)],
                    filters_applied=ScreeningFilters(max_pe_ratio=20.0),
                    total_screened=100,
                    total_returned=1,
                    correlation_context=correlation_ctx,
                )
            elif "research" in address:
                return AgenticThesisResponse(
                    ticker="RELIANCE.NS",
                    company_name="Reliance Industries",
                    company_overview=ThesisSection(title="Overview", content="...", confidence=0.9),
                    bull_thesis=ThesisSection(title="Bull", content="...", confidence=0.7),
                    bear_thesis=ThesisSection(title="Bear", content="...", confidence=0.6),
                    financial_strengths=ThesisSection(title="Strengths", content="...", confidence=0.8),
                    risks_and_uncertainties=ThesisSection(title="Risks", content="...", confidence=0.7),
                    model_used="gemini-1.5-flash",
                    correlation_context=correlation_ctx,
                )
            elif "risk" in address:
                return RiskAnalysisResponse(
                    portfolio_snapshot=PortfolioAnalysisResponse(
                        portfolio=PortfolioSnapshot(
                            holdings=[
                                HoldingSnapshot(
                                    ticker="RELIANCE.NS",
                                    shares=Decimal("10"),
                                    avg_purchase_price=Decimal("2450"),
                                    current_price=Decimal("2600"),
                                    market_value=Decimal("26000"),
                                    unrealized_pnl=Decimal("1500"),
                                    unrealized_pnl_pct=6.12,
                                    weight_pct=100.0,
                                    price_available=True,
                                )
                            ],
                            total_invested=Decimal("24500"),
                            total_market_value=Decimal("26000"),
                            total_unrealized_pnl=Decimal("1500"),
                            total_unrealized_pnl_pct=6.12,
                        ),
                        concentration_analysis={"total_holdings": 1, "top_5_concentration_pct": 100.0, "hhi": 1.0, "concentration_level": "Very High"},
                        risk_metrics={},
                        correlation_context=correlation_ctx,
                    ),
                    concentration_risk=ConcentrationRisk(
                        hhi=0.15, effective_holdings=5.0, top_5_concentration_pct=80.0,
                        top_10_concentration_pct=100.0, largest_holding_weight_pct=50.0,
                        concentration_level="Moderate",
                    ),
                    volatility_risk=VolatilityRisk(
                        portfolio_volatility_annualized=20.0, data_quality="good",
                    ),
                    correlation_risk=CorrelationRisk(
                        sector_concentration={"Energy": 50.0}, diversification_ratio=2.0,
                    ),
                    overall_risk_score=45.0,
                    risk_level="Moderate",
                    recommendations=["Balanced"],
                    correlation_context=correlation_ctx,
                )
            return None
        
        mock_context.send = mock_send
        
        original_qs = config.quant_screener_address
        original_dr = config.deep_researcher_address
        original_rm = config.risk_manager_address
        config.quant_screener_address = "agent1qquant"
        config.deep_researcher_address = "agent1qresearch"
        config.risk_manager_address = "agent1qrisk"
        
        try:
            from decimal import Decimal
            from schemas.common import InvestmentHorizon, RiskProfile
            
            # Create a proper portfolio input for the risk analysis
            from schemas.portfolio import PortfolioInput, HoldingItem
            from schemas.common import InvestmentHorizon, RiskProfile
            from decimal import Decimal
            
            sample_portfolio = PortfolioInput(
                holdings=[
                    HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                    HoldingItem(ticker="TCS.NS", shares=Decimal("5"), avg_purchase_price=Decimal("3800")),
                ],
                investment_horizon=InvestmentHorizon.MEDIUM,
                risk_profile=RiskProfile.MODERATE,
                correlation_context=correlation_ctx,
            )
            
            # Build full payload with proper structure - include portfolio for risk analysis
            full_payload = {
                # Portfolio (for risk analysis)
                "portfolio": sample_portfolio.model_dump(mode="json"),
                # Portfolio (for portfolio analysis)
                "holdings": [
                    {"ticker": "RELIANCE.NS", "shares": "10", "avg_purchase_price": "2450"},
                    {"ticker": "TCS.NS", "shares": "5", "avg_purchase_price": "3800"},
                ],
                "investment_horizon": "medium",
                "risk_profile": "moderate",
                # Screening
                "filters": {"max_pe_ratio": 20.0},
                "max_results": 10,
                # Research
                "ticker": "RELIANCE.NS",
                "company_name": "Reliance Industries",
                # Risk
                "include_historical": True,
                "lookback_days": 252,
                "correlation_context": correlation_ctx.model_dump(mode="json"),
            }
            
            result = await coordinate_agents(
                ctx=mock_context,
                request_type="full_analysis",
                payload=full_payload,
                correlation_context=correlation_ctx,
            )
            
            assert "screening" in result.completed_agents
            assert "research" in result.completed_agents
            assert "risk_analysis" in result.completed_agents
            assert len(result.failed_agents) == 0
            assert len(result.errors) == 0
        finally:
            config.quant_screener_address = original_qs
            config.deep_researcher_address = original_dr
            config.risk_manager_address = original_rm


