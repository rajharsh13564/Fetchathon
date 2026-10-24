"""Test FastAPI endpoints."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from schemas.common import InvestmentHorizon, RiskProfile


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self):
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            assert "gemini_configured" in data

    def test_readiness_check(self):
        with TestClient(app) as client:
            response = client.get("/ready")
            assert response.status_code == 200
            data = response.json()
            assert "ready" in data
            assert "checks" in data


class TestChatEndpoint:
    """Test chat endpoint."""

    def test_chat_endpoint_basic(self):
        with TestClient(app) as client:
            response = client.post("/api/chat", json={
                "message": "Hello",
            })
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "conversation_id" in data
            assert data["message_type"] in ["text", "clarification", "error"]

    def test_chat_endpoint_with_conversation_id(self):
        with TestClient(app) as client:
            # First message
            response1 = client.post("/api/chat", json={"message": "Hello"})
            conv_id = response1.json()["conversation_id"]
            
            # Second message with same conversation
            response2 = client.post("/api/chat", json={
                "message": "How are you?",
                "conversation_id": conv_id,
            })
            assert response2.status_code == 200
            assert response2.json()["conversation_id"] == conv_id

    def test_chat_endpoint_portfolio_analysis(self):
        with TestClient(app) as client:
            response = client.post("/api/chat", json={
                "message": "Analyze my portfolio: 10 RELIANCE.NS at 2450 and 5 TCS.NS at 3800",
            })
            assert response.status_code == 200
            data = response.json()
            # Should either ask for clarification or provide analysis
            assert "message" in data


class TestPortfolioEndpoint:
    """Test portfolio analysis endpoint."""

    def test_portfolio_analyze_valid(self):
        with TestClient(app) as client:
            response = client.post("/api/portfolio/analyze", json={
                "holdings": [
                    {"ticker": "RELIANCE.NS", "shares": 10, "avg_purchase_price": 2450},
                    {"ticker": "TCS.NS", "shares": 5, "avg_purchase_price": 3800},
                ],
                "investment_horizon": "medium",
                "risk_profile": "moderate",
            })
            assert response.status_code == 200
            data = response.json()
            assert "portfolio" in data
            assert "total_invested" in data["portfolio"]
            # Decimal serializes as string in JSON
            assert data["portfolio"]["total_invested"] in (43500.0, "43500", "43500.0")

    def test_portfolio_analyze_invalid_ticker(self):
        with TestClient(app) as client:
            response = client.post("/api/portfolio/analyze", json={
                "holdings": [
                    {"ticker": "", "shares": 10, "avg_purchase_price": 2450},
                ],
            })
            assert response.status_code == 400

    def test_portfolio_analyze_negative_shares(self):
        with TestClient(app) as client:
            response = client.post("/api/portfolio/analyze", json={
                "holdings": [
                    {"ticker": "RELIANCE.NS", "shares": -10, "avg_purchase_price": 2450},
                ],
            })
            assert response.status_code == 400


class TestScreeningEndpoint:
    """Test screening endpoint."""

    def test_screening_run_basic(self):
        with TestClient(app) as client:
            response = client.post("/api/screening/run", json={
                "filters": {},
                "max_results": 10,
            })
            assert response.status_code == 200
            data = response.json()
            assert "stocks" in data
            assert "total_screened" in data
            assert "total_returned" in data

    def test_screening_run_with_filters(self):
        with TestClient(app) as client:
            response = client.post("/api/screening/run", json={
                "filters": {
                    "max_pe_ratio": 20,
                    "min_market_cap": 100000000000,
                },
                "max_results": 5,
            })
            assert response.status_code == 200
            data = response.json()
            assert data["total_returned"] <= 5


class TestResearchEndpoint:
    """Test research endpoint."""

    def test_research_run_requires_gemini(self):
        with TestClient(app) as client:
            # This will fail if Gemini not configured, which is expected in test env
            response = client.post("/api/research/run", json={
                "ticker": "RELIANCE.NS",
                "company_name": "Reliance Industries",
            })
            # Should either succeed (if Gemini configured) or return 503
            assert response.status_code in [200, 503]


class TestConversationEndpoints:
    """Test conversation management endpoints."""

    def test_get_conversation_not_found(self):
        with TestClient(app) as client:
            response = client.get("/api/conversations/nonexistent")
            assert response.status_code == 404

    def test_delete_conversation(self):
        with TestClient(app) as client:
            # Create a conversation first
            response = client.post("/api/chat", json={"message": "Hello"})
            conv_id = response.json()["conversation_id"]
            
            # Delete it
            response = client.delete(f"/api/conversations/{conv_id}")
            assert response.status_code == 200
            
            # Verify deleted
            response = client.get(f"/api/conversations/{conv_id}")
            assert response.status_code == 404


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root(self):
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "FinancePilot AI"
            assert "docs" in data