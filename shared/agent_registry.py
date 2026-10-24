"""Agent registry for managing agent addresses and capabilities."""
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from schemas.common import AgentInfo, AgentStatus


@dataclass
class AgentRegistration:
    """Registration info for an agent."""
    name: str
    address: str
    seed: str
    protocol: str
    capabilities: List[str] = field(default_factory=list)
    mailbox_key: Optional[str] = None
    status: AgentStatus = AgentStatus.HEALTHY
    metadata: Dict[str, str] = field(default_factory=dict)


class AgentRegistry:
    """Registry of known agents and their capabilities."""

    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}

    def register(self, registration: AgentRegistration) -> None:
        """Register an agent."""
        self._agents[registration.name] = registration

    def unregister(self, name: str) -> None:
        """Unregister an agent."""
        self._agents.pop(name, None)

    def get(self, name: str) -> Optional[AgentRegistration]:
        """Get agent by name."""
        return self._agents.get(name)

    def get_address(self, name: str) -> Optional[str]:
        """Get agent address by name."""
        agent = self._agents.get(name)
        return agent.address if agent else None

    def get_all(self) -> Dict[str, AgentRegistration]:
        """Get all registered agents."""
        return self._agents.copy()

    def get_by_protocol(self, protocol: str) -> List[AgentRegistration]:
        """Get agents by protocol."""
        return [a for a in self._agents.values() if a.protocol == protocol]

    def update_status(self, name: str, status: AgentStatus) -> None:
        """Update agent status."""
        if name in self._agents:
            self._agents[name].status = status

    def is_available(self, name: str) -> bool:
        """Check if agent is available."""
        agent = self._agents.get(name)
        return agent is not None and agent.status == AgentStatus.HEALTHY and bool(agent.address)


# Default agent configurations for local development
def create_default_registry() -> AgentRegistry:
    """Create registry with default local agent configurations."""
    registry = AgentRegistry()

    # These would be populated from environment or config in production
    registry.register(AgentRegistration(
        name="orchestrator",
        address="",  # Filled at runtime
        seed="orchestrator_seed_change_in_production",
        protocol="finpilot.orchestrator.v1",
        capabilities=["chat", "portfolio_analysis", "coordination"],
    ))

    registry.register(AgentRegistration(
        name="quant_screener",
        address="",
        seed="quant_screener_seed_change_in_production",
        protocol="finpilot.quant_screener.v1",
        capabilities=["screening", "quantitative_analysis"],
    ))

    registry.register(AgentRegistration(
        name="risk_manager",
        address="",
        seed="risk_manager_seed_change_in_production",
        protocol="finpilot.risk_manager.v1",
        capabilities=["risk_analysis", "concentration_analysis", "volatility_analysis"],
    ))

    registry.register(AgentRegistration(
        name="deep_researcher",
        address="",
        seed="deep_researcher_seed_change_in_production",
        protocol="finpilot.deep_researcher.v1",
        capabilities=["fundamental_research", "bull_bear_analysis", "valuation"],
    ))

    return registry