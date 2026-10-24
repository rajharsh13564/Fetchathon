"""Test agent communication and message contracts."""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from uagents import Agent, Context
from uagents_core.models import Model

from schemas.common import CorrelationContext, ErrorResponse
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse, HoldingItem
from schemas.screening import ScreeningRequest, RankedShortlistResponse, ScreeningFilters
from schemas.research import ResearchRequest, AgenticThesisResponse
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
        """Verify no hardcoded agent addresses in code."""
        # This is a meta-test - the actual check is done by not having
        # placeholder addresses in the agent code
        from agents.orchestrator.agent import config
        
        # In local development, these should be None or from env
        # Not hardcoded placeholder addresses
        assert config.quant_screener_address is None or config.quant_screener_address == ""
        assert config.risk_manager_address is None or config.risk_manager_address == ""
        assert config.deep_researcher_address is None or config.deep_researcher_address == ""

    def test_agentverse_env_examples_have_placeholders(self):
        """Verify Agentverse env examples have placeholder addresses."""
        # These files should exist and contain placeholders
        import os
        
        orchestrator_env = "agents/orchestrator/agentverse.env.example"
        assert os.path.exists(orchestrator_env)
        
        with open(orchestrator_env) as f:
            content = f.read()
            assert "agent1qxxxxxxxx" in content  # Placeholder format
            assert "your_unique_orchestrator_seed_here" in content