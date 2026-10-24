"""Quantitative screening service."""
import asyncio
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

from schemas.screening import (
    ScreeningRequest,
    RankedShortlistResponse,
    ScreenedStock,
    ScreeningFilters,
)
from schemas.common import CorrelationContext
from services.market_data import get_market_data_service
from config.logging_config import get_logger
from shared.errors import MarketDataError

logger = get_logger(__name__)


# Default Indian stock universe for screening (major NSE stocks)
DEFAULT_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "KOTAKBANK.NS", "BHARTIARTL.NS", "ITC.NS", "SBIN.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "NESTLEIND.NS",
    "POWERGRID.NS", "NTPC.NS", "ONGC.NS", "COALINDIA.NS", "TATAMOTORS.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "HINDALCO.NS",
    "INDUSINDBK.NS", "BAJAJFINSV.NS", "GRASIM.NS", "CIPLA.NS", "DRREDDY.NS",
    "APOLLOHOSP.NS", "DIVISLAB.NS", "BRITANNIA.NS", "HEROMOTOCO.NS", "EICHERMOT.NS",
    "BPCL.NS", "IOC.NS", "GAIL.NS", "VEDL.NS", "SHREECEM.NS",
]


class ScreeningService:
    """Service for quantitative stock screening."""

    def __init__(self, market_data_service=None, universe: Optional[List[str]] = None):
        self.market_data = market_data_service or get_market_data_service()
        self.universe = universe or DEFAULT_UNIVERSE

    async def run_screening(
        self,
        request: ScreeningRequest,
        correlation_context: Optional[CorrelationContext] = None,
    ) -> RankedShortlistResponse:
        """Run quantitative screening based on request filters."""
        if correlation_context is None:
            correlation_context = request.correlation_context

        # Determine universe (exclude user's holdings if specified)
        exclude = set(request.filters.exclude_tickers)
        universe = [t for t in self.universe if t not in exclude]

        logger.info(f"Screening {len(universe)} stocks with filters: {request.filters.model_dump()}")

        # Fetch data for all stocks concurrently (with semaphore to limit concurrency)
        semaphore = asyncio.Semaphore(10)

        async def fetch_with_semaphore(ticker: str) -> Optional[ScreenedStock]:
            async with semaphore:
                return await self._fetch_and_score_stock(ticker, request.filters)

        tasks = [fetch_with_semaphore(t) for t in universe]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect valid results
        stocks = []
        errors = 0
        for ticker, result in zip(universe, results):
            if isinstance(result, Exception):
                logger.debug(f"Error screening {ticker}: {result}")
                errors += 1
            elif result is not None:
                stocks.append(result)

        # Sort by score descending
        stocks.sort(key=lambda s: s.score, reverse=True)

        # Limit results
        stocks = stocks[:request.max_results]

        response = RankedShortlistResponse(
            stocks=stocks,
            filters_applied=request.filters,
            total_screened=len(universe),
            total_returned=len(stocks),
            correlation_context=correlation_context,
            screening_timestamp=datetime.now(),
            warnings=[],
        )

        if errors > 0:
            response.warnings.append(f"{errors} stocks had data errors and were skipped")

        if len(stocks) == 0:
            response.warnings.append("No stocks matched the screening criteria")

        return response

    async def _fetch_and_score_stock(
        self,
        ticker: str,
        filters: ScreeningFilters,
    ) -> Optional[ScreenedStock]:
        """Fetch data for a stock and calculate screening score."""
        data = await self.market_data.get_screening_data(ticker)
        if not data or not data.get("current_price"):
            return None

        # Apply filters
        if not self._passes_filters(data, filters):
            return None

        # Calculate score
        score = self._calculate_score(data)

        return ScreenedStock(
            ticker=data["ticker"],
            name=data.get("short_name") or data.get("long_name"),
            sector=data.get("sector"),
            market_cap=data.get("market_cap"),
            current_price=data.get("current_price"),
            pe_ratio=data.get("pe_ratio"),
            pb_ratio=data.get("pb_ratio"),
            dividend_yield=data.get("dividend_yield"),
            distance_from_52w_high_pct=self._calc_distance_from_high(data),
            distance_from_52w_low_pct=self._calc_distance_from_low(data),
            sma_50=data.get("sma_50"),
            sma_200=data.get("sma_200"),
            price_above_sma_50=data.get("price_above_sma_50"),
            price_above_sma_200=data.get("price_above_sma_200"),
            volatility_30d=data.get("volatility_30d"),
            volume_avg_30d=data.get("volume_avg_30d"),
            score=score,
            price_timestamp=data.get("timestamp"),
            data_source="yfinance",
            data_available=True,
        )

    def _passes_filters(self, data: Dict[str, Any], filters: ScreeningFilters) -> bool:
        """Check if stock passes all filters."""
        # Market cap filters
        market_cap = data.get("market_cap")
        if market_cap is not None:
            if filters.min_market_cap and market_cap < filters.min_market_cap:
                return False
            if filters.max_market_cap and market_cap > filters.max_market_cap:
                return False

        # P/E ratio filters
        pe = data.get("pe_ratio")
        if pe is not None:
            if filters.min_pe_ratio and pe < filters.min_pe_ratio:
                return False
            if filters.max_pe_ratio and pe > filters.max_pe_ratio:
                return False

        # Distance from 52-week high
        dist_high = self._calc_distance_from_high(data)
        if dist_high is not None and filters.max_distance_from_52w_high_pct is not None:
            if dist_high > filters.max_distance_from_52w_high_pct:
                return False

        # SMA filters
        if filters.min_price_above_sma_50 is not None:
            above_sma50 = data.get("price_above_sma_50")
            if above_sma50 is None or above_sma50 != filters.min_price_above_sma_50:
                return False

        if filters.min_price_above_sma_200 is not None:
            above_sma200 = data.get("price_above_sma_200")
            if above_sma200 is None or above_sma200 != filters.min_price_above_sma_200:
                return False

        return True

    def _calc_distance_from_high(self, data: Dict[str, Any]) -> Optional[float]:
        """Calculate % distance from 52-week high."""
        high = data.get("fifty_two_week_high")
        price = data.get("current_price")
        if high and price and high > 0:
            return round(float((high - price) / high * 100), 2)
        return None

    def _calc_distance_from_low(self, data: Dict[str, Any]) -> Optional[float]:
        """Calculate % distance from 52-week low."""
        low = data.get("fifty_two_week_low")
        price = data.get("current_price")
        if low and price and low > 0:
            return round(float((price - low) / low * 100), 2)
        return None

    def _calculate_score(self, data: Dict[str, Any]) -> float:
        """
        Calculate composite screening score (0-100).
        Higher is better.
        Components:
        - Value (inverse P/E): 30%
        - Momentum (distance from 52w high): 25%
        - Trend (SMA positioning): 25%
        - Quality (low volatility): 20%
        """
        score = 0.0
        weights = {
            "value": 0.30,
            "momentum": 0.25,
            "trend": 0.25,
            "quality": 0.20,
        }

        # Value score (lower P/E is better, cap at 50)
        pe = data.get("pe_ratio")
        if pe and pe > 0:
            value_score = max(0, min(100, (50 - pe) / 50 * 100))
            score += value_score * weights["value"]

        # Momentum score (closer to 52w high is better)
        dist_high = self._calc_distance_from_high(data)
        if dist_high is not None:
            momentum_score = max(0, min(100, (20 - dist_high) / 20 * 100))
            score += momentum_score * weights["momentum"]

        # Trend score (above SMAs)
        trend_score = 0
        trend_count = 0
        if data.get("price_above_sma_50") is not None:
            trend_score += 100 if data["price_above_sma_50"] else 0
            trend_count += 1
        if data.get("price_above_sma_200") is not None:
            trend_score += 100 if data["price_above_sma_200"] else 0
            trend_count += 1
        if trend_count > 0:
            score += (trend_score / trend_count) * weights["trend"]

        # Quality score (lower volatility is better)
        vol = data.get("volatility_30d")
        if vol is not None:
            # Assume 0-50% annualized vol range
            quality_score = max(0, min(100, (0.5 - vol) / 0.5 * 100))
            score += quality_score * weights["quality"]

        return round(score, 2)


def get_screening_service() -> ScreeningService:
    """Get screening service instance."""
    return ScreeningService()