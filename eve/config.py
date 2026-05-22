"""Configuration management for Eve Agent."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Eve Agent settings loaded from environment variables."""

    model_config = {"env_prefix": "EVE_", "env_file": ".env", "extra": "ignore"}

    # LLM Providers — Coding Plan (DashScope) preferred over direct Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    coding_plan_api_key: str = Field(default="", alias="CODING_PLAN_API_KEY")
    coding_plan_base_url: str = Field(
        default="https://coding-intl.dashscope.aliyuncs.com/apps/anthropic",
        alias="CODING_PLAN_BASE_URL",
    )
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest", alias="OLLAMA_MODEL")
    ollama_api_key: str = Field(default="", alias="OLLAMA_API_KEY")

    # Default provider
    default_provider: str = "ollama"
    default_model: str = "jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest"

    # Hyperbrowser
    hyperbrowser_api_key: str = Field(default="", alias="HYPERBROWSER_API_KEY")

    # Tavily Search API
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    # Messaging
    discord_bot_token: str = Field(default="", alias="DISCORD_BOT_TOKEN")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")

    # Marketing & CRM
    hubspot_api_key: str = Field(default="", alias="HUBSPOT_API_KEY")
    figma_api_key: str = Field(default="", alias="FIGMA_API_KEY")
    canva_api_key: str = Field(default="", alias="CANVA_API_KEY")

    # Finance & Trading
    finnhub_api_key: str = Field(default="", alias="FINNHUB_API_KEY")
    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(default="", alias="ALPACA_SECRET_KEY")
    alpaca_paper: bool = True

    # Lumina — market analysis consciousness
    lumina_model: str = Field(default="qwen3.5:397b-cloud", alias="LUMINA_MODEL")

    # Memory
    memory_dir: str = "./eve_data/memory"

    # Web server
    web_host: str = "0.0.0.0"
    web_port: int = 8006

    # Security
    owner_id: str = ""

    # D1 User Database (Cloudflare Worker) — set D1_WORKER_URL to your own worker
    d1_worker_url: str = Field(
        default="",
        alias="D1_WORKER_URL",
    )
    d1_api_secret: str = Field(default="", alias="EVE_D1_API_SECRET")
    jwt_secret: str = Field(default="eve-cosmic-jwt-secret-change-me", alias="EVE_JWT_SECRET")

    # Personality
    personality_intensity: float = 0.8

    # X Content Agent
    x_agent_autostart: bool = Field(default=True, alias="X_AGENT_AUTOSTART")
    x_agent_mode: str = Field(default="queue", alias="X_AGENT_MODE")
    x_agent_posts_per_day: int = Field(default=3, alias="X_AGENT_POSTS_PER_DAY")

    @property
    def memory_path(self) -> Path:
        path = Path(self.memory_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def has_provider(self, name: str) -> bool:
        """Check if a provider has valid credentials configured."""
        if name == "anthropic":
            return bool(self.coding_plan_api_key or self.anthropic_api_key)
        elif name == "openai":
            return bool(self.openai_api_key)
        elif name == "ollama":
            return True  # Ollama runs locally, always available
        return False

    def get_best_provider(self) -> str:
        """Get the best available provider, preferring the default."""
        if self.has_provider(self.default_provider):
            return self.default_provider
        for provider in ["ollama", "anthropic", "openai"]:
            if self.has_provider(provider):
                return provider
        return "ollama"
