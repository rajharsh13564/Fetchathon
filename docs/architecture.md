# FinancePilot AI Architecture

## System Overview

FinancePilot AI is a multi-agent financial research platform for Indian equity portfolios. It combines natural language interaction with quantitative analysis, fundamental research, and risk assessment through a coordinated agent system.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FINANCEPILOT AI SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │   Frontend   │───▶│   Backend    │───▶│ Orchestrator │───▶│Agents    │  │
│  │   (React)    │    │  (FastAPI)   │    │    Agent     │    │          │  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘    └────┬─────┘  │
│                                                  │                 │        │
│                    ┌─────────────────────────────┼─────────────────┼────┐   │
│                    ▼                             ▼                 ▼    ▼   │
│             ┌───────────────┐            ┌───────────────┐  ┌──────────┐  │
│             │QuantScreener  │            │DeepResearcher │  │RiskMgr   │  │
│             │    Agent      │            │    Agent      │  │  Agent   │  │
│             └───────────────┘            └───────────────┘  └──────────┘  │
│                    │                             │             │            │
│                    └─────────────────────────────┼─────────────┘            │
│                                                  ▼                          │
│                                         ┌───────────────┐                   │
│                                         │Market Data    │                   │
│                                         │Service        │                   │
│                                         │(yfinance)     │                   │
│                                         └───────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Frontend (React + Vite)
- **Location**: `frontend/`
- **Technology**: React 18, Vite, Axios
- **Features**:
  - Natural language chat interface
  - Portfolio input form with dynamic holdings
  - Screening results table
  - Research report viewer
  - Responsive design

### 2. Backend API (FastAPI)
- **Location**: `backend/`
- **Technology**: FastAPI, Uvicorn, Pydantic
- **Endpoints**:
  - `GET /health` - Health check
  - `POST /api/chat` - Natural language chat
  - `POST /api/portfolio/analyze` - Portfolio analysis
  - `POST /api/screening/run` - Quantitative screening
  - `POST /api/research/run` - Deep research
- **Features**:
  - Request validation
  - CORS support
  - Conversation management
  - Correlation IDs for tracing

### 3. Orchestrator Agent
- **Location**: `agents/orchestrator/`
- **Role**: Central coordinator
- **Responsibilities**:
  - Receive chat messages (natural language)
  - Classify requests (education, portfolio, screening, research, risk)
  - Extract portfolio from natural language
  - Coordinate downstream agents
  - Consolidate responses
  - Maintain conversation history
- **Protocols**: `finpilot.orchestrator.v1`, `finpilot.chat.v1`

### 4. QuantScreener Agent
- **Location**: `agents/quant_screener/`
- **Role**: Quantitative stock screening
- **Responsibilities**:
  - Receive screening requests with filters
  - Fetch market data for universe
  - Apply deterministic filters
  - Calculate composite scores
  - Return ranked results
- **Universe**: 50+ major NSE stocks
- **Filters**: Market cap, P/E, 52W high distance, SMA, volatility
- **Protocol**: `finpilot.quant_screener.v1`

### 5. DeepResearcher Agent
- **Location**: `agents/deep_researcher/`
- **Role**: AI-powered fundamental research
- **Responsibilities**:
  - Receive research requests
  - Generate structured prompts with quant data
  - Call Gemini API
  - Parse and validate responses
  - Return structured thesis
- **Output Sections**: Overview, Bull/Bear cases, Financial strengths, Risks, Valuation
- **Protocol**: `finpilot.deep_researcher.v1`

### 6. RiskManager Agent
- **Location**: `agents/risk_manager/`
- **Role**: Portfolio risk assessment
- **Responsibilities**:
  - Concentration analysis (HHI, top holdings, sector)
  - Volatility analysis (historical, VaR, max drawdown)
  - Correlation/diversification assessment
  - Overall risk scoring
  - Recommendations generation
- **Protocol**: `finpilot.risk_manager.v1`

### 7. Shared Services
- **Market Data Service**: yfinance wrapper with caching
- **Gemini Client**: Async wrapper with retries
- **Portfolio Service**: Calculations and analysis
- **Screening Service**: Quantitative filtering and scoring
- **Research Service**: Prompt engineering and response parsing
- **Report Service**: Human-readable report generation

## Data Flow

