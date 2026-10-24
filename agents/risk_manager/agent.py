"""RiskManager Agent - Portfolio risk analysis."""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal

from uagents import Agent, Context, Protocol
from uagents_core.models import Model

from config.settings import get_settings
from config.logging_config import setup_logging, get_logger
from schemas.common import CorrelationContext, ErrorResponse
from schemas.portfolio import PortfolioInput, PortfolioAnalysisResponse, HoldingSnapshot
from agents.risk_manager.schemas import (
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    ConcentrationRisk,
    VolatilityRisk,
    CorrelationRisk,
    RiskManagerStatus,
    RiskManagerConfig,
)
from services.market_data import get_market_data_service
from services.portfolio_service import get_portfolio_service
from shared.protocol import RISK_MANAGER_PROTOCOL
from shared.errors import MarketDataError, InsufficientDataError

setup_logging()
logger = get_logger(__name__)

settings = get_settings()

# Create RiskManager agent
risk_manager = Agent(
    name="finpilot-risk-manager",
    seed=settings.risk_manager_seed,
    port=8003,
    mailbox=settings.risk_manager_mailbox_key,
)

# Protocol
risk_manager_protocol = Protocol(name=RISK_MANAGER_PROTOCOL, version="1.0.0")

# Services
market_data = get_market_data_service()
portfolio_service = get_portfolio_service()

# Configuration
config = RiskManagerConfig()


# ============================================================================
# Helper Functions
# ============================================================================

async def fetch_historical_data(
    tickers: List[str],
    lookback_days: int = 252,
) -> Dict[str, Any]:
    """Fetch historical price data for tickers."""
    period = f"{lookback_days}d" if lookback_days <= 365 else "1y"
    results = {}

    semaphore = asyncio.Semaphore(5)

    async def fetch_one(ticker: str):
        async with semaphore:
            try:
                hist = await market_data.get_history(ticker, period=period, interval="1d")
                if hist is not None and not hist.empty:
                    results[ticker] = hist["Close"]
            except Exception as e:
                logger.warning(f"Failed to fetch history for {ticker}: {e}")

    await asyncio.gather(*[fetch_one(t) for t in tickers])
    return results


def calculate_concentration_risk(snapshot: PortfolioAnalysisResponse) -> ConcentrationRisk:
    """Calculate concentration risk metrics."""
    conc = snapshot.concentration_analysis
    warnings = []

    hhi = conc.get("hhi", 0)
    top_5 = conc.get("top_5_concentration_pct", 0)
    top_10 = conc.get("top_10_concentration_pct", 0)
    largest = conc.get("largest_holding", {}).get("weight_pct", 0)
    effective = conc.get("effective_holdings", 0)

    if hhi > config.concentration_threshold_hhi:
        warnings.append(f"High concentration (HHI: {hhi:.3f} > {config.concentration_threshold_hhi})")
    if largest > config.max_single_holding_pct:
        warnings.append(f"Largest holding ({largest:.1f}%) exceeds threshold ({config.max_single_holding_pct}%)")

    # Determine concentration level
    if hhi < 0.15:
        level = "Low"
    elif hhi < 0.25:
        level = "Moderate"
    elif hhi < 0.50:
        level = "High"
    else:
        level = "Very High"

    return ConcentrationRisk(
        hhi=hhi,
        effective_holdings=effective,
        top_5_concentration_pct=top_5,
        top_10_concentration_pct=top_10,
        largest_holding_weight_pct=largest,
        concentration_level=level,
        warnings=warnings,
    )


def calculate_volatility_risk(
    snapshot: PortfolioAnalysisResponse,
    historical_data: Dict[str, Any],
) -> VolatilityRisk:
    """Calculate volatility risk metrics."""
    warnings = []
    holdings_vol = {}
    portfolio_returns = None
    weights = {}

    # Calculate weights from current market values
    total_value = snapshot.portfolio.total_market_value or Decimal("0")
    if total_value > 0:
        for h in snapshot.portfolio.holdings:
            if h.market_value and h.price_available:
                weights[h.ticker] = float(h.market_value / total_value)

    # Calculate individual holding volatilities
    for ticker, prices in historical_data.items():
        vol = market_data.calculate_volatility(prices, window=30)
        if vol is not None:
            holdings_vol[ticker] = vol

    # Calculate portfolio volatility (simplified - assumes zero correlation)
    # Real implementation would use covariance matrix
    if weights and holdings_vol:
        portfolio_var = sum(
            (weights.get(t, 0) ** 2) * (holdings_vol.get(t, 0) ** 2)
            for t in weights
        )
        portfolio_vol = portfolio_var ** 0.5
    else:
        portfolio_vol = None
        warnings.append("Insufficient data for portfolio volatility calculation")

    # Max drawdown estimate (from individual holdings)
    max_dd = None
    for ticker, prices in historical_data.items():
        dd = market_data.calculate_max_drawdown(prices)
        if dd is not None:
            if max_dd is None or dd < max_dd:
                max_dd = dd

    # VaR estimate (parametric, assuming normal distribution)
    var_95 = None
    if portfolio_vol is not None:
        # 1-day 95% VaR = portfolio_value * 1.645 * daily_vol
        daily_vol = portfolio_vol / (252 ** 0.5)
        var_95 = float(total_value) * 1.645 * daily_vol if total_value > 0 else None

    # Data quality assessment
    holdings_with_hist = len(historical_data)
    holdings_total = len(snapshot.portfolio.holdings)
    if holdings_with_hist == holdings_total and holdings_total > 0:
        data_quality = "good"
    elif holdings_with_hist > 0:
        data_quality = "partial"
    else:
        data_quality = "insufficient"
        warnings.append("No historical data available for volatility analysis")

    return VolatilityRisk(
        portfolio_volatility_annualized=round(portfolio_vol * 100, 2) if portfolio_vol else None,
        holdings_volatility={k: round(v * 100, 2) for k, v in holdings_vol.items()},
        max_drawdown_estimate=max_dd,
        var_95_1d=round(var_95, 2) if var_95 else None,
        data_quality=data_quality,
        warnings=warnings,
    )


