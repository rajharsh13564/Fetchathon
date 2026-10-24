# Agentverse Secrets Template

Copy this file and fill in your actual values. Set these in the Agentverse dashboard under **Agent Settings > Secrets**.

## Orchestrator Agent Secrets

```
AGENT_SEED=your_unique_orchestrator_seed_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
FINPILOT_SYSTEM_PROMPT=You are FinancePilot AI, a helpful financial research assistant for Indian equity markets. Provide accurate, balanced, and educational responses. Never guarantee returns or give personalized investment advice. Always distinguish between facts, calculations, and opinions. Cite sources when possible.
FINPILOT_RESEARCH_PROMPT=You are a senior equity research analyst specializing in Indian markets. Provide thorough, balanced analysis with clear bull and bear cases. Cite specific financial metrics and business fundamentals. Distinguish verified data from estimates and opinions.
MAILBOX_KEY=your_orchestrator_mailbox_key_from_agentverse
QUANT_SCREENER_ADDRESS=agent1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RISK_MANAGER_ADDRESS=agent1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEP_RESEARCHER_ADDRESS=agent1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MARKET_DATA_CACHE_TTL=60
```

## QuantScreener Agent Secrets

```
AGENT_SEED=your_unique_quant_screener_seed_here
MAILBOX_KEY=your_quant_screener_mailbox_key_from_agentverse
MARKET_DATA_CACHE_TTL=60
# Optional: Custom universe (comma-separated)
# QUANT_SCREENER_UNIVERSE=RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,HINDUNILVR.NS
```

## RiskManager Agent Secrets

```
AGENT_SEED=your_unique_risk_manager_seed_here
MAILBOX_KEY=your_risk_manager_mailbox_key_from_agentverse
RISK_CONCENTRATION_THRESHOLD_HHI=0.25
RISK_MAX_SINGLE_HOLDING_PCT=20.0
RISK_MAX_SECTOR_PCT=30.0
RISK_LOOKBACK_DAYS=252
```

## DeepResearcher Agent Secrets

```
AGENT_SEED=your_unique_deep_researcher_seed_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
FINPILOT_RESEARCH_PROMPT=You are a senior equity research analyst specializing in Indian markets. Provide thorough, balanced analysis with clear bull and bear cases. Cite specific financial metrics and business fundamentals. Distinguish verified data from estimates and opinions.
MAILBOX_KEY=your_deep_researcher_mailbox_key_from_agentverse
DEEP_RESEARCHER_TEMPERATURE=0.3
DEEP_RESEARCHER_MAX_TOKENS=8192
DEEP_RESEARCHER_TIMEOUT=60
```

## Generating Seeds

Run this command to generate a secure seed:

```bash
python -c "from uagents.crypto import Identity; print(Identity.generate().seed)"
```

Run 4 times to get 4 unique seeds.

## Mailbox Keys

1. Deploy agent to Agentverse
2. Go to Agent Settings > Mailbox
3. Enable mailbox and copy the key
4. Add to secrets

## Important Notes

- **Never commit this file with real values**
- Each agent needs a **unique seed**
- Use the **same Gemini API key** for Orchestrator and DeepResearcher
- Agent addresses are only known **after deployment**
- Update Orchestrator secrets with downstream addresses **after** deploying them