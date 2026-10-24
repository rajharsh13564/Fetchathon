from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from schemas.common import CorrelationContext, InvestmentHorizon, RiskProfile


class ResearchRequest(BaseModel):
    """Request for deep research on a company."""
    ticker: str
    company_name: Optional[str] = None
    include_quant_data: Optional[dict] = None
    investment_horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM
    risk_profile: RiskProfile = RiskProfile.MODERATE
    correlation_context: CorrelationContext = Field(default_factory=CorrelationContext)

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Ticker cannot be empty")
        if not (v.endswith(".NS") or v.endswith(".BO")):
            v = f"{v}.NS"
        return v


class EvidenceSource(BaseModel):
    """Source of evidence for research claims."""
    type: str  # "financial_data", "news", "filing", "model_knowledge"
    description: str
    timestamp: Optional[datetime] = None
    url: Optional[str] = None


class ThesisSection(BaseModel):
    """A section of the research thesis."""
    title: str
    content: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in this assessment")
    evidence: List[EvidenceSource] = Field(default_factory=list)
    key_metrics: dict = Field(default_factory=dict)


class AgenticThesisResponse(BaseModel):
    """Structured research response from DeepResearcher agent."""
    ticker: str
    company_name: str
    company_overview: ThesisSection
    bull_thesis: ThesisSection
    bear_thesis: ThesisSection
    financial_strengths: ThesisSection
    risks_and_uncertainties: ThesisSection
    valuation_observations: Optional[ThesisSection] = None
    investment_horizon_suitability: dict = Field(default_factory=dict)
    risk_profile_suitability: dict = Field(default_factory=dict)
    model_used: str
    data_sources: List[str] = Field(default_factory=list)
    research_timestamp: datetime = Field(default_factory=datetime.now)
    correlation_context: CorrelationContext
    disclaimer: str = Field(
        default="This research is for informational purposes only and does not constitute "
                "investment advice. Past performance does not guarantee future results."
    )

    def get_summary(self) -> str:
        """Get a brief summary of the research."""
        return (
            f"{self.company_name} ({self.ticker}): "
            f"Bull case - {self.bull_thesis.content[:100]}... | "
            f"Bear case - {self.bear_thesis.content[:100]}..."
        )