### Chat Flow
```
User Message
    │
    ▼
Frontend ──POST /api/chat──▶ Backend
    │                          │
    │                          ▼
    │                   Orchestrator Agent
    │                          │
    │              ┌───────────┼───────────┐
    │              ▼           ▼           ▼
    │         Classify    Extract      Generate
    │         Request     Portfolio    Response
    │              │           │           │
    │              ▼           ▼           │
    │         Portfolio    (if needed)   │
    │         Analysis                 │
    │              │           │           │
    └──────────────┴───────────┴──────────┘
                         │
                         ▼
                   Response to User
```

### Portfolio Analysis Flow
```
Portfolio Input
    │
    ▼
Orchestrator ──PortfolioInput──▶ Portfolio Service
    │                              │
    │                              ▼
    │                    Market Data Service
    │                              │
    │                    ◀── Quotes ───
    │                              │
    │              ◀── PortfolioAnalysisResponse
    │
    ▼
Consolidated Report
```

### Screening Flow
```
Screening Request
    │
    ▼
Orchestrator ──ScreeningRequest──▶ QuantScreener Agent
    │                              │
    │              ┌───────────────┼───────────────┐
    │              ▼               ▼               ▼
    │         Fetch Data      Apply Filters   Calculate
    │         (Parallel)      (Deterministic)  Scores
    │              │               │               │
    │              └───────────────┼───────────────┘
    │                              ▼
    │                    ◀── RankedShortlistResponse
    │
    ▼
Results to User
```

### Research Flow
```
Research Request
    │
    ▼
Orchestrator ──ResearchRequest──▶ DeepResearcher Agent
    │                              │
    │                              ▼
    │                    Build Prompt with Quant Data
    │                              │
    │                              ▼
    │                    Gemini API Call
    │                              │
    │              ◀── AgenticThesisResponse
    │
    ▼
Structured Report
```

## Message Protocols

All inter-agent communication uses uAgents protocols with Pydantic models:

| Protocol | Version | Request | Response |
|----------|---------|---------|----------|
| `finpilot.orchestrator.v1` | 1.0.0 | Various | Various |
| `finpilot.chat.v1` | 1.0.0 | ChatRequest | ChatResponse |
| `finpilot.quant_screener.v1` | 1.0.0 | ScreeningRequest | RankedShortlistResponse |
| `finpilot.risk_manager.v1` | 1.0.0 | RiskAnalysisRequest | RiskAnalysisResponse |
| `finpilot.deep_researcher.v1` | 1.0.0 | ResearchRequest | AgenticThesisResponse |

## Configuration

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required for AI features |
| `GEMINI_MODEL` | Model name | `gemini-1.5-flash` |
| `FINPILOT_SYSTEM_PROMPT` | Orchestrator system prompt | Built-in default |
| `FINPILOT_RESEARCH_PROMPT` | Researcher system prompt | Built-in default |
| `MARKET_DATA_CACHE_TTL` | Cache TTL seconds | 60 |
| `API_HOST` | Backend host | `0.0.0.0` |
| `API_PORT` | Backend port | 8000 |
| `FRONTEND_URL` | Frontend for CORS | `http://localhost:5173` |

### Agent Seeds
Each agent requires a unique seed for identity:
- `ORCHESTRATOR_SEED`
- `QUANT_SCREENER_SEED`
- `RISK_MANAGER_SEED`
- `DEEP_RESEARCHER_SEED`

## Deployment

### Local Development
```bash
# Terminal 1: Backend
make run-backend

# Terminal 2: Frontend
make run-frontend

# Terminal 3-6: Agents (optional)
make run-orchestrator
make run-quant-screener
make run-risk-manager
make run-deep-researcher
```

### Agentverse Deployment
See `deployment/agentverse/README.md` for detailed instructions.

### Docker
```bash
docker-compose up -d
```

## Security

- No hardcoded secrets
- Environment-based configuration
- Input validation on all endpoints
- CORS restricted to frontend origin
- No API keys in frontend code
- Agent seeds stored in Agentverse Secrets

## Scalability Considerations

- Market data service uses caching (TTL configurable)
- Screening runs in parallel with semaphore limiting
- Gemini client has retry logic with exponential backoff
- Agents are stateless (can run multiple instances)
- Backend uses in-memory conversation storage (Redis recommended for production)

## Monitoring

- Health endpoints: `/health`, `/ready`
- Structured logging with correlation IDs
- Agent startup/shutdown events
- Error tracking with context