from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import datetime
from schemas.common import CorrelationContext


class ScreeningFilters(BaseModel):
    """Filters for quantitative screening."""
    min_market_cap: Optional[Decimal] = Field(default=None, description="Minimum market cap (INR)")
    max_market_cap: Optional[Decimal] = Field(default=None, description="Maximum market cap (INR)")
    min_pe_ratio: Optional[float] = Field(default=None, description="Minimum P/E ratio")
    max_pe_ratio: Optional[float] = Field(default=None, description="Maximum P/E ratio")
    max_distance_from_52w_high_pct: Optional[float] = Field(
        default=None, description="Max % below 52-week high (e.g., 20 = within 20%)"
    )
    min_price_above_sma_50: Optional[bool] = Field(default=None, description="Price above 50-day SMA")
    min_price_above_sma_200: Optional[bool] = Field(default=None, description="Price above 200-day SMA")
    exclude_tickers: List[str] = Field(default_factory=list, description="Tickers to exclude")
    sector: Optional[str] = Field(default=None, description="Sector filter")


class ScreeningRequest(BaseModel):
    """Request for quantitative screening."""
    filters: ScreeningFilters = Field(default_factory=ScreeningFilters)
    max_results: int = Field(default=20, ge=1, le=100)
    correlation_context: CorrelationContext = Field(default_factory=CorrelationContext)


class ScreenedStock(BaseModel):
    """A stock that passed screening filters."""
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    distance_from_52w_high_pct: Optional[float] = None
    distance_from_52w_low_pct: Optional[float] = None
    sma_50: Optional[Decimal] = None
    sma_200: Optional[Decimal] = None
    price_above_sma_50: Optional[bool] = None
    price_above_sma_200: Optional[bool] = None
    volatility_30d: Optional[float] = None
    volume_avg_30d: Optional[int] = None
    score: float = Field(default=0.0, description="Composite screening score")
    price_timestamp: Optional[datetime] = None
    data_source: str = "yfinance"
    data_available: bool = True

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Ticker cannot be empty")
        if not (v.endswith(".NS") or v.endswith(".BO")):
            v = f"{v}.NS"
        return v


class RankedShortlistResponse(BaseModel):
    """Response with ranked screening results."""
    stocks: List[ScreenedStock] = Field(default_factory=list)
    filters_applied: ScreeningFilters
    total_screened: int = 0
    total_returned: int = 0
    correlation_context: CorrelationContext
    screening_timestamp: datetime = Field(default_factory=datetime.now)
    warnings: List[str] = Field(default_factory=list)
    methodology: str = Field(
        default=(
            "Screening based on yfinance data. Scores are composite of: "
            "value (inverse P/E), momentum (distance from 52w high), "
            "trend (SMA positioning), and quality (volatility). "
            "Lower P/E, closer to 52w high, above SMAs, lower volatility score higher."
        )
    )