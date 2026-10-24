# FinancePilot AI

A multi-agent financial research platform for Indian equity portfolios, built with Fetch.ai uAgents.

## Features

- Natural-language financial conversations via Gemini AI
- Portfolio analysis with P&L, weights, and concentration metrics
- Quantitative stock screening with deterministic filters
- AI-assisted fundamental research (bull/bear cases)
- Risk assessment and concentration analysis
- Multi-agent communication via Fetch.ai uAgents
- Agentverse deployment ready
- FastAPI backend with React frontend

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Frontend   │────▶│   FastAPI API    │────▶│  Orchestrator   │
│  (React)    │     │   (Backend)      │     │    Agent        │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                      │
                    ┌─────────────────────────────────┼─────────────────────────────────┐
                    ▼                                 ▼                                 ▼
            ┌───────────────┐               ┌─────────────────┐               ┌─────────────────┐
            │QuantScreener  │               │  DeepResearcher │               │   RiskManager   │
            │    Agent      │               │     Agent       │               │     Agent       │
            └───────────────┘               └─────────────────┘               └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Google Gemini API key

### Installation

```bash
# Clone and enter project
cd FinancePilot-AI-v2

# Python setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
cd ..

# Configure environment
cp .env.example .env
# Edit .env with your GEMINI_API_KEY
```

### Running Locally

**Terminal 1 - Start Backend API:**
```bash
source venv/bin/activate
python -m backend.main
```

**Terminal 2 - Start Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - Start Agents (optional, for full multi-agent mode):**
```bash
source venv/bin/activate
python -m agents.orchestrator.agent
# In separate terminals:
python -m agents.quant_screener.agent
python -m agents.risk_manager.agent
python -m agents.deep_researcher.agent
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes (for AI features) |
| `GEMINI_MODEL` | Model name (default: gemini-1.5-flash) | No |
| `FINPILOT_SYSTEM_PROMPT` | Custom system prompt | No |
| `MARKET_DATA_CACHE_TTL` | Cache TTL in seconds (default: 60) | No |
| `API_HOST` | Backend host (default: 0.0.0.0) | No |
| `API_PORT` | Backend port (default: 8000) | No |

## Project Structure

```
FinancePilot-AI-v2/
├── config/                 # Configuration and settings
├── schemas/                # Pydantic message schemas (shared)
├── shared/                 # Shared utilities and protocols
├── services/               # Business logic services
├── agents/                 # uAgents implementations
│   ├── orchestrator/       # Central coordinator
│   ├── quant_screener/     # Quantitative screening
│   ├── risk_manager/       # Portfolio risk analysis
│   └── deep_researcher/    # AI-powered research
├── backend/                # FastAPI backend
├── frontend/               # React + Vite frontend
├── deployment/             # Agentverse and Docker deployment
├── tests/                  # Test suite
└── docs/                   # Documentation
```

## API Endpoints

- `GET /health` - Health check
- `POST /api/chat` - Natural language chat
- `POST /api/portfolio/analyze` - Portfolio analysis
- `POST /api/screening/run` - Run stock screening
- `POST /api/research/run` - Run deep research

## Testing

```bash
source venv/bin/activate
pytest tests/ -v
```

## Agentverse Deployment

See `deployment/agentverse/README.md` for detailed deployment instructions.

## Disclaimer

This application provides informational research and is not a substitute for qualified financial advice. Past performance does not guarantee future results. All investments carry risk.