# FinancePilot AI API Reference

## Base URL

```
Local: http://localhost:8000
Production: https://your-domain.com
```

## Authentication

Currently no authentication required for local development. For production, implement API key or JWT authentication.

## Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `X-Request-ID` | Optional correlation ID |
| `X-Conversation-ID` | Optional conversation ID |

## Endpoints

---

### Health Check

#### GET /health

Check service health and configuration.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "2.0.0",
  "gemini_configured": true,
  "settings": {
    "gemini_model": "gemini-1.5-flash",
    "market_data_cache_ttl": 60,
    "api_host": "0.0.0.0",
    "api_port": 8000
  }
}
```

**Status Codes:**
- `200` - Healthy
- `503` - Unhealthy

---

#### GET /ready

Check service readiness.

**Response:**
```json
{
  "ready": true,
  "checks": {
    "config": true,
    "gemini": true
  }
}
```

---

### Chat

#### POST /api/chat

Natural language chat with FinancePilot AI.

**Request:**
```json
{
  "message": "Analyze my portfolio: 10 RELIANCE.NS at 2450",
  "conversation_id": "optional-existing-conversation-id",
  "portfolio_context": {},
  "investment_horizon": "medium",
  "risk_profile": "moderate"
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | User message (1-4000 chars) |
| `conversation_id` | string | No | Existing conversation ID |
| `portfolio_context` | object | No | Portfolio data for context |
| `investment_horizon` | string | No | short/medium/long |
| `risk_profile` | string | No | conservative/moderate/aggressive |

**Response:**
```json
{
  "message": "I'll analyze your portfolio...",
  "conversation_id": "uuid",
  "message_type": "text|portfolio_analysis|screening_result|research_report|clarification|error",
  "metadata": {},
  "correlation_context": {
    "request_id": "uuid",
    "conversation_id": "uuid"
  },
  "requires_clarification": false,
  "clarification_questions": [],
  "suggested_actions": []
}
```

**Message Types:**
- `text` - Regular conversation
- `portfolio_analysis` - Includes portfolio analysis
- `screening_result` - Includes screening results
- `research_report` - Includes research report
- `clarification` - Needs more information
- `error` - Error occurred

**Status Codes:**
- `200` - Success
- `400` - Invalid request
- `500` - Server error

---

#### GET /api/conversations/{conversation_id}

Get conversation history.

**Response:**
```json
{
  "conversation_id": "uuid",
  "messages": [
    {
      "role": "user",
      "content": "Hello",
      "timestamp": "2024-01-15T10:30:00.000Z",
      "message_type": "text",
      "metadata": {}
    }
  ],
  "created_at": "2024-01-15T10:30:00.000Z",
  "updated_at": "2024-01-15T10:35:00.000Z",
  "portfolio_context": {}
}
```

**Status Codes:**
- `200` - Success
- `404` - Conversation not found

---

#### DELETE /api/conversations/{conversation_id}

Delete conversation history.

**Response:**
```json
{
  "status": "deleted"
}
```

---

### Portfolio Analysis

#### POST /api/portfolio/analyze

Analyze portfolio with current market data.

**Request:**
```json
{
  "holdings": [
    {
      "ticker": "RELIANCE.NS",
      "shares": 10,
      "avg_purchase_price": 2450,
      "purchase_date": "2024-01-01T00:00:00Z"
    }
  ],
  "investment_horizon": "medium",
  "risk_profile": "moderate"
}
```

**Holdings Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | Yes | NSE/BSE ticker (e.g., RELIANCE.NS) |
| `shares` | number | Yes | Number of shares (>0) |
| `avg_purchase_price` | number | Yes | Average buy price (>0) |
| `purchase_date` | string | No | ISO 8601 date |

**Response:**
```json
{
  "portfolio": {
    "holdings": [
      {
        "ticker": "RELIANCE.NS",
        "shares": 10,
        "avg_purchase_price": 2450,
        "current_price": 2600,
        "price_timestamp": "2024-01-15T10:30:00Z",
        "price_source": "yfinance",
        "market_value": 26000,
        "unrealized_pnl": 1500,
        "unrealized_pnl_pct": 6.12,
        "weight_pct": 100,
        "price_available": true
      }
    ],
    "total_invested": 24500,
    "total_market_value": 26000,
    "total_unrealized_pnl": 1500,
    "total_unrealized_pnl_pct": 6.12,
    "data_timestamp": "2024-01-15T10:30:00Z",
    "data_source": "yfinance",
    "holdings_with_prices": 1,
    "holdings_without_prices": 0
  },
  "concentration_analysis": {
    "total_holdings": 1,
    "top_5_concentration_pct": 100,
    "top_10_concentration_pct": 100,
    "hhi": 1.0,
    "effective_holdings": 1.0,
    "largest_holding": {"ticker": "RELIANCE.NS", "weight_pct": 100},
    "concentration_level": "Very High (concentrated)"
  },
  "risk_metrics": {
    "holdings_with_prices": 1,
    "holdings_without_prices": 0,
    "data_completeness_pct": 100
  },
  "correlation_context": {},
  "warnings": []
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid holdings (empty, negative shares, etc.)
- `500` - Server error

---

### Stock Screening

#### POST /api/screening/run

Run quantitative stock screening.

**Request:**
```json
{
  "filters": {
    "min_market_cap": 100000000000,
    "max_market_cap": 5000000000000,
    "min_pe_ratio": 5,
    "max_pe_ratio": 25,
    "max_distance_from_52w_high_pct": 20,
    "min_price_above_sma_50": true,
    "min_price_above_sma_200": false,
    "exclude_tickers": ["RELIANCE.NS"],
    "sector": "IT"
  },
  "max_results": 20
}
```

**Filters:**
| Filter | Type | Description |
|--------|------|-------------|
| `min_market_cap` | number | Minimum market cap (INR) |
| `max_market_cap` | number | Maximum market cap (INR) |
| `min_pe_ratio` | number | Minimum P/E ratio |
| `max_pe_ratio` | number | Maximum P/E ratio |
| `max_distance_from_52w_high_pct` | number | Max % below 52W high |
| `min_price_above_sma_50` | boolean | Price above 50-day SMA |
| `min_price_above_sma_200` | boolean | Price above 200-day SMA |
| `exclude_tickers` | array | Tickers to exclude |
| `sector` | string | Sector filter |

**Response:**
```json
{
  "stocks": [
    {
      "ticker": "TCS.NS",
      "name": "Tata Consultancy Services",
      "sector": "IT",
      "market_cap": 1400000000000,
      "current_price": 3900,
      "pe_ratio": 28,
      "pb_ratio": 12,
      "dividend_yield": 0.015,
      "distance_from_52w_high_pct": 7.14,
      "distance_from_52w_low_pct": 21.88,
      "sma_50": 3850,
      "sma_200": 3600,
      "price_above_sma_50": true,
      "price_above_sma_200": true,
      "volatility_30d": 0.20,
      "volume_avg_30d": 500000,
      "score": 82.5,
      "price_timestamp": "2024-01-15T10:30:00Z",
      "data_source": "yfinance",
      "data_available": true
    }
  ],
  "filters_applied": {},
  "total_screened": 50,
  "total_returned": 1,
  "correlation_context": {},
  "screening_timestamp": "2024-01-15T10:30:00Z",
  "warnings": [],
  "methodology": "Screening based on yfinance data..."
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid filters
- `500` - Server error

---

### Deep Research

#### POST /api/research/run

Run AI-powered fundamental research.

**Request:**
```json
{
  "ticker": "RELIANCE.NS",
  "company_name": "Reliance Industries",
  "include_quant_data": {
    "current_price": 2600,
    "pe_ratio": 15.5
  },
  "investment_horizon": "medium",
  "risk_profile": "moderate"
}
```

**Response:**
```json
{
  "ticker": "RELIANCE.NS",
  "company_name": "Reliance Industries",
  "company_overview": {
    "title": "Company Overview",
    "content": "Reliance Industries is a diversified conglomerate...",
    "confidence": 0.9,
    "evidence": [
      {
        "type": "financial_data",
        "description": "Revenue: ₹8.5L cr",
        "timestamp": "2024-01-15T00:00:00Z",
        "url": null
      }
    ],
    "key_metrics": {
      "revenue": "₹8.5L cr",
      "employees": "300K+"
    }
  },
  "bull_thesis": {
    "title": "Bull Thesis",
    "content": "Strong growth in digital and retail...",
    "confidence": 0.75,
    "evidence": [],
    "key_metrics": {}
  },
  "bear_thesis": {
    "title": "Bear Thesis",
    "content": "High debt and regulatory risks...",
    "confidence": 0.7,
    "evidence": [],
    "key_metrics": {}
  },
  "financial_strengths": {
    "title": "Financial Strengths",
    "content": "Strong cash flows and market leadership...",
    "confidence": 0.85,
    "evidence": [],
    "key_metrics": {}
  },
  "risks_and_uncertainties": {
    "title": "Risks & Uncertainties",
    "content": "Regulatory changes and execution risks...",
    "confidence": 0.7,
    "evidence": [],
    "key_metrics": {}
  },
  "valuation_observations": {
    "title": "Valuation Observations",
    "content": "Trading at reasonable multiples...",
    "confidence": 0.65,
    "evidence": [],
    "key_metrics": {}
  },
  "investment_horizon_suitability": {
    "short": {"suitable": false, "reasoning": "...", "confidence": 0.5},
    "medium": {"suitable": true, "reasoning": "...", "confidence": 0.7},
    "long": {"suitable": true, "reasoning": "...", "confidence": 0.8}
  },
  "risk_profile_suitability": {
    "conservative": {"suitable": false, "reasoning": "...", "confidence": 0.6},
    "moderate": {"suitable": true, "reasoning": "...", "confidence": 0.7},
    "aggressive": {"suitable": true, "reasoning": "...", "confidence": 0.7}
  },
  "model_used": "gemini-1.5-flash",
  "data_sources": ["yfinance", "gemini_model_knowledge"],
  "research_timestamp": "2024-01-15T10:30:00Z",
  "correlation_context": {},
  "disclaimer": "This research is for informational purposes only..."
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid request
- `503` - Gemini API not configured
- `500` - Server error

---

## Error Responses

All endpoints may return errors in this format:

```json
{
  "detail": {
    "error": "Error description",
    "code": "ERROR_CODE",
    "details": {}
  }
}
```

**Common Error Codes:**
| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `CONFIGURATION_ERROR` | 503 | Required config missing (e.g., Gemini key) |
| `MARKET_DATA_ERROR` | 500 | Market data fetch failed |
| `GEMINI_API_ERROR` | 500 | Gemini API call failed |
| `AGENT_UNAVAILABLE` | 503 | Downstream agent not reachable |
| `AGENT_COMMUNICATION_ERROR` | 500 | Agent message failed |
| `INSUFFICIENT_DATA_ERROR` | 400 | Not enough data for operation |

---

## Rate Limits

No rate limits implemented in local development. For production, implement:
- 60 requests/minute for chat
- 30 requests/minute for analysis endpoints
- 10 requests/minute for research

---

## WebSocket (Future)

Real-time updates via WebSocket planned for:
- Live portfolio updates
- Screening progress
- Research generation status

---

## SDK Examples

### Python
```python
import httpx

client = httpx.Client(base_url="http://localhost:8000")

# Chat
response = client.post("/api/chat", json={"message": "Analyze my portfolio"})
print(response.json())

# Portfolio
response = client.post("/api/portfolio/analyze", json={
    "holdings": [{"ticker": "RELIANCE.NS", "shares": 10, "avg_purchase_price": 2450}]
})
print(response.json())
```

### JavaScript
```javascript
const response = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Explain P/E ratio' })
});
const data = await response.json();
console.log(data.message);
```

### cURL
```bash
# Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is P/E ratio?"}'

# Portfolio
curl -X POST http://localhost:8000/api/portfolio/analyze \
  -H "Content-Type: application/json" \
  -d '{"holdings": [{"ticker": "RELIANCE.NS", "shares": 10, "avg_purchase_price": 2450}]}'
```