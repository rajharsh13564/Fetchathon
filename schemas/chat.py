from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4
from schemas.common import CorrelationContext, InvestmentHorizon, RiskProfile


class ChatRequest(BaseModel):
    """Natural language chat request."""
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    portfolio_context: Optional[Dict[str, Any]] = None
    investment_horizon: Optional[InvestmentHorizon] = None
    risk_profile: Optional[RiskProfile] = None
    correlation_context: CorrelationContext = Field(default_factory=CorrelationContext)

    def get_or_create_conversation_id(self) -> str:
        """Get existing conversation ID or create new one."""
        if self.conversation_id:
            return self.conversation_id
        self.conversation_id = str(uuid4())
        return self.conversation_id


class ChatMessage(BaseModel):
    """A single chat message in history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    message_type: str = "text"  # "text", "portfolio_analysis", "screening_result", "research_report", "error"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    message: str
    conversation_id: str
    message_type: str = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    correlation_context: CorrelationContext
    requires_clarification: bool = False
    clarification_questions: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)


class ConversationHistory(BaseModel):
    """Full conversation history."""
    conversation_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    portfolio_context: Optional[Dict[str, Any]] = None