def calculate_correlation_risk(
    snapshot: PortfolioAnalysisResponse,
    historical_data: Dict[str, Any],
) -> CorrelationRisk:
    """Calculate correlation and sector risk."""
    warnings = []
    sector_concentration = {}

    # Sector concentration (would need sector data from market_data)
    # For now, use basic ticker-based approximation
    for h in snapshot.portfolio.holdings:
        if h.market_value and h.price_available:
            # Simple sector mapping (in production, use actual sector data)
            sector = "Unknown"
            ticker_base = h.ticker.replace(".NS", "").replace(".BO", "")
            if ticker_base in ["RELIANCE", "ONGC", "IOC", "BPCL", "GAIL"]:
                sector = "Energy"
            elif ticker_base in ["TCS", "INFY", "WIPRO", "HCLTECH"]:
                sector = "IT"
            elif ticker_base in ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "INDUSINDBK"]:
                sector = "Banking"
            elif ticker_base in ["HINDUNILVR", "NESTLEIND", "BRITANNIA", "ITC"]:
                sector = "FMCG"
            elif ticker_base in ["MARUTI", "TATAMOTORS", "HEROMOTOCO", "EICHERMOT", "BAJAJFINSV"]:
                sector = "Auto"
            elif ticker_base in ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"]:
                sector = "Pharma"
            elif ticker_base in ["LT", "ULTRACEMCO", "SHREECEM", "GRASIM"]:
                sector = "Construction/Infra"

            weight = float(h.market_value / (snapshot.portfolio.total_market_value or Decimal("1")))
            sector_concentration[sector] = sector_concentration.get(sector, 0) + weight * 100

    # Check sector concentration
    for sector, pct in sector_concentration.items():
        if pct > config.max_sector_pct:
            warnings.append(f"High sector concentration: {sector} at {pct:.1f}%")

    # Diversification ratio (simplified)
    div_ratio = None
    if len(sector_concentration) > 1:
        div_ratio = 1 / sum((pct / 100) ** 2 for pct in sector_concentration.values())

    return CorrelationRisk(
        sector_concentration={k: round(v, 2) for k, v in sector_concentration.items()},
        high_correlation_pairs=[],  # Would need pairwise correlation
        diversification_ratio=round(div_ratio, 2) if div_ratio else None,
        warnings=warnings,
    )


def calculate_overall_risk_score(
    concentration: ConcentrationRisk,
    volatility: VolatilityRisk,
    correlation: CorrelationRisk,
) -> tuple[float, str]:
    """Calculate overall risk score (0-100)."""
    score = 0.0

    # Concentration component (0-40 points)
    if concentration.hhi < 0.15:
        score += 5
    elif concentration.hhi < 0.25:
        score += 15
    elif concentration.hhi < 0.50:
        score += 30
    else:
        score += 40

    # Volatility component (0-35 points)
    if volatility.portfolio_volatility_annualized is not None:
        vol = volatility.portfolio_volatility_annualized
        if vol < 15:
            score += 5
        elif vol < 25:
            score += 15
        elif vol < 40:
            score += 25
        else:
            score += 35
    else:
        score += 15  # Unknown volatility = moderate penalty

    # Correlation/Diversification component (0-25 points)
    if correlation.diversification_ratio is not None:
        dr = correlation.diversification_ratio
        if dr > 3:
            score += 5
        elif dr > 2:
            score += 12
        elif dr > 1.5:
            score += 20
        else:
            score += 25
    else:
        score += 15

    # Risk level
    if score < 25:
        level = "Low"
    elif score < 50:
        level = "Moderate"
    elif score < 75:
        level = "High"
    else:
        level = "Very High"

    return round(score, 1), level


