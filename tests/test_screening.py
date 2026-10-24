"""Test screening service."""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.screening import (
    ScreeningRequest,
    ScreeningFilters,
    RankedShortlistResponse,
    ScreenedStock,
)
from schemas.common import CorrelationContext
from services.screening_service import ScreeningService, get_screening_service


class TestScreeningService:
    """Test ScreeningService with mocked market data."""

    @pytest.fixture
    def mock_market_data(self):
        """Create mock market data service with screening data."""
        mock = AsyncMock()
        
        async def mock_get_screening_data(ticker):
            data_map = {
                "RELIANCE.NS": {
                    "ticker": "RELIANCE.NS",
                    "short_name": "Reliance Industries",
                    "sector": "Energy",
                    "current_price": Decimal("2600"),
                    "market_cap": Decimal("1750000000000"),
                    "pe_ratio": 15.5,
                    "pb_ratio": 2.1,
                    "dividend_yield": 0.003,
                    "fifty_two_week_high": Decimal("2850"),
                    "fifty_two_week_low": Decimal("2100"),
                    "fifty_day_average": Decimal("2550"),
                    "two_hundred_day_average": Decimal("2400"),
                    "sma_50": Decimal("2550"),
                    "sma_200": Decimal("2400"),
                    "price_above_sma_50": True,
                    "price_above_sma_200": True,
                    "volatility_30d": 0.25,
                    "volume_avg_30d": 1000000,
                    "timestamp": datetime.now(),
                    "source": "yfinance",
                },
                "TCS.NS": {
                    "ticker": "TCS.NS",
                    "short_name": "Tata Consultancy Services",
                    "sector": "IT",
                    "current_price": Decimal("3900"),
                    "market_cap": Decimal("1400000000000"),
                    "pe_ratio": 28.0,
                    "pb_ratio": 12.0,
                    "dividend_yield": 0.015,
                    "fifty_two_week_high": Decimal("4200"),
                    "fifty_two_week_low": Decimal("3200"),
                    "fifty_day_average": Decimal("3850"),
                    "two_hundred_day_average": Decimal("3600"),
                    "sma_50": Decimal("3850"),
                    "sma_200": Decimal("3600"),
                    "price_above_sma_50": True,
                    "price_above_sma_200": True,
                    "volatility_30d": 0.20,
                    "volume_avg_30d": 500000,
                    "timestamp": datetime.now(),
                    "source": "yfinance",
                },
                "INFY.NS": {
                    "ticker": "INFY.NS",
                    "short_name": "Infosys",
                    "sector": "IT",
                    "current_price": Decimal("1500"),
                    "market_cap": Decimal("620000000000"),
                    "pe_ratio": 24.0,
                    "pb_ratio": 8.5,
                    "dividend_yield": 0.025,
                    "fifty_two_week_high": Decimal("1750"),
                    "fifty_two_week_low": Decimal("1300"),
                    "fifty_day_average": Decimal("1480"),
                    "two_hundred_day_average": Decimal("1450"),
                    "sma_50": Decimal("1480"),
                    "sma_200": Decimal("1450"),
                    "price_above_sma_50": True,
                    "price_above_sma_200": True,
                    "volatility_30d": 0.22,
                    "volume_avg_30d": 800000,
                    "timestamp": datetime.now(),
                    "source": "yfinance",
                },
            }
            return data_map.get(ticker)
        
        mock.get_screening_data = mock_get_screening_data
        return mock

    @pytest.mark.asyncio
    async def test_run_screening_basic(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        # Use small universe for testing
        service.universe = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        
        request = ScreeningRequest(
            filters=ScreeningFilters(),
            max_results=10,
        )
        
        result = await service.run_screening(request)
        
        assert isinstance(result, RankedShortlistResponse)
        assert result.total_screened == 3
        assert result.total_returned == 3
        assert len(result.stocks) == 3
        
        # Check all stocks have scores
        for stock in result.stocks:
            assert stock.score >= 0
            assert stock.ticker in ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

    @pytest.mark.asyncio
    async def test_run_screening_with_pe_filter(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        service.universe = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        
        request = ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=20.0),
            max_results=10,
        )
        
        result = await service.run_screening(request)
        
        # Only RELIANCE (PE 15.5) should pass
        assert result.total_returned == 1
        assert result.stocks[0].ticker == "RELIANCE.NS"

    @pytest.mark.asyncio
    async def test_run_screening_with_market_cap_filter(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        service.universe = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        
        request = ScreeningRequest(
            filters=ScreeningFilters(min_market_cap=Decimal("1000000000000")),  # 1L cr
            max_results=10,
        )
        
        result = await service.run_screening(request)
        
        # RELIANCE and TCS should pass (both > 1L cr), INFY should not (62K cr)
        assert result.total_returned == 2
        tickers = {s.ticker for s in result.stocks}
        assert "RELIANCE.NS" in tickers
        assert "TCS.NS" in tickers

    @pytest.mark.asyncio
    async def test_run_screening_exclude_tickers(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        service.universe = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        
        request = ScreeningRequest(
            filters=ScreeningFilters(exclude_tickers=["RELIANCE.NS"]),
            max_results=10,
        )
        
        result = await service.run_screening(request)
        
        assert result.total_returned == 2
        tickers = {s.ticker for s in result.stocks}
        assert "RELIANCE.NS" not in tickers
        assert "TCS.NS" in tickers
        assert "INFY.NS" in tickers

    @pytest.mark.asyncio
    async def test_run_screening_sma_filter(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        service.universe = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        
        request = ScreeningRequest(
            filters=ScreeningFilters(min_price_above_sma_50=True),
            max_results=10,
        )
        
        result = await service.run_screening(request)
        
        # All three are above SMA 50 in mock data
        assert result.total_returned == 3

    @pytest.mark.asyncio
    async def test_run_screening_max_results(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        service.universe = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        
        request = ScreeningRequest(
            filters=ScreeningFilters(),
            max_results=2,
        )
        
        result = await service.run_screening(request)
        
        assert result.total_returned == 2
        assert len(result.stocks) == 2

    @pytest.mark.asyncio
    async def test_run_screening_no_matches(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        service.universe = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        
        request = ScreeningRequest(
            filters=ScreeningFilters(max_pe_ratio=5.0),  # Too low
            max_results=10,
        )
        
        result = await service.run_screening(request)
        
        assert result.total_returned == 0
        assert len(result.warnings) > 0
        assert "No stocks matched" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_score_calculation(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        
        # Test that RELIANCE (low PE, above SMAs) scores higher than TCS (high PE)
        reliance_data = await mock_market_data.get_screening_data("RELIANCE.NS")
        tcs_data = await mock_market_data.get_screening_data("TCS.NS")
        
        reliance_score = service._calculate_score(reliance_data)
        tcs_score = service._calculate_score(tcs_data)
        
        # RELIANCE has lower PE (15.5 vs 28) so should score higher on value
        assert reliance_score > tcs_score

    @pytest.mark.asyncio
    async def test_distance_from_high_calculation(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        
        reliance_data = await mock_market_data.get_screening_data("RELIANCE.NS")
        dist = service._calc_distance_from_high(reliance_data)
        
        # (2850 - 2600) / 2850 * 100 = 8.77%
        assert dist == pytest.approx(8.77, rel=0.01)

    @pytest.mark.asyncio
    async def test_passes_filters(self, mock_market_data):
        service = ScreeningService(market_data_service=mock_market_data)
        
        reliance_data = await mock_market_data.get_screening_data("RELIANCE.NS")
        
        # Should pass
        filters = ScreeningFilters(max_pe_ratio=20.0)
        assert service._passes_filters(reliance_data, filters) is True
        
        # Should fail
        filters = ScreeningFilters(max_pe_ratio=10.0)
        assert service._passes_filters(reliance_data, filters) is False


class TestGetScreeningService:
    """Test service factory."""

    def test_get_screening_service(self):
        service = get_screening_service()
        assert isinstance(service, ScreeningService)
        assert len(service.universe) > 0