from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import datetime
from schemas.common import InvestmentHorizon, RiskProfile, CorrelationContext


class HoldingItem(BaseModel):
    """A single portfolio holding."""
    ticker: str = Field(..., description="NSE/BSE ticker symbol (e.g., RELIANCE.NS, TCS.NS)")
    shares: Decimal = Field(..., gt=0, description="Number of shares held")
    avg_purchase_price: Decimal = Field(..., gt=0, description="Average purchase price per share")
    purchase_date: Optional[datetime] = Field(default=None, description="Purchase date (optional)")

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Ticker cannot be empty")
        # Normalize common Indian ticker formats
        if not (v.endswith(".NS") or v.endswith(".BO")):
            # Default to NSE for Indian stocks
            v = f"{v}.NS"
        return v

    def investment_value(self) -> Decimal:
        """Calculate total invested amount for this holding."""
        return self.shares * self.avg_purchase_price


class PortfolioInput(BaseModel):
    """Input for portfolio analysis."""
    holdings: List[HoldingItem] = Field(..., min_length=1, description="List of holdings")
    investment_horizon: InvestmentHorizon = Field(default=InvestmentHorizon.MEDIUM)
    risk_profile: RiskProfile = Field(default=RiskProfile.MODERATE)
    correlation_context: CorrelationContext = Field(default_factory=CorrelationContext)

    @field_validator("holdings")
    @classmethod
    def validate_holdings(cls, v: List[HoldingItem]) -> List[HoldingItem]:
        if not v:
            raise ValueError("At least one holding is required")
        # Check for duplicate tickers
        tickers = [h.ticker for h in v]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Duplicate tickers found in holdings")
        return v

    def total_invested(self) -> Decimal:
        """Calculate total invested amount across all holdings."""
        return sum(h.investment_value() for h in self.holdings)


class HoldingSnapshot(BaseModel):
    """Current snapshot of a holding with market data."""
    ticker: str
    shares: Decimal
    avg_purchase_price: Decimal
    current_price: Optional[Decimal] = None
    price_timestamp: Optional[datetime] = None
    price_source: Optional[str] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[float] = None
    weight_pct: Optional[float] = None
    price_available: bool = False

    def calculate_metrics(self, total_portfolio_value: Decimal) -> None:
        """Calculate derived metrics."""
        if self.current_price is not None and self.current_price > 0:
            self.market_value = self.shares * self.current_price
            self.unrealized_pnl = self.market_value - self.investment_value()
            if self.investment_value() > 0:
                self.unrealized_pnl_pct = float(self.unrealized_pnl / self.investment_value() * 100)
            self.price_available = True
        else:
            self.price_available = False

        if total_portfolio_value > 0 and self.market_value is not None:
            self.weight_pct = float(self.market_value / total_portfolio_value * 100)

    def investment_value(self) -> Decimal:
        return self.shares * self.avg_purchase_price


class PortfolioSnapshot(BaseModel):
    """Complete portfolio snapshot with current market data."""
    holdings: List[HoldingSnapshot]
    total_invested: Decimal
    total_market_value: Optional[Decimal] = None
    total_unrealized_pnl: Optional[Decimal] = None
    total_unrealized_pnl_pct: Optional[float] = None
    data_timestamp: datetime = Field(default_factory=datetime.now)
    data_source: str = "yfinance"
    holdings_with_prices: int = 0
    holdings_without_prices: int = 0

    def calculate_totals(self) -> None:
        """Calculate portfolio-level totals."""
        self.total_market_value = sum(
            h.market_value for h in self.holdings if h.market_value is not None
        )
        if self.total_market_value is not None and self.total_market_value > 0:
            self.total_unrealized_pnl = self.total_market_value - self.total_invested
            if self.total_invested > 0:
                self.total_unrealized_pnl_pct = float(
                    self.total_unrealized_pnl / self.total_invested * 100
                )

        self.holdings_with_prices = sum(1 for h in self.holdings if h.price_available)
        self.holdings_without_prices = len(self.holdings) - self.holdings_with_prices


class PortfolioAnalysisResponse(BaseModel):
    """Response from portfolio analysis."""
    portfolio: PortfolioSnapshot
    concentration_analysis: dict = Field(default_factory=dict)
    risk_metrics: dict = Field(default_factory=dict)
    correlation_context: CorrelationContext
    warnings: List[str] = Field(default_factory=list)