def generate_recommendations(
    concentration: ConcentrationRisk,
    volatility: VolatilityRisk,
    correlation: CorrelationRisk,
) -> List[str]:
    """Generate risk management recommendations."""
    recs = []

    if concentration.hhi > config.concentration_threshold_hhi:
        recs.append("Consider diversifying: portfolio is highly concentrated (HHI > 0.25)")

    if concentration.largest_holding_weight_pct > config.max_single_holding_pct:
        recs.append(f"Largest holding ({concentration.largest_holding_weight_pct:.1f}%) exceeds {config.max_single_holding_pct}% threshold")

    for sector, pct in correlation.sector_concentration.items():
        if pct > config.max_sector_pct:
            recs.append(f"Sector concentration: {sector} at {pct:.1f}% (consider reducing)")

    if volatility.data_quality == "insufficient":
        recs.append("Unable to calculate volatility metrics - insufficient historical data")

    if volatility.portfolio_volatility_annualized and volatility.portfolio_volatility_annualized > 30:
        recs.append("High portfolio volatility - consider adding lower-volatility assets")

    if correlation.diversification_ratio and correlation.diversification_ratio < 2:
        recs.append("Low diversification ratio - holdings may be highly correlated")

    if not recs:
        recs.append("Portfolio risk profile appears balanced")

    return recs


# ============================================================================
# Message Handlers
# ============================================================================

@risk_manager_protocol.on_message(model=RiskAnalysisRequest, replies=RiskAnalysisResponse)
async def handle_risk_analysis(ctx: Context, sender: str, msg: RiskAnalysisRequest):
    """Handle risk analysis request."""
    logger.info(f"Risk analysis request from {sender} for {len(msg.portfolio.holdings)} holdings")

    try:
        # First get portfolio analysis with current prices
        portfolio_analysis = await portfolio_service.analyze_portfolio(
            msg.portfolio, msg.correlation_context
        )

        # Fetch historical data for volatility/correlation analysis
        tickers = [h.ticker for h in msg.portfolio.holdings]
        historical_data = {}
        if msg.include_historical:
            historical_data = await fetch_historical_data(tickers, msg.lookback_days)

        # Calculate risk components
        concentration_risk = calculate_concentration_risk(portfolio_analysis)
        volatility_risk = calculate_volatility_risk(portfolio_analysis, historical_data)
        correlation_risk = calculate_correlation_risk(portfolio_analysis, historical_data)

        # Overall risk
        overall_score, risk_level = calculate_overall_risk_score(
            concentration_risk, volatility_risk, correlation_risk
        )

        # Recommendations
        recommendations = generate_recommendations(
            concentration_risk, volatility_risk, correlation_risk
        )

        # Data limitations
        limitations = []
        if not historical_data:
            limitations.append("No historical price data available for volatility/correlation analysis")
        elif len(historical_data) < len(tickers):
            missing = set(tickers) - set(historical_data.keys())
            limitations.append(f"Missing historical data for: {', '.join(missing)}")

        limitations.extend(concentration_risk.warnings)
        limitations.extend(volatility_risk.warnings)
        limitations.extend(correlation_risk.warnings)

        response = RiskAnalysisResponse(
            portfolio_snapshot=portfolio_analysis,
            concentration_risk=concentration_risk,
            volatility_risk=volatility_risk,
            correlation_risk=correlation_risk,
            overall_risk_score=overall_score,
            risk_level=risk_level,
            recommendations=recommendations,
            correlation_context=msg.correlation_context,
            analysis_timestamp=datetime.now(),
            data_limitations=limitations,
        )

        await ctx.send(sender, response)

    except MarketDataError as e:
        logger.error(f"Market data error: {e}")
        error_resp = ErrorResponse(
            error=str(e),
            code="MARKET_DATA_ERROR",
            details=e.details,
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)
    except Exception as e:
        logger.error(f"Risk analysis error: {e}")
        error_resp = ErrorResponse(
            error=f"Risk analysis failed: {str(e)}",
            code="RISK_ANALYSIS_ERROR",
            request_id=msg.correlation_context.request_id,
        )
        await ctx.send(sender, error_resp)


# ============================================================================
# Startup/Shutdown
# ============================================================================

@risk_manager.on_event("startup")
async def startup(ctx: Context):
    """Agent startup."""
    logger.info(f"RiskManager started at {risk_manager.address}")
    logger.info(f"Concentration threshold (HHI): {config.concentration_threshold_hhi}")
    logger.info(f"Max single holding: {config.max_single_holding_pct}%")
    logger.info(f"Max sector: {config.max_sector_pct}%")


@risk_manager.on_event("shutdown")
async def shutdown(ctx: Context):
    """Agent shutdown."""
    logger.info("RiskManager shutting down")


# Include protocol
risk_manager.include(risk_manager_protocol)


if __name__ == "__main__":
    risk_manager.run()