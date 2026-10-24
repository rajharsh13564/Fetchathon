# FinancePilot AI Troubleshooting Guide

## Table of Contents
1. [Installation Issues](#installation-issues)
2. [Configuration Issues](#configuration-issues)
3. [Runtime Errors](#runtime-errors)
4. [Agent Communication Issues](#agent-communication-issues)
5. [Market Data Issues](#market-data-issues)
6. [Gemini API Issues](#gemini-api-issues)
7. [Frontend Issues](#frontend-issues)
8. [Testing Issues](#testing-issues)
9. [Deployment Issues](#deployment-issues)
10. [Performance Issues](#performance-issues)

---

## Installation Issues

### ModuleNotFoundError: No module named 'uagents'

**Cause:** Dependencies not installed or wrong virtual environment.

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify
python -c "import uagents; print('uagents OK')"
```

### Error: externally-managed-environment

**Cause:** System Python is managed by OS package manager (Kali, Ubuntu 23.04+).

**Solution:** Always use virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend: npm install fails

**Cause:** Node version mismatch or network issues.

**Solution:**
```bash
# Check Node version (need 18+)
node --version

# Clear cache and retry
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install

# Or use different registry
npm install --registry=https://registry.npmmirror.com
```

---

## Configuration Issues

### GEMINI_API_KEY not configured

**Symptoms:**
- Chat returns "Gemini API key not configured"
- Research endpoint returns 503
- Health check shows `gemini_configured: false`

**Solution:**
```bash
# 1. Check .env exists
ls -la .env

# 2. Verify content
cat .env | grep GEMINI_API_KEY

# 3. Should show: GEMINI_API_KEY=your_actual_key
# NOT: GEMINI_API_KEY=your_gemini_api_key_here

# 4. Restart backend after changes
```

### Port Already in Use

**Symptoms:**
- `OSError: [Errno 98] Address already in use`
- Backend fails to start on port 8000

**Solution:**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9

# Or change port in .env
API_PORT=8001

# For agents, check ports 8001-8004
lsof -ti:8001,8002,8003,8004 | xargs kill -9
```

### CORS Errors in Frontend

**Symptoms:**
- Browser console shows CORS error
- Frontend can't connect to backend

**Solution:**
```bash
# Check .env has correct frontend URL
FRONTEND_URL=http://localhost:5173

# For production, update to actual domain
FRONTEND_URL=https://yourdomain.com

# Restart backend
```

---

## Runtime Errors

### Pydantic ValidationError on Startup

**Cause:** Schema mismatch or invalid default values.

**Solution:**
```bash
# Run tests to identify issue
pytest tests/test_schemas.py -v

# Check for min_items or other unsupported constraints
# Replace with validators (see schemas/common.py)
```

### uAgents ImportError: cannot import name 'Protocol'

**Cause:** Version mismatch or incorrect import.

**Solution:**
```bash
# Verify uagents version
pip show uagents

# Should be 0.26.x
# Import correctly:
from uagents import Agent, Context, Protocol, Model
```

### Agent Fails to Start: Address Already in Use

**Cause:** Multiple agents trying to use same port.

**Solution:**
```bash
# Each agent uses different port:
# Orchestrator: 8001
# QuantScreener: 8002
# RiskManager: 8003
# DeepResearcher: 8004

# Check .env for port overrides
# Kill existing processes
lsof -ti:8001,8002,8003,8004 | xargs kill -9
```

### Asyncio Event Loop Errors

**Cause:** Running async code incorrectly.

**Solution:**
```python
# Correct pattern:
import asyncio

async def main():
    # async code here

if __name__ == "__main__":
    asyncio.run(main())

# NOT: loop = asyncio.get_event_loop() in Python 3.10+
```

---

## Agent Communication Issues

### Messages Not Delivered Between Agents

**Symptoms:**
- Orchestrator sends request but no response
- Timeout errors in logs

**Diagnosis:**
```bash
# 1. Check all agents are running
ps aux | grep python

# 2. Verify agent addresses in orchestrator .env
QUANT_SCREENER_ADDRESS=agent1q...
RISK_MANAGER_ADDRESS=agent1q...
DEEP_RESEARCHER_ADDRESS=agent1q...

# 3. Check agent logs for startup messages
# Should see: "Agent started at agent1q..."

# 4. Verify protocols match
# All agents must use same protocol version
```

### Agent Address Shows as Empty String

**Cause:** Agent address not set in environment.

**Solution:**
```bash
# For local development, agents auto-generate addresses
# Check logs on startup for actual address

# For Agentverse deployment:
# 1. Deploy agent
# 2. Copy address from Agentverse dashboard
# 3. Add to downstream agent's secrets
# 4. Redeploy downstream agent
```

### Message Schema Mismatch

**Symptoms:**
- `TypeError: issubclass() arg 1 must be a class`
- Deserialization errors

**Solution:**
```bash
# Run compatibility tests
pytest tests/test_agent_communication.py -v

# Ensure all agents use SAME schema definitions
# Schemas are in schemas/ package - import from there
# Don't redefine schemas in each agent
```

### Agent Communication Timeout

**Symptoms:**
- `asyncio.TimeoutError` after 30s
- Requests hang

**Solution:**
```python
# Increase timeout in orchestrator
# In agent.py:
response = await ctx.send(agent_address, message, timeout=60)

# Or check if downstream agent is actually processing
# Add logging to downstream agent handlers
```

---

## Market Data Issues

### yfinance Returns No Data

**Symptoms:**
- Holdings show "No price data available"
- Screening returns empty results
- Warnings about missing prices

**Causes & Solutions:**

1. **Invalid Ticker Format**
   ```python
   # Correct: RELIANCE.NS, TCS.NS
   # Incorrect: RELIANCE, reliance, RELIANCE.BSE
   ```

2. **Delisted or Suspended Stock**
   ```bash
   # Check manually
   python -c "import yfinance as yf; print(yf.Ticker('RELIANCE.NS').info)"
   ```

3. **Rate Limited by Yahoo Finance**
   ```bash
   # Increase cache TTL
   MARKET_DATA_CACHE_TTL=300  # 5 minutes
   
   # Reduce concurrent requests in screening service
   # Edit services/screening_service.py: max_concurrent_fetches
   ```

4. **Network Issues**
   ```bash
   # Test connectivity
   curl -I https://query1.finance.yahoo.com
   ```

### Stale Price Data

**Symptoms:**
- Prices don't update after market hours
- Old timestamps

**Solution:**
```bash
# Reduce cache TTL for more frequent updates
MARKET_DATA_CACHE_TTL=30  # 30 seconds

# Clear cache manually
python -c "from services.market_data import get_market_data_service; get_market_data_service().clear_cache()"
```

### Screening Returns No Results

**Symptoms:**
- `total_returned: 0`
- Warning: "No stocks matched the screening criteria"

**Diagnosis:**
```bash
# 1. Check filters are too restrictive
# Remove filters one by one to identify culprit

# 2. Verify universe has data
python -c "
from services.screening_service import get_screening_service
s = get_screening_service()
print('Universe size:', len(s.universe))
"

# 3. Check market data for sample tickers
python -c "
import asyncio
from services.market_data import get_market_data_service
async def test():
    m = get_market_data_service()
    print(await m.get_quote('RELIANCE.NS'))
asyncio.run(test())
"
```

---

## Gemini API Issues

### Gemini API Key Invalid

**Symptoms:**
- `GeminiAPIError: Authentication failed`
- 401 errors in logs

**Solution:**
```bash
# 1. Verify key at https://makersuite.google.com/app/apikey
# 2. Regenerate if needed
# 3. Update .env and restart
```

### Rate Limit Exceeded

**Symptoms:**
- `RateLimitError: Gemini rate limit exceeded`
- 429 errors

**Solution:**
```bash
# 1. Wait for quota reset (usually per minute/day)
# 2. Reduce request frequency
# 3. Implement caching for repeated queries
# 4. Check Google Cloud quota page
```

### Quota Exhausted

**Symptoms:**
- `GeminiAPIError: Quota exceeded`
- Requests fail consistently

**Solution:**
```bash
# 1. Check Google Cloud Console > APIs > Generative AI > Quotas
# 2. Request quota increase
# 3. Optimize prompts to use fewer tokens
# 5. Implement request queuing
```

### Model Not Found

**Symptoms:**
- `GeminiAPIError: Model not found`

**Solution:**
```bash
# Check available models
# Update GEMINI_MODEL in .env
# Current supported: gemini-1.5-flash, gemini-1.5-pro
GEMINI_MODEL=gemini-1.5-flash
```

### Response Parsing Fails

**Symptoms:**
- `GeminiAPIError: Invalid JSON response`
- Research returns malformed data

**Solution:**
```bash
# 1. Check prompt requests valid JSON
# 2. Add response_schema to generation config
# 3. Lower temperature for more consistent output
# 4. Check logs for raw response
```

---

## Frontend Issues

### Frontend Shows Blank Page

**Symptoms:**
- White screen, no errors in console

**Solution:**
```bash
# 1. Check build output
cd frontend && npm run build

# 2. Check for JS errors in browser console
# 3. Verify Vite config proxy
# 4. Check index.html has correct root div
```

### "Failed to fetch" in Browser Console

**Symptoms:**
- Network errors for API calls
- Chat doesn't work

**Solution:**
```bash
# 1. Verify backend is running
curl http://localhost:8000/health

# 2. Check Vite proxy config (vite.config.js)
# Should proxy /api to localhost:8000

# 3. Check browser network tab for actual request URL
```

### React Hydration Errors

**Symptoms:**
- Console warnings about hydration mismatch

**Solution:**
```bash
# Usually caused by date/time formatting differences
# Use useEffect for client-only rendering
# Or ensure consistent formatting
```

### Styles Not Applied

**Symptoms:**
- UI looks unstyled
- Tailwind/CSS not loading

**Solution:**
```bash
# Check styles.css is imported in main.jsx
import './styles.css'

# Rebuild frontend
cd frontend && npm run build
```

---

## Testing Issues

### Tests Fail with Import Errors

**Cause:** PYTHONPATH not set correctly.

**Solution:**
```bash
# Run from project root
cd FinancePilot-AI-v2
pytest tests/

# Or set PYTHONPATH
PYTHONPATH=. pytest tests/
```

### Async Tests Hang

**Cause:** Missing pytest-asyncio or incorrect async setup.

**Solution:**
```bash
# Ensure pytest-asyncio installed
pip install pytest-asyncio

# Check pytest.ini has asyncio_mode = auto
# Or use @pytest.mark.asyncio decorator
```

### Mock Not Working

**Cause:** Incorrect patch target.

**Solution:**
```python
# Patch where it's USED, not where it's DEFINED
# services/portfolio_service.py uses:
from services.market_data import get_market_data_service

# So patch:
@patch('services.portfolio_service.get_market_data_service')
def test_something(mock_get_service):
    ...
```

### Tests Pass Locally But Fail in CI

**Cause:** Environment differences.

**Solution:**
```bash
# 1. Check Python version matches
# 2. Pin all dependencies in requirements.txt
# 3. Use same OS (Linux) for CI
# 4. Cache pip dependencies
# 5. Set deterministic seeds for random operations
```

---

## Deployment Issues

### Agentverse Deployment Fails

**Symptoms:**
- Agent won't start on Agentverse
- Import errors in logs

**Solution:**
```bash
# 1. Use self-contained agent.py (in deployment/agentverse/)
# 2. Check requirements.txt only has supported packages
# 3. No relative imports - use absolute
# 4. All schemas must be in same file or inline

# Agentverse supported packages (check current list):
# uagents, pydantic, yfinance, google-generativeai, httpx, python-dotenv
```

### Agentverse Secrets Not Working

**Symptoms:**
- Agent starts but config values are empty
- `GEMINI_API_KEY` not found

**Solution:**
```bash
# 1. Secrets names must match exactly (case-sensitive)
# 2. No quotes around values
# 3. Restart agent after adding secrets
# 4. Check Agentverse logs for "Configuration loaded"
```

### Docker Build Fails

**Symptoms:**
- `pip install` fails in Docker
- Missing system dependencies

**Solution:**
```dockerfile
# Add build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Or use manylinux wheels (default for most packages)
```

### Docker Container Exits Immediately

**Cause:** Main process exits or crashes.

**Solution:**
```bash
# Check logs
docker logs <container_id>

# Ensure CMD runs foreground process
CMD ["python", "-m", "backend.main"]

# Not: CMD python -m backend.main &
```

---

## Performance Issues

### Slow Portfolio Analysis

**Symptoms:**
- Analysis takes >10 seconds
- Timeout errors

**Diagnosis:**
```bash
# 1. Check market data cache hit rate
# 2. Reduce concurrent yfinance calls
# 3. Increase cache TTL
MARKET_DATA_CACHE_TTL=120

# 4. Profile with:
python -m cProfile -o profile.stats backend/main.py
```

### Slow Screening

**Symptoms:**
- Screening takes >30 seconds
- Times out

**Solution:**
```bash
# 1. Reduce universe size for testing
# 2. Increase concurrency limit carefully
# 3. Cache screening results
# 4. Pre-compute common screens

# In screening_service.py:
# max_concurrent_fetches = 10  # Adjust based on rate limits
```

### High Memory Usage

**Symptoms:**
- Memory grows over time
- OOM kills

**Solution:**
```bash
# 1. Clear caches periodically
# 2. Limit conversation history size
# 3. Use generators for large datasets
# 4. Profile with memory_profiler

# In market_data.py:
# Add cache size limit
MAX_CACHE_SIZE = 1000
```

### Slow Frontend

**Symptoms:**
- UI laggy
- Large re-renders

**Solution:**
```bash
# 1. Use React.memo for components
# 2. Virtualize long lists (screening results)
# 3. Debounce input handlers
# 4. Check for unnecessary state updates
```

---

## Debugging Tips

### Enable Debug Logging

```bash
# Set log level
export PYTHON_LOG_LEVEL=DEBUG

# Or in code:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Trace Agent Communication

```python
# Add to agent handlers
@agent.on_message(model=MyModel)
async def handler(ctx: Context, sender: str, msg: MyModel):
    ctx.logger.info(f"Received from {sender}: {msg}")
    # Process...
    ctx.logger.info(f"Sending response to {sender}")
```

### Inspect Market Data

```python
# Quick market data check
python -c "
import asyncio
from services.market_data import get_market_data_service

async def check():
    m = get_market_data_service()
    quote = await m.get_quote('RELIANCE.NS')
    print(quote)

asyncio.run(check())
"
```

### Profile API Endpoints

```bash
# Install profiling tools
pip install py-spy

# Profile running backend
py-spy record -o profile.svg --pid <backend_pid>

# Or use FastAPI built-in
# Add to main.py:
# from fastapi import FastAPI
# app = FastAPI()
# @app.middleware("http")
# async def add_process_time_header(request, call_next):
#     import time
#     start = time.time()
#     response = await call_next(request)
#     response.headers["X-Process-Time"] = str(time.time() - start)
#     return response
```

---

## Getting Help

1. **Check Logs First** - Most issues leave traces
2. **Run Tests** - `pytest tests/ -v` validates core functionality
3. **Search Issues** - Check GitHub issues for similar problems
4. **Minimal Reproduction** - Create smallest case that fails
5. **Check Versions** - Ensure all dependencies match requirements.txt

### Useful Commands

```bash
# Full system check
make test && make lint && make typecheck

# Clean restart
make clean
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
./start.sh

# Debug mode
PYTHON_LOG_LEVEL=DEBUG python -m backend.main

# Check all imports work
python -c "
from agents.orchestrator.agent import orchestrator
from agents.quant_screener.agent import quant_screener
from agents.risk_manager.agent import risk_manager
from agents.deep_researcher.agent import deep_researcher
print('All agents import OK')
"
```

---

## Known Limitations

1. **yfinance Reliability** - Free data source, occasional downtime
2. **Gemini Quota** - Free tier has strict limits
3. **Agentverse Constraints** - Limited package support, no background tasks
4. **Single-threaded Agents** - uAgents are single-threaded per agent
5. **No Persistent Storage** - Conversations lost on restart (local)
6. **Indian Market Only** - Optimized for NSE/BSE tickers
7. **No Real-time Data** - yfinance has 15-min delay for some data