from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Gemini API
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-1.5-flash", description="Gemini model name")

    # Prompts
    finpilot_system_prompt: str = Field(
        default=(
            "You are FinancePilot AI, a helpful financial research assistant for Indian equity markets. "
            "Provide accurate, balanced, and educational responses. Never guarantee returns or give "
            "personalized investment advice. Always distinguish between facts, calculations, and opinions. "
            "Cite sources when possible."
        ),
        description="System prompt for the orchestrator agent",
    )
    finpilot_research_prompt: str = Field(
        default=(
            "You are a senior equity research analyst specializing in Indian markets. "
            "Provide thorough, balanced analysis with clear bull and bear cases. "
            "Cite specific financial metrics and business fundamentals. "
            "Distinguish verified data from estimates and opinions."
        ),
        description="System prompt for the deep researcher agent",
    )

    # Market Data
    market_data_cache_ttl: int = Field(default=60, description="Market data cache TTL in seconds")

    # API Server
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    frontend_url: str = Field(default="http://localhost:5173", description="Frontend URL for CORS")

    # Agent Seeds (for Agentverse deployment)
    orchestrator_seed: str = Field(default="orchestrator_seed_change_in_production", description="Orchestrator agent seed")
    quant_screener_seed: str = Field(default="quant_screener_seed_change_in_production", description="Quant screener agent seed")
    risk_manager_seed: str = Field(default="risk_manager_seed_change_in_production", description="Risk manager agent seed")
    deep_researcher_seed: str = Field(default="deep_researcher_seed_change_in_production", description="Deep researcher agent seed")

    # Agentverse Mailbox Keys
    orchestrator_mailbox_key: Optional[str] = Field(default=None, description="Orchestrator mailbox key")
    quant_screener_mailbox_key: Optional[str] = Field(default=None, description="Quant screener mailbox key")
    risk_manager_mailbox_key: Optional[str] = Field(default=None, description="Risk manager mailbox key")
    deep_researcher_mailbox_key: Optional[str] = Field(default=None, description="Deep researcher mailbox key")

    # Downstream Agent Addresses (for local development)
    quant_screener_address: Optional[str] = Field(default=None, description="Quant screener agent address")
    risk_manager_address: Optional[str] = Field(default=None, description="Risk manager agent address")
    deep_researcher_address: Optional[str] = Field(default=None, description="Deep researcher agent address")

    def validate_gemini_key(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()