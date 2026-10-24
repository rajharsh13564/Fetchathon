"""Market data service using yfinance."""
import asyncio
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from decimal import Decimal
from functools import lru_cache
import yfinance as yf
import pandas as pd

from config.settings import get_settings
from config.logging_config import get_logger
from shared.errors import MarketDataError

logger = get_logger(__name__)


class MarketDataService:
    """Service for fetching and caching market data."""

    def __init__(self, cache_ttl: Optional[int] = None):
        self.cache_ttl = cache_ttl or get_settings().market_data_cache_ttl
        self._quote_cache: Dict[str, tuple[Any, float]] = {}
        self._history_cache: Dict[str, tuple[pd.DataFrame, float]] = {}

    def _normalize_ticker(self, ticker: str) -> str:
        """Normalize ticker to yfinance format."""
        ticker = ticker.strip().upper()
        if not (ticker.endswith(".NS") or ticker.endswith(".BO")):
            ticker = f"{ticker}.NS"
        return ticker

    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if cache entry is still valid."""
        return (time.time() - timestamp) < self.cache_ttl

    async def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote for a ticker.
        Returns dict with price, change, volume, etc. or None if unavailable.
        """
        normalized = self._normalize_ticker(ticker)

        # Check cache
        if normalized in self._quote_cache:
            data, timestamp = self._quote_cache[normalized]
            if self._is_cache_valid(timestamp):
                logger.debug(f"Cache hit for {normalized}")
                return data

        try:
            # Run yfinance in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            ticker_obj = await loop.run_in_executor(None, yf.Ticker, normalized)
            info = await loop.run_in_executor(None, lambda: ticker_obj.info)

            if not info or info.get("regularMarketPrice") is None:
                logger.warning(f"No price data for {normalized}")
                return None

            quote = {
                "ticker": normalized,
                "current_price": Decimal(str(info.get("regularMarketPrice", 0))),
                "previous_close": Decimal(str(info.get("regularMarketPreviousClose", 0))),
                "change": Decimal(str(info.get("regularMarketChange", 0))),
                "change_percent": float(info.get("regularMarketChangePercent", 0)),
                "volume": info.get("regularMarketVolume", 0),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "dividend_yield": info.get("dividendYield"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "fifty_day_average": info.get("fiftyDayAverage"),
                "two_hundred_day_average": info.get("twoHundredDayAverage"),
                "short_name": info.get("shortName"),
                "long_name": info.get("longName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "currency": info.get("currency", "INR"),
                "timestamp": datetime.now(),
                "source": "yfinance",
            }

            # Cache the result
            self._quote_cache[normalized] = (quote, time.time())
            logger.debug(f"Fetched quote for {normalized}: {quote['current_price']}")
            return quote

        except Exception as e:
            logger.error(f"Error fetching quote for {normalized}: {e}")
            raise MarketDataError(f"Failed to fetch quote: {str(e)}", ticker=normalized)

    async def get_quotes(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get quotes for multiple tickers concurrently."""
        tasks = [self.get_quote(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        quotes = {}
        for ticker, result in zip(tickers, results):
            normalized = self._normalize_ticker(ticker)
            if isinstance(result, Exception):
                logger.error(f"Error fetching {normalized}: {result}")
                quotes[normalized] = None
            else:
                quotes[normalized] = result

        return quotes

    async def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Get historical price data."""
        normalized = self._normalize_ticker(ticker)
        cache_key = f"{normalized}:{period}:{interval}"

        if cache_key in self._history_cache:
            data, timestamp = self._history_cache[cache_key]
            if self._is_cache_valid(timestamp):
                return data

        try:
            loop = asyncio.get_event_loop()
            ticker_obj = await loop.run_in_executor(None, yf.Ticker, normalized)
            hist = await loop.run_in_executor(
                None,
                lambda: ticker_obj.history(period=period, interval=interval)
            )

            if hist is not None and not hist.empty:
                self._history_cache[cache_key] = (hist, time.time())
                return hist

            return None

        except Exception as e:
            logger.error(f"Error fetching history for {normalized}: {e}")
            raise MarketDataError(f"Failed to fetch history: {str(e)}", ticker=normalized)

    def calculate_sma(self, prices: pd.Series, window: int) -> Optional[Decimal]:
        """Calculate Simple Moving Average."""
        if len(prices) < window:
            return None
        sma = prices.rolling(window=window).mean().iloc[-1]
        return Decimal(str(round(sma, 2))) if not pd.isna(sma) else None

    def calculate_volatility(self, prices: pd.Series, window: int = 30) -> Optional[float]:
        """Calculate annualized volatility."""
        if len(prices) < window:
            return None
        returns = prices.pct_change().dropna()
        if len(returns) < window:
            return None
        vol = returns.tail(window).std() * (252 ** 0.5)  # Annualized
        return round(float(vol), 4) if not pd.isna(vol) else None

    def calculate_max_drawdown(self, prices: pd.Series) -> Optional[float]:
        """Calculate maximum drawdown."""
        if len(prices) < 2:
            return None
        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        max_dd = drawdown.min()
        return round(float(max_dd) * 100, 2) if not pd.isna(max_dd) else None

    async def get_screening_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive data for screening."""
        quote = await self.get_quote(ticker)
        if not quote:
            return None

        # Get 1 year history for technical indicators
        hist = await self.get_history(ticker, period="1y", interval="1d")
        if hist is None or hist.empty:
            return quote

        close_prices = hist["Close"]

        # Calculate technical indicators
        sma_50 = self.calculate_sma(close_prices, 50)
        sma_200 = self.calculate_sma(close_prices, 200)
        volatility_30d = self.calculate_volatility(close_prices, 30)
        max_drawdown = self.calculate_max_drawdown(close_prices)
        avg_volume_30d = int(hist["Volume"].tail(30).mean()) if len(hist) >= 30 else None

        quote.update({
            "sma_50": sma_50,
            "sma_200": sma_200,
            "price_above_sma_50": (
                quote["current_price"] > sma_50 if sma_50 and quote["current_price"] else None
            ),
            "price_above_sma_200": (
                quote["current_price"] > sma_200 if sma_200 and quote["current_price"] else None
            ),
            "volatility_30d": volatility_30d,
            "max_drawdown": max_drawdown,
            "volume_avg_30d": avg_volume_30d,
        })

        return quote

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._quote_cache.clear()
        self._history_cache.clear()
        logger.info("Market data cache cleared")


# Global instance
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """Get or create global market data service."""
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service