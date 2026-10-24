"""Test portfolio calculations and service."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.portfolio import PortfolioInput, HoldingItem
from schemas.common import CorrelationContext, InvestmentHorizon, RiskProfile
from services.portfolio_service import PortfolioService, get_portfolio_service


class TestPortfolioCalculations:
    """Test portfolio calculation logic."""

    def test_total_invested_calculation(self):
        portfolio = PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                HoldingItem(ticker="TCS.NS", shares=Decimal("5"), avg_purchase_price=Decimal("3800")),
            ]
        )
        assert portfolio.total_invested() == Decimal("43500")

    def test_holding_investment_value(self):
        holding = HoldingItem(
            ticker="RELIANCE.NS",
            shares=Decimal("10"),
            avg_purchase_price=Decimal("2450"),
        )
        assert holding.investment_value() == Decimal("24500")

    def test_extract_portfolio_from_text_simple(self):
        service = PortfolioService()
        text = "I have 10 RELIANCE.NS shares bought at 2450 and 5 TCS.NS shares bought at 3800"
        portfolio = service.extract_portfolio_from_text(text)
        
        assert portfolio is not None
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[0].ticker == "RELIANCE.NS"
        assert portfolio.holdings[0].shares == Decimal("10")
        assert portfolio.holdings[0].avg_purchase_price == Decimal("2450")

    def test_extract_portfolio_from_text_with_symbols(self):
        service = PortfolioService()
        text = "My portfolio: 10 shares of RELIANCE.NS at ₹2,450 and 5 TCS.NS @ 3800"
        portfolio = service.extract_portfolio_from_text(text)
        
        assert portfolio is not None
        assert len(portfolio.holdings) == 2

    def test_extract_portfolio_duplicate_removal(self):
        service = PortfolioService()
        text = "10 RELIANCE.NS at 2450 and 5 RELIANCE.NS at 2500"
        portfolio = service.extract_portfolio_from_text(text)
        
        assert portfolio is not None
        assert len(portfolio.holdings) == 1  # Duplicate removed

    def test_extract_portfolio_no_match(self):
        service = PortfolioService()
        text = "Hello, how are you?"
        portfolio = service.extract_portfolio_from_text(text)
        assert portfolio is None


class TestPortfolioService:
    """Test PortfolioService with mocked market data."""

    @pytest.fixture
    def mock_market_data(self):
        """Create mock market data service."""
        mock = AsyncMock()
        mock.get_quotes.return_value = {
            "RELIANCE.NS": {
                "ticker": "RELIANCE.NS",
                "current_price": Decimal("2600"),
                "previous_close": Decimal("2550"),
                "change": Decimal("50"),
                "change_percent": 1.96,
                "volume": 1000000,
                "market_cap": 1750000000000,
                "pe_ratio": 15.5,
                "short_name": "Reliance Industries",
                "sector": "Energy",
                "timestamp": None,
                "source": "yfinance",
            },
            "TCS.NS": {
                "ticker": "TCS.NS",
                "current_price": Decimal("3900"),
                "previous_close": Decimal("3850"),
                "change": Decimal("50"),
                "change_percent": 1.30,
                "volume": 500000,
                "market_cap": 1400000000000,
                "pe_ratio": 28.0,
                "short_name": "Tata Consultancy Services",
                "sector": "IT",
                "timestamp": None,
                "source": "yfinance",
            },
        }
        return mock

    @pytest.mark.asyncio
    async def test_analyze_portfolio_with_prices(self, mock_market_data):
        service = PortfolioService(market_data_service=mock_market_data)
        
        portfolio = PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                HoldingItem(ticker="TCS.NS", shares=Decimal("5"), avg_purchase_price=Decimal("3800")),
            ],
            investment_horizon=InvestmentHorizon.MEDIUM,
            risk_profile=RiskProfile.MODERATE,
        )
        
        result = await service.analyze_portfolio(portfolio)
        
        assert result.portfolio.total_invested == Decimal("43500")
        assert result.portfolio.total_market_value == Decimal("45500")
        assert result.portfolio.total_unrealized_pnl == Decimal("2000")
        assert result.portfolio.total_unrealized_pnl_pct == pytest.approx(4.60, rel=0.01)
        assert result.portfolio.holdings_with_prices == 2
        assert result.portfolio.holdings_without_prices == 0
        
        # Check holding details
        reliance = next(h for h in result.portfolio.holdings if h.ticker == "RELIANCE.NS")
        assert reliance.current_price == Decimal("2600")
        assert reliance.market_value == Decimal("26000")
        assert reliance.unrealized_pnl == Decimal("1500")
        assert reliance.weight_pct == pytest.approx(57.14, rel=0.01)

    @pytest.mark.asyncio
    async def test_analyze_portfolio_missing_prices(self, mock_market_data):
        mock_market_data.get_quotes.return_value = {
            "RELIANCE.NS": None,  # Missing price
            "TCS.NS": {
                "ticker": "TCS.NS",
                "current_price": Decimal("3900"),
                "source": "yfinance",
            },
        }
        
        service = PortfolioService(market_data_service=mock_market_data)
        
        portfolio = PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("10"), avg_purchase_price=Decimal("2450")),
                HoldingItem(ticker="TCS.NS", shares=Decimal("5"), avg_purchase_price=Decimal("3800")),
            ],
        )
        
        result = await service.analyze_portfolio(portfolio)
        
        assert result.portfolio.holdings_with_prices == 1
        assert result.portfolio.holdings_without_prices == 1
        assert len(result.warnings) == 1
        assert "RELIANCE.NS" in result.warnings[0]
        
        # TCS should have data
        tcs = next(h for h in result.portfolio.holdings if h.ticker == "TCS.NS")
        assert tcs.price_available is True
        
        # Reliance should not
        reliance = next(h for h in result.portfolio.holdings if h.ticker == "RELIANCE.NS")
        assert reliance.price_available is False

    @pytest.mark.asyncio
    async def test_concentration_analysis(self):
        # Create a dedicated mock for this test with prices for both tickers
        mock_market_data = AsyncMock()
        mock_market_data.get_quotes.return_value = {
            "RELIANCE.NS": {
                "ticker": "RELIANCE.NS",
                "current_price": Decimal("2600"),
                "source": "yfinance",
            },
            "TCS.NS": {
                "ticker": "TCS.NS",
                "current_price": Decimal("3900"),
                "source": "yfinance",
            },
        }
        
        service = PortfolioService(market_data_service=mock_market_data)
        
        # Create concentrated portfolio
        portfolio = PortfolioInput(
            holdings=[
                HoldingItem(ticker="RELIANCE.NS", shares=Decimal("100"), avg_purchase_price=Decimal("2450")),
                HoldingItem(ticker="TCS.NS", shares=Decimal("1"), avg_purchase_price=Decimal("3800")),
            ],
        )
        
        result = await service.analyze_portfolio(portfolio)
        
        conc = result.concentration_analysis
        assert conc["total_holdings"] == 2
        assert conc["top_5_concentration_pct"] > 90  # Highly concentrated
        assert conc["hhi"] > 0.5  # Very high HHI
        assert conc["concentration_level"] == "Very High (concentrated)"
        assert conc["largest_holding"]["ticker"] == "RELIANCE.NS"


class TestGetPortfolioService:
    """Test service factory."""

    def test_get_portfolio_service(self):
        service = get_portfolio_service()
        assert isinstance(service, PortfolioService)