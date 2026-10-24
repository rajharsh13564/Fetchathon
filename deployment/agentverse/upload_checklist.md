# Agentverse Deployment Checklist

Follow this checklist for each agent deployment. Complete in order.

## Pre-Deployment

- [ ] Generate 4 unique agent seeds
- [ ] Obtain Google Gemini API key
- [ ] Prepare Agentverse account
- [ ] Review agent code for hardcoded values

---

## 1. Deploy QuantScreener Agent (No Dependencies)

### Files to Upload
- [ ] `deployment/agentverse/quant_screener/agent.py`
- [ ] `deployment/agentverse/quant_screener/schemas.py`
- [ ] `deployment/agentverse/quant_screener/requirements.txt`

### Secrets to Configure
- [ ] `AGENT_SEED` (unique seed)
- [ ] `MAILBOX_KEY` (after deployment)
- [ ] `MARKET_DATA_CACHE_TTL` (optional, default: 60)

### Verification
- [ ] Agent starts without errors
- [ ] Check logs: "QuantScreener started at agent1q..."
- [ ] Note agent address: `agent1q...`
- [ ] Test: Send ScreeningRequest via Agentverse UI

---

## 2. Deploy RiskManager Agent (No Dependencies)

### Files to Upload
- [ ] `deployment/agentverse/risk_manager/agent.py`
- [ ] `deployment/agentverse/risk_manager/schemas.py`
- [ ] `deployment/agentverse/risk_manager/requirements.txt`

### Secrets to Configure
- [ ] `AGENT_SEED` (unique seed)
- [ ] `MAILBOX_KEY` (after deployment)
- [ ] Risk thresholds (optional, defaults provided)

### Verification
- [ ] Agent starts without errors
- [ ] Check logs: "RiskManager started at agent1q..."
- [ ] Note agent address: `agent1q...`
- [ ] Test: Send RiskAnalysisRequest via Agentverse UI

---

## 3. Deploy DeepResearcher Agent (Requires Gemini)

### Files to Upload
- [ ] `deployment/agentverse/deep_researcher/agent.py`
- [ ] `deployment/agentverse/deep_researcher/schemas.py`
- [ ] `deployment/agentverse/deep_researcher/requirements.txt`

### Secrets to Configure
- [ ] `AGENT_SEED` (unique seed)
- [ ] `GEMINI_API_KEY` (same as orchestrator)
- [ ] `GEMINI_MODEL` (default: gemini-1.5-flash)
- [ ] `FINPILOT_RESEARCH_PROMPT`
- [ ] `MAILBOX_KEY` (after deployment)
- [ ] Model parameters (optional)

### Verification
- [ ] Agent starts without errors
- [ ] Check logs: "DeepResearcher started at agent1q..."
- [ ] Note agent address: `agent1q...`
- [ ] Test: Send ResearchRequest via Agentverse UI
- [ ] Verify Gemini API calls work (check logs)

---

## 4. Deploy Orchestrator Agent (Requires All Downstream)

### Files to Upload
- [ ] `deployment/agentverse/orchestrator/agent.py`
- [ ] `deployment/agentverse/orchestrator/schemas.py`
- [ ] `deployment/agentverse/orchestrator/requirements.txt`

### Secrets to Configure
- [ ] `AGENT_SEED` (unique seed)
- [ ] `GEMINI_API_KEY` (same as deep researcher)
- [ ] `GEMINI_MODEL`
- [ ] `FINPILOT_SYSTEM_PROMPT`
- [ ] `FINPILOT_RESEARCH_PROMPT`
- [ ] `MAILBOX_KEY` (after deployment)
- [ ] `QUANT_SCREENER_ADDRESS` (from step 1)
- [ ] `RISK_MANAGER_ADDRESS` (from step 2)
- [ ] `DEEP_RESEARCHER_ADDRESS` (from step 3)

### Verification
- [ ] Agent starts without errors
- [ ] Check logs: "Orchestrator started at agent1q..."
- [ ] Note agent address: `agent1q...`
- [ ] Test: Send ChatRequest via Agentverse UI
- [ ] Verify downstream agent communication works

---

## Post-Deployment Integration Testing

### Test 1: Basic Chat
- [ ] Send "Hello" to Orchestrator
- [ ] Verify response received

### Test 2: Portfolio Analysis
- [ ] Send "Analyze my portfolio: 10 RELIANCE.NS at 2450"
- [ ] Verify portfolio analysis response
- [ ] Check P&L calculations are correct

### Test 3: Stock Screening
- [ ] Send "Find stocks with P/E under 15"
- [ ] Verify screening results returned
- [ ] Check QuantScreener logs for activity

### Test 4: Deep Research
- [ ] Send "Research TCS.NS bull and bear case"
- [ ] Verify research report received
- [ ] Check DeepResearcher logs for Gemini calls

### Test 5: Risk Analysis
- [ ] Send portfolio with concentrated holdings
- [ ] Verify risk metrics returned
- [ ] Check RiskManager logs

---

## Production Checklist

- [ ] All agents show "Running" status in Agentverse
- [ ] Mailbox keys configured for all agents
- [ ] Gemini API key has sufficient quota
- [ ] Monitor logs for errors (first 24 hours)
- [ ] Set up alerts for agent downtime
- [ ] Document agent addresses for team
- [ ] Backup seeds securely (password manager)

---

## Rollback Plan

If issues arise:

1. **Agent failing**: Check logs, fix code, redeploy same agent (address preserved)
2. **Communication failing**: Verify all agent addresses in Orchestrator secrets
3. **Gemini quota exceeded**: Wait for reset or upgrade plan
4. **Complete failure**: Revert to previous agent version in Agentverse

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Deployer | | | |
| Reviewer | | | |
| Product Owner | | | |