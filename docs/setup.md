# FinancePilot AI Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Google Gemini API key (for AI features)
- Git

## Quick Start

### 1. Clone and Enter Project

```bash
cd FinancePilot-AI-v2
```

### 2. Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your values
# Required: GEMINI_API_KEY
# Optional: Other settings
```

**Required Configuration:**
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

**Get Gemini API Key:**
1. Go to https://makersuite.google.com/app/apikey
2. Create API key
3. Add to `.env`

### 5. Run Application

**Option A: All-in-one (Recommended for Development)**

Terminal 1 - Backend:
```bash
source venv/bin/activate
python -m backend.main
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

Access:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**Option B: With Agents (Full Multi-Agent Mode)**

Terminal 1 - Backend:
```bash
source venv/bin/activate
python -m backend.main
```

Terminal 2 - Frontend:
```bash
cd frontend && npm run dev
```

Terminal 3 - Orchestrator:
```bash
source venv/bin/activate
python -m agents.orchestrator.agent
```

Terminal 4 - QuantScreener:
```bash
source venv/bin/activate
python -m agents.quant_screener.agent
```

Terminal 5 - RiskManager:
```bash
source venv/bin/activate
python -m agents.risk_manager.agent
```

Terminal 6 - DeepResearcher:
```bash
source venv/bin/activate
python -m agents.deep_researcher.agent
```

### 6. Quick Start Script

```bash
# Make executable and run
chmod +x start.sh
./start.sh
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes* | - | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-1.5-flash` | Gemini model to use |
| `FINPILOT_SYSTEM_PROMPT` | No | Built-in | Orchestrator system prompt |
| `FINPILOT_RESEARCH_PROMPT` | No | Built-in | Researcher system prompt |
| `MARKET_DATA_CACHE_TTL` | No | 60 | Market data cache seconds |
| `API_HOST` | No | `0.0.0.0` | Backend host |
| `API_PORT` | No | 8000 | Backend port |
| `FRONTEND_URL` | No | `http://localhost:5173` | CORS origin |
| `ORCHESTRATOR_SEED` | No** | Random | Agent seed |
| `QUANT_SCREENER_SEED` | No** | Random | Agent seed |
| `RISK_MANAGER_SEED` | No** | Random | Agent seed |
| `DEEP_RESEARCHER_SEED` | No** | Random | Agent seed |

*Required for AI features (chat, research). Portfolio analysis and screening work without it.

**Required for Agentverse deployment. Random seeds work for local development.

### Agentverse Deployment

For production deployment to Agentverse, see `deployment/agentverse/README.md`.

## Usage Examples

### Natural Language Chat

```
"Explain what P/E ratio means"
"Compare Reliance Industries and TCS"
"Analyze my portfolio: 10 RELIANCE.NS at 2450, 5 TCS.NS at 3800"
"Find stocks with P/E under 15 and market cap over 10000 crores"
"Research TCS.NS bull and bear case"
"What are the risks in my holdings?"
```

### Portfolio Analysis

Via API:
```bash
curl -X POST http://localhost:8000/api/portfolio/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "holdings": [
      {"ticker": "RELIANCE.NS", "shares": 10, "avg_purchase_price": 2450},
      {"ticker": "TCS.NS", "shares": 5, "avg_purchase_price": 3800}
    ],
    "investment_horizon": "medium",
    "risk_profile": "moderate"
  }'
```

### Stock Screening

```bash
curl -X POST http://localhost:8000/api/screening/run \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "max_pe_ratio": 20,
      "min_market_cap": 100000000000,
      "max_distance_from_52w_high_pct": 20
    },
    "max_results": 10
  }'
```

### Deep Research

```bash
curl -X POST http://localhost:8000/api/research/run \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "RELIANCE.NS",
    "company_name": "Reliance Industries",
    "investment_horizon": "long",
    "risk_profile": "moderate"
  }'
```

## Testing

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_schemas.py -v
pytest tests/test_portfolio.py -v
pytest tests/test_screening.py -v
pytest tests/test_research.py -v
pytest tests/test_orchestrator.py -v
pytest tests/test_api.py -v
pytest tests/test_agent_communication.py -v

# With coverage
pytest --cov=. tests/
```

## Troubleshooting

### Common Issues

**1. ModuleNotFoundError: No module named 'uagents'**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**2. Gemini API Key Not Configured**
- Check `.env` file exists and has `GEMINI_API_KEY=your_key`
- Restart backend after changes

**3. Port Already in Use**
```bash
# Change port in .env
API_PORT=8001
# Or kill existing process
lsof -ti:8000 | xargs kill -9
```

**4. Frontend Can't Connect to Backend**
- Check `FRONTEND_URL` in `.env` matches frontend URL
- Check backend is running on `API_HOST:API_PORT`
- Check CORS settings in `backend/main.py`

**5. yfinance Rate Limited**
- Increase `MARKET_DATA_CACHE_TTL` (default 60s)
- Reduce concurrent requests in screening service

**6. Agent Communication Fails**
- Verify agent addresses in `.env` for orchestrator
- Check all agents are running
- Check agent ports (8001-8004) not in use

### Logs

Backend logs appear in terminal. For agents:
```bash
# Agent logs go to stdout
python -m agents.orchestrator.agent 2>&1 | tee orchestrator.log
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Backend readiness
curl http://localhost:8000/ready
```

## Development

### Code Structure
```
FinancePilot-AI-v2/
├── config/          # Settings, logging
├── schemas/         # Pydantic models (shared)
├── shared/          # Protocols, utilities
├── services/        # Business logic
├── agents/          # uAgents implementations
├── backend/         # FastAPI app
├── frontend/        # React app
├── tests/           # Test suite
├── deployment/      # Agentverse, Docker
└── docs/            # Documentation
```

### Adding New Features

1. Define schemas in `schemas/`
2. Add service logic in `services/`
3. Create/update agents in `agents/`
4. Add API endpoints in `backend/api/`
5. Update frontend in `frontend/src/`
6. Write tests in `tests/`

### Linting & Type Checking

```bash
# Lint
make lint

# Type check
make typecheck
```

## Production Considerations

- Use Redis for conversation storage
- Add authentication/authorization
- Set up monitoring (Prometheus/Grafana)
- Configure log aggregation
- Use PostgreSQL for persistent data
- Set up CI/CD pipeline
- Configure SSL/TLS
- Use secrets manager for API keys

## Support

- Check `docs/troubleshooting.md` for common issues
- Review `docs/architecture.md` for system understanding
- See `deployment/agentverse/` for Agentverse deployment