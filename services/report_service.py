"""Report generation service for consolidating analysis results."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

from schemas.portfolio import PortfolioAnalysisResponse
from schemas.screening import RankedShortlistResponse
from schemas.research import AgenticThesisResponse
from schemas.common import CorrelationContext
from config.logging_config import get_logger

logger = get_logger(__name__)


class ReportService:
    """Service for generating consolidated investment research reports."""

    def generate_portfolio_report(
        self,
        analysis: PortfolioAnalysisResponse,
        include_risk: bool = True,
    ) -> str:
        """Generate human-readable portfolio analysis report."""
        p = analysis.portfolio
        lines = [
            "=" * 60,
            "FINANCEPILOT AI - PORTFOLIO ANALYSIS REPORT",
            "=" * 60,
            f"Generated: {p.data_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Data Source: {p.data_source}",
            "",
            "PORTFOLIO SUMMARY",
            "-" * 40,
            f"Total Invested:     ₹{p.total_invested:,.2f}",
        ]

        if p.total_market_value is not None:
            lines.extend([
                f"Current Value:      ₹{p.total_market_value:,.2f}",
                f"Unrealized P&L:     ₹{p.total_unrealized_pnl:,.2f} ({p.total_unrealized_pnl_pct:+.2f}%)",
            ])
        else:
            lines.append("Current Value:      N/A (insufficient price data)")

        lines.extend([
            "",
            f"Holdings with Prices: {p.holdings_with_prices}/{len(p.holdings)}",
            "",
            "HOLDINGS DETAIL",
            "-" * 40,
        ])

        for h in p.holdings:
            lines.append(f"\n{h.ticker}:")
            lines.append(f"  Shares:           {h.shares:,.0f}")
            lines.append(f"  Avg Buy Price:    ₹{h.avg_purchase_price:,.2f}")
            lines.append(f"  Invested:         ₹{h.investment_value():,.2f}")

            if h.price_available and h.current_price:
                lines.append(f"  Current Price:    ₹{h.current_price:,.2f}")
                lines.append(f"  Market Value:     ₹{h.market_value:,.2f}")
                lines.append(f"  Unrealized P&L:   ₹{h.unrealized_pnl:,.2f} ({h.unrealized_pnl_pct:+.2f}%)")
                lines.append(f"  Weight:           {h.weight_pct:.2f}%")
                lines.append(f"  Price as of:      {h.price_timestamp.strftime('%Y-%m-%d %H:%M') if h.price_timestamp else 'N/A'}")
            else:
                lines.append(f"  Current Price:    N/A (no data)")

        # Concentration analysis
        conc = analysis.concentration_analysis
        if conc:
            lines.extend([
                "",
                "CONCENTRATION ANALYSIS",
                "-" * 40,
                f"Total Holdings:          {conc.get('total_holdings', 0)}",
                f"Top 5 Concentration:     {conc.get('top_5_concentration_pct', 0):.2f}%",
                f"Top 10 Concentration:    {conc.get('top_10_concentration_pct', 0):.2f}%",
                f"HHI Index:               {conc.get('hhi', 0):.4f}",
                f"Effective Holdings:      {conc.get('effective_holdings', 0):.1f}",
                f"Largest Holding:         {conc.get('largest_holding', {}).get('ticker', 'N/A')} ({conc.get('largest_holding', {}).get('weight_pct', 0):.2f}%)",
                f"Concentration Level:     {conc.get('concentration_level', 'N/A')}",
            ])

        # Risk metrics
        if include_risk and analysis.risk_metrics:
            rm = analysis.risk_metrics
            lines.extend([
                "",
                "RISK METRICS",
                "-" * 40,
            ])
            for key, value in rm.items():
                if key != "note":
                    lines.append(f"  {key}: {value}")
            if "note" in rm:
                lines.append(f"  Note: {rm['note']}")

        # Warnings
        if analysis.warnings:
            lines.extend([
                "",
                "WARNINGS",
                "-" * 40,
            ])
            for w in analysis.warnings:
                lines.append(f"  ⚠ {w}")

        lines.extend([
            "",
            "DISCLAIMER",
            "-" * 40,
            "This analysis is for informational purposes only and does not constitute",
            "investment advice. Past performance does not guarantee future results.",
            "All investments carry risk. Please consult a qualified financial advisor.",
            "=" * 60,
        ])

        return "\n".join(lines)

    def generate_screening_report(
        self,
        result: RankedShortlistResponse,
    ) -> str:
        """Generate screening results report."""
        lines = [
            "=" * 60,
            "FINANCEPILOT AI - QUANTITATIVE SCREENING RESULTS",
            "=" * 60,
            f"Screened: {result.screening_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Universe Size: {result.total_screened}",
            f"Results Returned: {result.total_returned}",
            "",
            "FILTERS APPLIED",
            "-" * 40,
        ]

        filters = result.filters_applied.model_dump(exclude_none=True)
        for key, value in filters.items():
            if value not in (None, [], {}):
                lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            f"METHODOLOGY: {result.methodology}",
            "",
            "TOP RESULTS",
            "-" * 40,
        ])

        for i, stock in enumerate(result.stocks, 1):
            lines.append(f"\n{i}. {stock.ticker} - Score: {stock.score}")
            if stock.name:
                lines.append(f"   Name: {stock.name}")
            if stock.sector:
                lines.append(f"   Sector: {stock.sector}")
            if stock.current_price:
                lines.append(f"   Price: ₹{stock.current_price:,.2f}")
            if stock.pe_ratio:
                lines.append(f"   P/E: {stock.pe_ratio:.2f}")
            if stock.market_cap:
                lines.append(f"   Market Cap: ₹{stock.market_cap:,.0f}")
            if stock.distance_from_52w_high_pct is not None:
                lines.append(f"   From 52W High: {stock.distance_from_52w_high_pct:.2f}%")
            if stock.price_above_sma_50 is not None:
                lines.append(f"   > SMA50: {'Yes' if stock.price_above_sma_50 else 'No'}")
            if stock.price_above_sma_200 is not None:
                lines.append(f"   > SMA200: {'Yes' if stock.price_above_sma_200 else 'No'}")
            if stock.volatility_30d:
                lines.append(f"   30D Vol: {stock.volatility_30d:.2%}")

        if result.warnings:
            lines.extend([
                "",
                "WARNINGS",
                "-" * 40,
            ])
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")

        lines.extend([
            "",
            "DISCLAIMER",
            "-" * 40,
            "Screening based on historical/quantitative data only.",
            "Not a recommendation to buy or sell. Past performance ≠ future results.",
            "=" * 60,
        ])

        return "\n".join(lines)

    def generate_research_report(
        self,
        thesis: AgenticThesisResponse,
    ) -> str:
        """Generate deep research report."""
        lines = [
            "=" * 70,
            f"FINANCEPILOT AI - DEEP RESEARCH REPORT",
            "=" * 70,
            f"Company: {thesis.company_name} ({thesis.ticker})",
            f"Generated: {thesis.research_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Model: {thesis.model_used}",
            f"Data Sources: {', '.join(thesis.data_sources)}",
            "",
        ]

        sections = [
            ("COMPANY OVERVIEW", thesis.company_overview),
            ("BULL THESIS", thesis.bull_thesis),
            ("BEAR THESIS", thesis.bear_thesis),
            ("FINANCIAL STRENGTHS", thesis.financial_strengths),
            ("RISKS & UNCERTAINTIES", thesis.risks_and_uncertainties),
        ]

        if thesis.valuation_observations:
            sections.append(("VALUATION OBSERVATIONS", thesis.valuation_observations))

        for title, section in sections:
            lines.extend([
                f"{title}",
                "-" * 50,
                f"Confidence: {section.confidence:.0%}",
                "",
                section.content,
                "",
            ])

            if section.key_metrics:
                lines.append("Key Metrics:")
                for k, v in section.key_metrics.items():
                    lines.append(f"  {k}: {v}")
                lines.append("")

            if section.evidence:
                lines.append("Evidence Sources:")
                for e in section.evidence:
                    ts = e.timestamp.strftime('%Y-%m-%d') if e.timestamp else "N/A"
                    lines.append(f"  - [{e.type}] {e.description} ({ts})")
                lines.append("")

        # Suitability
        lines.extend([
            "INVESTMENT HORIZON SUITABILITY",
            "-" * 50,
        ])
        for horizon, info in thesis.investment_horizon_suitability.items():
            lines.append(f"  {horizon.capitalize()}: {'✓' if info.get('suitable') else '✗'} - {info.get('reasoning', '')}")

        lines.extend([
            "",
            "RISK PROFILE SUITABILITY",
            "-" * 50,
        ])
        for profile, info in thesis.risk_profile_suitability.items():
            lines.append(f"  {profile.capitalize()}: {'✓' if info.get('suitable') else '✗'} - {info.get('reasoning', '')}")

        lines.extend([
            "",
            thesis.disclaimer,
            "=" * 70,
        ])

        return "\n".join(lines)

    def generate_consolidated_report(
        self,
        portfolio_analysis: Optional[PortfolioAnalysisResponse] = None,
        screening_results: Optional[RankedShortlistResponse] = None,
        research_reports: Optional[List[AgenticThesisResponse]] = None,
        correlation_context: Optional[CorrelationContext] = None,
    ) -> str:
        """Generate a consolidated report from all available analyses."""
        lines = [
            "=" * 70,
            "FINANCEPILOT AI - CONSOLIDATED INVESTMENT RESEARCH REPORT",
            "=" * 70,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Request ID: {correlation_context.request_id if correlation_context else 'N/A'}",
            "",
        ]

        if portfolio_analysis:
            lines.append(self.generate_portfolio_report(portfolio_analysis, include_risk=True))
            lines.append("\n\n")

        if screening_results:
            lines.append(self.generate_screening_report(screening_results))
            lines.append("\n\n")

        if research_reports:
            for thesis in research_reports:
                lines.append(self.generate_research_report(thesis))
                lines.append("\n\n")

        lines.extend([
            "END OF REPORT",
            "=" * 70,
        ])

        return "\n".join(lines)


def get_report_service() -> ReportService:
    """Get report service instance."""
    return ReportService()