"""Test research service."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.research import (
    ResearchRequest,
    AgenticThesisResponse,
    ThesisSection,
    EvidenceSource,
)
from schemas.common import CorrelationContext, InvestmentHorizon, RiskProfile
from services.research_service import ResearchService, get_research_service
from shared.errors import ConfigurationError, GeminiAPIError


class TestResearchService:
    """Test ResearchService with mocked Gemini client."""

    @pytest.fixture
    def mock_gemini_client(self):
        """Create mock Gemini client."""
        mock = AsyncMock()
        
        # Mock generate_json response
        mock.generate_json.return_value = {
            "company_overview": {
                "title": "Company Overview",
                "content": "Reliance Industries is a diversified conglomerate...",
                "confidence": 0.9,
                "evidence": [
                    {"type": "financial_data", "description": "Revenue: ₹8.5L cr", "timestamp": "2024-01-15"}
                ],
                "key_metrics": {"revenue": "₹8.5L cr", "employees": "300K+"}
            },
            "bull_thesis": {
                "title": "Bull Thesis",
                "content": "Strong growth in digital and retail segments...",
                "confidence": 0.75,
                "evidence": [
                    {"type": "financial_data", "description": "Jio subscribers 450M+"}
                ],
                "key_metrics": {"jio_subscribers": "450M+"}
            },
            "bear_thesis": {
                "title": "Bear Thesis",
                "content": "High debt and regulatory risks...",
                "confidence": 0.7,
                "evidence": [
                    {"type": "financial_data", "description": "Debt: ₹2.5L cr"}
                ],
                "key_metrics": {"debt": "₹2.5L cr"}
            },
            "financial_strengths": {
                "title": "Financial Strengths",
                "content": "Strong cash flows and market leadership...",
                "confidence": 0.85,
                "evidence": [],
                "key_metrics": {"operating_cash_flow": "₹1.2L cr"}
            },
            "risks_and_uncertainties": {
                "title": "Risks & Uncertainties",
                "content": "Regulatory changes and execution risks...",
                "confidence": 0.7,
                "evidence": [],
                "key_metrics": {}
            },
            "valuation_observations": {
                "title": "Valuation Observations",
                "content": "Trading at reasonable multiples...",
                "confidence": 0.65,
                "evidence": [],
                "key_metrics": {"pe_ratio": 15.5}
            },
        }
        
        return mock

    @pytest.mark.asyncio
    async def test_research_company_success(self, mock_gemini_client):
        service = ResearchService(gemini_client=mock_gemini_client)
        
        request = ResearchRequest(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            investment_horizon=InvestmentHorizon.MEDIUM,
            risk_profile=RiskProfile.MODERATE,
        )
        
        result = await service.research_company(request)
        
        assert isinstance(result, AgenticThesisResponse)
        assert result.ticker == "RELIANCE.NS"
        assert result.company_name == "Reliance Industries"
        assert result.model_used == "gemini-1.5-flash"
        assert len(result.data_sources) > 0
        
        # Check all sections present
        assert result.company_overview.title == "Company Overview"
        assert result.bull_thesis.title == "Bull Thesis"
        assert result.bear_thesis.title == "Bear Thesis"
        assert result.financial_strengths.title == "Financial Strengths"
        assert result.risks_and_uncertainties.title == "Risks & Uncertainties"
        assert result.valuation_observations is not None
        
        # Check evidence parsing
        assert len(result.company_overview.evidence) == 1
        assert result.company_overview.evidence[0].type == "financial_data"

    @pytest.mark.asyncio
    async def test_research_company_missing_gemini(self):
        service = ResearchService(gemini_client=None)
        
        request = ResearchRequest(ticker="RELIANCE.NS")
        
        with pytest.raises(ConfigurationError):
            await service.research_company(request)

    @pytest.mark.asyncio
    async def test_research_company_gemini_error(self, mock_gemini_client):
        mock_gemini_client.generate_json.side_effect = GeminiAPIError("API error")
        service = ResearchService(gemini_client=mock_gemini_client)
        
        request = ResearchRequest(ticker="RELIANCE.NS")
        
        with pytest.raises(GeminiAPIError):
            await service.research_company(request)

    def test_build_research_prompt(self):
        service = ResearchService()
        
        request = ResearchRequest(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            include_quant_data={"current_price": Decimal("2600"), "pe_ratio": 15.5},
            investment_horizon=InvestmentHorizon.LONG,
            risk_profile=RiskProfile.AGGRESSIVE,
        )
        
        prompt = service._build_research_prompt(request)
        
        assert "RELIANCE.NS" in prompt
        assert "Reliance Industries" in prompt
        assert "long" in prompt  # enum value is lowercase
        assert "aggressive" in prompt  # enum value is lowercase
        assert "QUANTITATIVE DATA" in prompt
        assert "15.5" in prompt

    def test_assess_horizon_suitability(self):
        service = ResearchService()
        
        sections = {
            "bull_thesis": ThesisSection(title="Bull", content="Growth", confidence=0.7),
            "bear_thesis": ThesisSection(title="Bear", content="Risks", confidence=0.6),
        }
        
        short = service._assess_horizon_suitability(InvestmentHorizon.SHORT, sections)
        assert short["suitable"] is False
        
        long = service._assess_horizon_suitability(InvestmentHorizon.LONG, sections)
        assert long["suitable"] is True

    def test_assess_risk_suitability(self):
        service = ResearchService()
        
        sections = {
            "risks_and_uncertainties": ThesisSection(title="Risks", content="High uncertainty", confidence=0.7),
        }
        
        conservative = service._assess_risk_suitability(RiskProfile.CONSERVATIVE, sections)
        assert conservative["suitable"] is False  # High uncertainty
        
        aggressive = service._assess_risk_suitability(RiskProfile.AGGRESSIVE, sections)
        assert aggressive["suitable"] is True


class TestGetResearchService:
    """Test service factory."""

    def test_get_research_service(self):
        service = get_research_service()
        assert isinstance(service, ResearchService)


# Need to import Decimal for the test
from decimal import Decimal