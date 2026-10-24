#!/usr/bin/env python3
"""Script to add new TestInterAgentCommunication class to test_agent_communication.py."""

with open('tests/test_agent_communication.py', 'r') as f:
    content = f.read()

new_tests = '''

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

    @pytest.fixture(autouse=True)
    def enable_agent_communication(self, monkeypatch):
        """Enable agent communication for tests and set mock addresses."""
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


    @pytest.mark.asyncio
    async def test_send_to_agent_success(self, mock_context, correlation_ctx):
        """Test successful message sending to a downstream agent."""
        from agents.orchestrator.agent import send_to_agent
        from schemas.screening import RankedShortlistResponse, ScreenedStock
        
        # Mock successful response
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
        
        # Return wrong type
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
    async def test_coordinate_agents_screening_success(self, mock_context, correlation_ctx, sample_screening_request):
        """Test coordinate_agents with successful screening."""
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
    async def test_coordinate_agents_research_success(self, mock_context, correlation_ctx, sample_research_request):
        """Test coordinate_agents with successful research."""
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
    async def test_coordinate_agents_risk_success(self, mock_context, correlation_ctx):
        """Test coordinate_agents with successful risk analysis."""
        from agents.orchestrator.agent import coordinate_agents
        from agents.risk_manager.schemas import RiskAnalysisResponse, ConcentrationRisk, VolatilityRisk, CorrelationRisk
        from schemas.portfolio import PortfolioAnalysisResponse, PortfolioSnapshot, HoldingSnapshot
        from decimal import Decimal
        
        # Create a proper PortfolioAnalysisResponse object
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


    @pytest.mark.asyncio
    async def test_coordinate_agents_partial_failure(self, mock_context, correlation_ctx, sample_screening_request):
        """Test coordinate_agents handles partial failures correctly."""
        from agents.orchestrator.agent import coordinate_agents
        from schemas.screening import RankedShortlistResponse, ScreenedStock
        
        # Mock screening success but research failure
        mock_context.send.side_effect = [
            RankedShortlistResponse(  # Screening success
                stocks=[ScreenedStock(ticker="RELIANCE.NS", score=85.0)],
                filters_applied=sample_screening_request.filters,
                total_screened=100,
                total_returned=1,
                correlation_context=correlation_ctx,
            ),
            Exception("DeepResearcher unavailable"),  # Research failure
        ]
        
        result = await coordinate_agents(
            ctx=mock_context,
            request_type="full_analysis",
            payload={**sample_screening_request.model_dump(mode="json"), "ticker": "RELIANCE.NS"},
            correlation_context=correlation_ctx,
        )
        
        # Screening should succeed
        assert "screening" in result.completed_agents
        # Research should fail
        assert "research" in result.failed_agents
        assert "research" in result.errors


    @pytest.mark.asyncio
    async def test_coordinate_agents_missing_address(self, mock_context, correlation_ctx, sample_screening_request):
        """Test coordinate_agents handles missing agent address gracefully."""
        from agents.orchestrator.agent import coordinate_agents, config
        
        # Ensure address is None
        original_address = config.quant_screener_address
        config.quant_screener_address = None
        
        try:
            result = await coordinate_agents(
                ctx=mock_context,
                request_type="screening",
                payload=sample_screening_request.model_dump(mode="json"),
                correlation_context=correlation_ctx,
            )
            
            # Should fall back to local service or record error
            assert "screening" in result.errors or "screening" in result.results
        finally:
            config.quant_screener_address = original_address


    @pytest.mark.asyncio
    async def test_correlation_context_propagation(self, mock_context, correlation_ctx):
        """Test that correlation context is properly propagated through agent communication."""
        from agents.orchestrator.agent import coordinate_agents
        from schemas.screening import RankedShortlistResponse, ScreenedStock, ScreeningFilters
        
        # Create a screening request with the test correlation context
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
        
        try:
            await coordinate_agents(
                ctx=mock_context,
                request_type="screening",
                payload=test_screening_request.model_dump(mode="json"),
                correlation_context=correlation_ctx,
            )
            
            # Verify correlation context was propagated
            assert captured_request is not None
            assert captured_request.correlation_context.request_id == correlation_ctx.request_id
            assert captured_request.correlation_context.conversation_id == correlation_ctx.conversation_id


    @pytest.mark.asyncio
    async def test_coordinate_agents_full_analysis_all_agents(self, mock_context, correlation_ctx):
        """Test coordinate_agents with full_analysis request_type using all agents."""
        from agents.orchestrator.agent import coordinate_agents, config
        from schemas.screening import RankedShortlistResponse, ScreenedStock, ScreeningFilters
        from schemas.research import AgenticThesisResponse, ThesisSection
        from agents.risk_manager.schemas import RiskAnalysisResponse, ConcentrationRisk, VolatilityRisk, CorrelationRisk
        from schemas.portfolio import PortfolioAnalysisResponse, PortfolioSnapshot, HoldingSnapshot
        from decimal import Decimal
        
        # Create proper PortfolioAnalysisResponse for risk response
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
        
        # Mock all three agent responses
        def mock_send(address, request, timeout):
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
        
        # Configure all addresses
        original_qs = config.quant_screener_address
        original_dr = config.deep_researcher_address
        original_rm = config.risk_manager_address
        config.quant_screener_address = "agent1qquant"
        config.deep_researcher_address = "agent1qresearch"
        config.risk_manager_address = "agent1qrisk"
        
        try:
            # Build full payload with proper enum values
            from decimal import Decimal
            from schemas.common import InvestmentHorizon, RiskProfile
            
            full_payload = {
                # Portfolio
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
            
            # All three agents should complete successfully
            assert "screening" in result.completed_agents
            assert "research" in result.completed_agents
            assert "risk_analysis" in result.completed_agents
            assert len(result.failed_agents) == 0
            assert len(result.errors) == 0
'''

# Add the new class at the end of the file
content = content.rstrip() + new_tests + "\n"

with open('tests/test_agent_communication.py', 'w') as f:
    f.write(content)
print("Tests added successfully")