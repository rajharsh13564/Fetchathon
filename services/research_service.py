"""Deep research service using Gemini."""
from typing import Optional, Dict, Any
from datetime import datetime

from schemas.research import (
    ResearchRequest,
    AgenticThesisResponse,
    ThesisSection,
    EvidenceSource,
)
from schemas.common import CorrelationContext, InvestmentHorizon, RiskProfile
from services.gemini_client import get_gemini_client, GeminiClient
from config.settings import get_settings
from config.logging_config import get_logger
from shared.errors import GeminiAPIError, ConfigurationError

logger = get_logger(__name__)


class ResearchService:
    """Service for AI-powered fundamental research."""

    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini = gemini_client or get_gemini_client()
        self.settings = get_settings()

    async def research_company(
        self,
        request: ResearchRequest,
        correlation_context: Optional[CorrelationContext] = None,
    ) -> AgenticThesisResponse:
        """Conduct deep research on a company."""
        if correlation_context is None:
            correlation_context = request.correlation_context

        if not self.gemini:
            raise ConfigurationError(
                "Gemini API key not configured. Cannot perform research."
            )

        # Build research prompt
        prompt = self._build_research_prompt(request)

        # Get system prompt
        system_prompt = self.settings.finpilot_research_prompt

        # Generate research
        try:
            result = await self.gemini.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=8192,
            )
        except Exception as e:
            logger.error(f"Research generation failed: {e}")
            raise GeminiAPIError(f"Research generation failed: {str(e)}")

        # Parse and validate response
        thesis = self._parse_research_result(result, request, correlation_context)
        return thesis

    def _build_research_prompt(self, request: ResearchRequest) -> str:
        """Build the research prompt."""
        quant_data = request.include_quant_data or {}

        quant_section = ""
        if quant_data:
            quant_section = f"""
QUANTITATIVE DATA (from screening):
- Current Price: {quant_data.get('current_price', 'N/A')}
- P/E Ratio: {quant_data.get('pe_ratio', 'N/A')}
- P/B Ratio: {quant_data.get('pb_ratio', 'N/A')}
- Market Cap: {quant_data.get('market_cap', 'N/A')}
- 52W High Distance: {quant_data.get('distance_from_52w_high_pct', 'N/A')}%
- Above SMA 50: {quant_data.get('price_above_sma_50', 'N/A')}
- Above SMA 200: {quant_data.get('price_above_sma_200', 'N/A')}
- 30D Volatility: {quant_data.get('volatility_30d', 'N/A')}
"""

        return f"""
Conduct comprehensive fundamental research on {request.company_name or request.ticker} ({request.ticker}).

{quant_section}

INVESTMENT CONTEXT:
- Investment Horizon: {request.investment_horizon.value}
- Risk Profile: {request.risk_profile.value}

Provide a structured analysis with the following sections. For each section, provide:
1. Title
2. Detailed content (3-5 paragraphs)
3. Confidence level (0.0-1.0)
4. Evidence sources (financial_data, news, filing, model_knowledge)
5. Key metrics (relevant financial ratios, numbers)

SECTIONS REQUIRED:
1. Company Overview - Business model, market position, key products/services
2. Bull Thesis - Positive catalysts, growth drivers, competitive advantages
3. Bear Thesis - Risks, headwinds, competitive threats, valuation concerns
4. Financial Strengths - Profitability, balance sheet, cash flow, returns
5. Risks and Uncertainties - Specific, material risks with likelihood assessment
6. Valuation Observations - Relative and absolute valuation, key multiples

OUTPUT FORMAT (JSON):
{{
  "company_overview": {{"title": "...", "content": "...", "confidence": 0.0, "evidence": [], "key_metrics": {{}}}},
  "bull_thesis": {{"title": "...", "content": "...", "confidence": 0.0, "evidence": [], "key_metrics": {{}}}},
  "bear_thesis": {{"title": "...", "content": "...", "confidence": 0.0, "evidence": [], "key_metrics": {{}}}},
  "financial_strengths": {{"title": "...", "content": "...", "confidence": 0.0, "evidence": [], "key_metrics": {{}}}},
  "risks_and_uncertainties": {{"title": "...", "content": "...", "confidence": 0.0, "evidence": [], "key_metrics": {{}}}},
  "valuation_observations": {{"title": "...", "content": "...", "confidence": 0.0, "evidence": [], "key_metrics": {{}}}}
}}

IMPORTANT:
- Distinguish verified data from estimates/opinions
- Cite specific metrics and sources
- Be balanced - both bull and bear cases should be substantive
- Note data limitations and timestamp
- Do not guarantee returns or give personalized advice
"""

    def _parse_research_result(
        self,
        result: Dict[str, Any],
        request: ResearchRequest,
        correlation_context: CorrelationContext,
    ) -> AgenticThesisResponse:
        """Parse and validate research result."""

        def parse_section(data: Dict) -> ThesisSection:
            evidence = [
                EvidenceSource(
                    type=e.get("type", "model_knowledge"),
                    description=e.get("description", ""),
                    timestamp=datetime.fromisoformat(e["timestamp"]) if e.get("timestamp") else None,
                    url=e.get("url"),
                )
                for e in data.get("evidence", [])
            ]
            return ThesisSection(
                title=data.get("title", ""),
                content=data.get("content", ""),
                confidence=data.get("confidence", 0.5),
                evidence=evidence,
                key_metrics=data.get("key_metrics", {}),
            )

        sections = {}
        for key in ["company_overview", "bull_thesis", "bear_thesis",
                    "financial_strengths", "risks_and_uncertainties", "valuation_observations"]:
            if key in result:
                sections[key] = parse_section(result[key])
            else:
                sections[key] = ThesisSection(
                    title=key.replace("_", " ").title(),
                    content="Not available",
                    confidence=0.0,
                )

        # Build horizon and risk suitability
        horizon_suitability = {
            h.value: self._assess_horizon_suitability(h, sections)
            for h in InvestmentHorizon
        }
        risk_suitability = {
            r.value: self._assess_risk_suitability(r, sections)
            for r in RiskProfile
        }

        return AgenticThesisResponse(
            ticker=request.ticker,
            company_name=request.company_name or request.ticker,
            company_overview=sections["company_overview"],
            bull_thesis=sections["bull_thesis"],
            bear_thesis=sections["bear_thesis"],
            financial_strengths=sections["financial_strengths"],
            risks_and_uncertainties=sections["risks_and_uncertainties"],
            valuation_observations=sections.get("valuation_observations"),
            investment_horizon_suitability=horizon_suitability,
            risk_profile_suitability=risk_suitability,
            model_used=self.settings.gemini_model,
            data_sources=["yfinance", "gemini_model_knowledge"],
            research_timestamp=datetime.now(),
            correlation_context=correlation_context,
        )

    def _assess_horizon_suitability(
        self,
        horizon: InvestmentHorizon,
        sections: Dict[str, ThesisSection],
    ) -> Dict[str, Any]:
        """Assess suitability for investment horizon."""
        base = {
            "suitable": True,
            "reasoning": "",
            "confidence": 0.5,
        }

        if horizon == InvestmentHorizon.SHORT:
            base["reasoning"] = "Short horizon exposes to volatility; research focuses on fundamentals"
            base["suitable"] = False
        elif horizon == InvestmentHorizon.MEDIUM:
            base["reasoning"] = "Medium horizon aligns with business cycle and earnings visibility"
        else:
            base["reasoning"] = "Long horizon allows compounding of fundamentals and riding volatility"

        return base

    def _assess_risk_suitability(
        self,
        risk_profile: RiskProfile,
        sections: Dict[str, ThesisSection],
    ) -> Dict[str, Any]:
        """Assess suitability for risk profile."""
        base = {
            "suitable": True,
            "reasoning": "",
            "confidence": 0.5,
        }

        risks = sections.get("risks_and_uncertainties", ThesisSection(title="", content=""))

        if risk_profile == RiskProfile.CONSERVATIVE:
            base["reasoning"] = "Conservative investors should weigh risks carefully; high uncertainty may be unsuitable"
            base["suitable"] = "high" not in risks.content.lower() if risks.content else True
        elif risk_profile == RiskProfile.MODERATE:
            base["reasoning"] = "Moderate risk profile can accommodate balanced risk/reward"
        else:
            base["reasoning"] = "Aggressive profile may tolerate higher uncertainty for potential upside"

        return base


def get_research_service() -> ResearchService:
    """Get research service instance."""
    return ResearchService()