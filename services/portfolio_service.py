"""Portfolio analysis service."""
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

from schemas.portfolio import (
    PortfolioInput,
    PortfolioSnapshot,
    HoldingSnapshot,
    PortfolioAnalysisResponse,
    HoldingItem,
)
from schemas.common import CorrelationContext
from services.market_data import get_market_data_service
from config.logging_config import get_logger
from shared.errors import MarketDataError, InsufficientDataError

logger = get_logger(__name__)


class PortfolioService:
    """Service for portfolio analysis and calculations."""

    def __init__(self, market_data_service=None):
        self.market_data = market_data_service or get_market_data_service()

    async def analyze_portfolio(
        self,
        portfolio_input: PortfolioInput,
        correlation_context: Optional[CorrelationContext] = None,
    ) -> PortfolioAnalysisResponse:
        """
        Analyze a portfolio with current market data.
        """
        if correlation_context is None:
            correlation_context = portfolio_input.correlation_context

        # Extract tickers
        tickers = [h.ticker for h in portfolio_input.holdings]

        # Fetch current quotes
        quotes = await self.market_data.get_quotes(tickers)

        # Build holding snapshots
        holding_snapshots = []
        warnings = []

        for holding in portfolio_input.holdings:
            quote = quotes.get(holding.ticker)

            snapshot = HoldingSnapshot(
                ticker=holding.ticker,
                shares=holding.shares,
                avg_purchase_price=holding.avg_purchase_price,
                purchase_date=holding.purchase_date,
            )

            if quote and quote.get("current_price") is not None:
                snapshot.current_price = quote["current_price"]
                snapshot.price_timestamp = quote.get("timestamp")
                snapshot.price_source = quote.get("source", "yfinance")
            else:
                warnings.append(f"No price data available for {holding.ticker}")

            holding_snapshots.append(snapshot)

        # Create portfolio snapshot
        total_invested = portfolio_input.total_invested()
        portfolio_snapshot = PortfolioSnapshot(
            holdings=holding_snapshots,
            total_invested=total_invested,
            data_source="yfinance",
        )

        # First pass: calculate market values for each holding (without weights)
        for snapshot in portfolio_snapshot.holdings:
            snapshot.calculate_metrics(Decimal("0"))  # Pass 0 to skip weight calculation

        # Calculate portfolio totals (now market_value is set)
        portfolio_snapshot.calculate_totals()

        # Second pass: calculate weights with correct total market value
        for snapshot in portfolio_snapshot.holdings:
            if snapshot.market_value is not None and portfolio_snapshot.total_market_value:
                snapshot.weight_pct = float(snapshot.market_value / portfolio_snapshot.total_market_value * 100)

        # Analyze concentration
        concentration = self._analyze_concentration(portfolio_snapshot)

        # Basic risk metrics
        risk_metrics = self._calculate_risk_metrics(portfolio_snapshot)

        response = PortfolioAnalysisResponse(
            portfolio=portfolio_snapshot,
            concentration_analysis=concentration,
            risk_metrics=risk_metrics,
            correlation_context=correlation_context,
            warnings=warnings,
        )

        return response

    def _analyze_concentration(self, snapshot: PortfolioSnapshot) -> Dict[str, Any]:
        """Analyze portfolio concentration."""
        if not snapshot.holdings:
            return {}

        # Top holdings by weight
        holdings_with_weight = [
            h for h in snapshot.holdings if h.weight_pct is not None
        ]
        holdings_with_weight.sort(key=lambda x: x.weight_pct or 0, reverse=True)

        top_5_weight = sum(h.weight_pct or 0 for h in holdings_with_weight[:5])
        top_10_weight = sum(h.weight_pct or 0 for h in holdings_with_weight[:10])

        # Herfindahl-Hirschman Index (HHI)
        hhi = sum((h.weight_pct or 0) ** 2 for h in holdings_with_weight) / 10000

        # Number of effective holdings (1/HHI)
        effective_holdings = 1 / (hhi * 10000) if hhi > 0 else 0

        return {
            "total_holdings": len(snapshot.holdings),
            "top_5_concentration_pct": round(top_5_weight, 2),
            "top_10_concentration_pct": round(top_10_weight, 2),
            "hhi": round(hhi, 4),
            "effective_holdings": round(effective_holdings, 1),
            "largest_holding": {
                "ticker": holdings_with_weight[0].ticker,
                "weight_pct": round(holdings_with_weight[0].weight_pct or 0, 2),
            } if holdings_with_weight else None,
            "concentration_level": self._get_concentration_level(hhi),
        }

    def _get_concentration_level(self, hhi: float) -> str:
        """Get concentration level description from HHI."""
        if hhi < 0.15:
            return "Low (well diversified)"
        elif hhi < 0.25:
            return "Moderate"
        elif hhi < 0.50:
            return "High"
        else:
            return "Very High (concentrated)"

    def _calculate_risk_metrics(self, snapshot: PortfolioSnapshot) -> Dict[str, Any]:
        """Calculate basic portfolio risk metrics."""
        holdings_with_prices = [h for h in snapshot.holdings if h.price_available]

        if len(holdings_with_prices) < 2:
            return {
                "warning": "Insufficient price data for risk metrics",
                "holdings_with_prices": len(holdings_with_prices),
            }

        # Weighted average volatility (simplified - would need historical data for proper calc)
        # This is a placeholder - real implementation would use historical returns
        return {
            "holdings_with_prices": len(holdings_with_prices),
            "holdings_without_prices": snapshot.holdings_without_prices,
            "data_completeness_pct": round(
                snapshot.holdings_with_prices / len(snapshot.holdings) * 100, 1
            ) if snapshot.holdings else 0,
            "note": "Historical volatility and correlation analysis requires RiskManager agent",
        }

    def extract_portfolio_from_text(
        self,
        text: str,
    ) -> Optional[PortfolioInput]:
        """
        Attempt to extract portfolio holdings from natural language text.
        This is a simple heuristic - production would use LLM.
        """
        import re

        # Pattern: "X shares of TICKER at ₹Y" or "X TICKER @ Y" or "X TICKER shares bought at Y"
        patterns = [
            r"(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?([A-Z]{2,10}(?:\.NS|\.BO)?)\s+(?:at|@|bought at)\s*[₹$]?\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+([A-Z]{2,10}(?:\.NS|\.BO)?)\s+(?:at|@)\s*[₹$]?\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+([A-Z]{2,10}(?:\.NS|\.BO)?)\s+shares?\s+(?:at|bought at)\s*[₹$]?\s*(\d+(?:\.\d+)?)",
        ]

        holdings = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    shares = Decimal(match[0])
                    ticker = match[1].upper()
                    price = Decimal(match[2])

                    if not (ticker.endswith(".NS") or ticker.endswith(".BO")):
                        ticker = f"{ticker}.NS"

                    holdings.append(HoldingItem(
                        ticker=ticker,
                        shares=shares,
                        avg_purchase_price=price,
                    ))
                except Exception:
                    continue

        if holdings:
            # Remove duplicates (keep first)
            seen = set()
            unique_holdings = []
            for h in holdings:
                if h.ticker not in seen:
                    seen.add(h.ticker)
                    unique_holdings.append(h)

            return PortfolioInput(holdings=unique_holdings)

        return None


def get_portfolio_service() -> PortfolioService:
    """Get portfolio service instance."""
    return PortfolioService()