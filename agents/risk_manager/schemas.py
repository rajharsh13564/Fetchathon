"""RiskManager-specific message schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from schemas.common import CorrelationContext, AgentStatus
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse


class RiskAnalysisRequest(BaseModel):
    """Request for risk analysis."""
    portfolio: PortfolioInput
    investment_horizon: Optional[str] = None
    risk_profile: Optional[str] = None
    correlation_context: CorrelationContext = Field(default_factory=CorrelationContext)
    include_historical: bool = True
    lookback_days: int = 252


class ConcentrationRisk(BaseModel):
    """Concentration risk metrics."""
    hhi: float
    effective_holdings: float
    top_5_concentration_pct: float
    top_10_concentration_pct: float
    largest_holding_weight_pct: float
    concentration_level: str
    warnings: List[str] = Field(default_factory=list)


class VolatilityRisk(BaseModel):
    """Volatility risk metrics."""
    portfolio_volatility_annualized: Optional[float] = None
    holdings_volatility: Dict[str, float] = Field(default_factory=dict)
    max_drawdown_estimate: Optional[float] = None
    var_95_1d: Optional[float] = None  # Value at Risk 95% 1-day
    data_quality: str = "insufficient"  # "good", "partial", "insufficient"
    warnings: List[str] = Field(default_factory=list)


class CorrelationRisk(BaseModel):
    """Correlation risk metrics."""
    sector_concentration: Dict[str, float] = Field(default_factory=dict)
    high_correlation_pairs: List[Dict[str, Any]] = Field(default_factory=list)
    diversification_ratio: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)


class RiskAnalysisResponse(BaseModel):
    """Comprehensive risk analysis response."""
    portfolio_snapshot: PortfolioAnalysisResponse
    concentration_risk: ConcentrationRisk
    volatility_risk: VolatilityRisk
    correlation_risk: CorrelationRisk
    overall_risk_score: float = Field(ge=0.0, le=100.0, description="0-100, higher = riskier")
    risk_level: str  # "Low", "Moderate", "High", "Very High"
    recommendations: List[str] = Field(default_factory=list)
    correlation_context: CorrelationContext
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    data_limitations: List[str] = Field(default_factory=list)


class RiskManagerStatus(BaseModel):
    """RiskManager agent status."""
    status: AgentStatus = AgentStatus.HEALTHY
    last_analysis: Optional[float] = None


class RiskManagerConfig(BaseModel):
    """Configuration for RiskManager agent."""
    concentration_threshold_hhi: float = 0.25
    max_single_holding_pct: float = 20.0
    max_sector_pct: float = 30.0
    var_confidence: float = 0.95
    lookback_days: int = 252