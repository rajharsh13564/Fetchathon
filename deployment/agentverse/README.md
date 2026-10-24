# Agentverse Deployment Guide

This directory contains deployment configurations for hosting FinancePilot AI agents on Agentverse.

## Overview

Each agent must be deployed separately to Agentverse. The deployment process:

1. Create agent entry point files
2. Configure secrets in Agentverse dashboard
3. Deploy each agent
4. Wire up agent addresses
5. Test communication

## Directory Structure

```
deployment/agentverse/
├── README.md                    # This file
├── secrets.example.md           # Required secrets template
├── upload_checklist.md          # Deployment checklist
├── orchestrator/
│   ├── agent.py                 # Self-contained orchestrator
│   ├── schemas.py               # Required schemas
│   └── requirements.txt         # Minimal dependencies
├── quant_screener/
│   ├── agent.py
│   ├── schemas.py
│   └── requirements.txt
├── risk_manager/
│   ├── agent.py
│   ├── schemas.py
│   └── requirements.txt
└── deep_researcher/
    ├── agent.py
    ├── schemas.py
    └── requirements.txt
```

## Prerequisites

- Agentverse account
- Google Gemini API key
- Unique seeds for each agent (generate with `uagents-generate-seed` or similar)

## Quick Start

### 1. Generate Agent Seeds

```bash
# Generate unique seeds for each agent
python -c "from uagents.crypto import Identity; print(Identity.generate().seed)"
# Run 4 times for 4 agents
```

### 2. Configure Secrets

Copy `secrets.example.md` and fill in your values:

| Secret | Orchestrator | QuantScreener | RiskManager | DeepResearcher |
|--------|-------------|---------------|-------------|----------------|
| `AGENT_SEED` | ✅ | ✅ | ✅ | ✅ |
| `GEMINI_API_KEY` | ✅ | | | ✅ |
| `MAILBOX_KEY` | ✅ | ✅ | ✅ | ✅ |
| Downstream addresses | ✅ | | | |

### 3. Deploy Agents

Deploy in this order (dependencies first):

1. **QuantScreener** - No dependencies
2. **RiskManager** - No dependencies  
3. **DeepResearcher** - Requires Gemini API key
4. **Orchestrator** - Requires all downstream agent addresses

### 4. Wire Up Addresses

After deploying each agent, note its address and update the orchestrator's secrets:
- `QUANT_SCREENER_ADDRESS`
- `RISK_MANAGER_ADDRESS`
- `DEEP_RESEARCHER_ADDRESS`

Then redeploy orchestrator.

## Agent Entry Points

Each agent directory contains a self-contained `agent.py` that includes:
- All required schema definitions (copied from shared)
- Service logic (inline or imported)
- Protocol definitions
- Message handlers

This is necessary because Agentverse may not support the full project structure.

## Requirements

Each agent has a minimal `requirements.txt`:

```
uagents==0.26.1
pydantic==2.14.1
yfinance==1.7.0
google-generativeai==0.8.6
httpx==0.28.1
python-dotenv==1.2.4
```

## Testing Deployment

After deployment, test each agent:

```bash
# Test orchestrator chat
curl -X POST https://agentverse.ai/api/v1/agents/<orchestrator_address>/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello FinancePilot"}'
```

## Troubleshooting

### Common Issues

1. **Agent fails to start**: Check logs in Agentverse dashboard
2. **Message delivery fails**: Verify agent addresses are correct
3. **Gemini errors**: Verify API key is set correctly in secrets
4. **Import errors**: Ensure all schemas are included in agent.py

### Debugging

- Check Agentverse logs for each agent
- Use `agent.on_event("startup")` to log configuration
- Verify message schemas match between sender and receiver

## Updating Agents

To update a deployed agent:

1. Modify the agent code
2. Redeploy through Agentverse dashboard
3. Agent address remains the same
4. No need to update downstream agents unless protocol changes

## Security Notes

- Never commit seeds or API keys to git
- Use Agentverse Secrets for all sensitive values
- Rotate seeds periodically in production
- Monitor agent logs for unusual activity

## Support

For Agentverse-specific issues, consult:
- [Agentverse Documentation](https://docs.agentverse.ai)
- [uAgents Documentation](https://docs.fetch.ai/uagents)
- Fetch.ai Discord community