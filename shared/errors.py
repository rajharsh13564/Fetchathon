"""Custom exceptions for FinancePilot AI."""
from typing import Optional, Any, Dict


class FinancePilotError(Exception):
    """Base exception for FinancePilot AI."""

    def __init__(
        self,
        message: str,
        code: str = "FINPILOT_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.message,
            "code": self.code,
            "details": self.details,
        }


class ConfigurationError(FinancePilotError):
    """Raised when configuration is invalid or missing."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)


class AgentUnavailableError(FinancePilotError):
    """Raised when a downstream agent is unavailable."""
    def __init__(self, agent_name: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Agent '{agent_name}' is unavailable",
            "AGENT_UNAVAILABLE",
            {"agent_name": agent_name, **(details or {})},
        )


class AgentCommunicationError(FinancePilotError):
    """Raised when agent communication fails."""
    def __init__(self, agent_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Communication with '{agent_name}' failed: {message}",
            "AGENT_COMMUNICATION_ERROR",
            {"agent_name": agent_name, "original_error": message, **(details or {})},
        )


class MarketDataError(FinancePilotError):
    """Raised when market data retrieval fails."""
    def __init__(self, message: str, ticker: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "MARKET_DATA_ERROR",
            {"ticker": ticker, **(details or {})},
        )


class ValidationError(FinancePilotError):
    """Raised when input validation fails."""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "VALIDATION_ERROR",
            {"field": field, **(details or {})},
        )


class GeminiAPIError(FinancePilotError):
    """Raised when Gemini API call fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "GEMINI_API_ERROR", details)


class RateLimitError(FinancePilotError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "RATE_LIMIT_ERROR",
            {"retry_after": retry_after, **(details or {})},
        )


class TimeoutError(FinancePilotError):
    """Raised when an operation times out."""
    def __init__(self, operation: str, timeout_seconds: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds}s",
            "TIMEOUT_ERROR",
            {"operation": operation, "timeout_seconds": timeout_seconds, **(details or {})},
        )


class InsufficientDataError(FinancePilotError):
    """Raised when there's insufficient data for an operation."""
    def __init__(self, message: str, missing_fields: Optional[list] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "INSUFFICIENT_DATA_ERROR",
            {"missing_fields": missing_fields or [], **(details or {})},
        )