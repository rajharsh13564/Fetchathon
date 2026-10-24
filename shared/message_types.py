"""Message type definitions and serialization utilities."""
from typing import Type, Dict, Any, TypeVar, get_args
from pydantic import BaseModel
from uagents_core.models import Model as UAgentModel


T = TypeVar("T", bound=BaseModel)


def get_message_types() -> Dict[str, Type[BaseModel]]:
    """Get all message types used across agents."""
    from schemas.portfolio import (
        PortfolioInput,
        PortfolioAnalysisResponse,
        HoldingItem,
        HoldingSnapshot,
        PortfolioSnapshot,
    )
    from schemas.screening import (
        ScreeningRequest,
        RankedShortlistResponse,
        ScreenedStock,
        ScreeningFilters,
    )
    from schemas.research import (
        ResearchRequest,
        AgenticThesisResponse,
        EvidenceSource,
        ThesisSection,
    )
    from schemas.chat import (
        ChatRequest,
        ChatResponse,
        ChatMessage,
        ConversationHistory,
    )
    from schemas.common import (
        ErrorResponse,
        CorrelationContext,
        AgentInfo,
        InvestmentHorizon,
        RiskProfile,
        AgentStatus,
    )

    return {
        # Portfolio
        "PortfolioInput": PortfolioInput,
        "PortfolioAnalysisResponse": PortfolioAnalysisResponse,
        "HoldingItem": HoldingItem,
        "HoldingSnapshot": HoldingSnapshot,
        "PortfolioSnapshot": PortfolioSnapshot,
        # Screening
        "ScreeningRequest": ScreeningRequest,
        "RankedShortlistResponse": RankedShortlistResponse,
        "ScreenedStock": ScreenedStock,
        "ScreeningFilters": ScreeningFilters,
        # Research
        "ResearchRequest": ResearchRequest,
        "AgenticThesisResponse": AgenticThesisResponse,
        "EvidenceSource": EvidenceSource,
        "ThesisSection": ThesisSection,
        # Chat
        "ChatRequest": ChatRequest,
        "ChatResponse": ChatResponse,
        "ChatMessage": ChatMessage,
        "ConversationHistory": ConversationHistory,
        # Common
        "ErrorResponse": ErrorResponse,
        "CorrelationContext": CorrelationContext,
        "AgentInfo": AgentInfo,
        "InvestmentHorizon": InvestmentHorizon,
        "RiskProfile": RiskProfile,
        "AgentStatus": AgentStatus,
    }


def validate_message_compatibility(
    sender_model: Type[BaseModel],
    receiver_model: Type[BaseModel],
) -> bool:
    """
    Validate that a sender's message model is compatible with receiver's expected model.
    Checks if sender_model fields are subset of receiver_model fields.
    """
    sender_fields = set(sender_model.model_fields.keys())
    receiver_fields = set(receiver_model.model_fields.keys())
    return sender_fields.issubset(receiver_fields)


def serialize_message(message: BaseModel) -> Dict[str, Any]:
    """Serialize a message for transport."""
    return message.model_dump(mode="json")


def deserialize_message(data: Dict[str, Any], model: Type[T]) -> T:
    """Deserialize a message from transport format."""
    return model.model_validate(data)


# Agent message handlers registry
class MessageHandlerRegistry:
    """Registry for agent message handlers."""

    def __init__(self):
        self._handlers: Dict[str, Dict[str, Any]] = {}

    def register(self, agent_name: str, message_type: str, handler: Any) -> None:
        """Register a handler for an agent and message type."""
        if agent_name not in self._handlers:
            self._handlers[agent_name] = {}
        self._handlers[agent_name][message_type] = handler

    def get_handler(self, agent_name: str, message_type: str) -> Any:
        """Get handler for agent and message type."""
        return self._handlers.get(agent_name, {}).get(message_type)

    def get_agent_handlers(self, agent_name: str) -> Dict[str, Any]:
        """Get all handlers for an agent."""
        return self._handlers.get(agent_name, {})


# Global registry instance
message_registry = MessageHandlerRegistry()