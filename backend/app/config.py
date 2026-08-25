"""Application configuration via Pydantic Settings.

All configuration comes from environment variables (optionally a local
``.env`` file). Credentials are never hardcoded.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: .../researchpilot
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class LLMProvider(str, Enum):
    """Which LLM backend the agents call."""

    ollama = "ollama"
    openai = "openai"


class DemoScenario(str, Enum):
    """Deterministic workshop demo scenarios."""

    normal = "normal"
    slow_search = "slow_search"
    search_failure = "search_failure"
    search_retry = "search_retry"
    expensive_agent = "expensive_agent"
    agent_loop = "agent_loop"
    parallel_research = "parallel_research"
    low_groundedness = "low_groundedness"


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM provider ---
    llm_provider: LLMProvider = Field(default=LLMProvider.ollama, alias="LLM_PROVIDER")

    # --- OpenAI (only required when LLM_PROVIDER=openai) ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # --- Ollama (default provider; no API key needed, runs locally) ---
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )

    # --- Langfuse ---
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", alias="LANGFUSE_HOST"
    )
    langfuse_capture_input: bool = Field(
        default=False, alias="LANGFUSE_CAPTURE_INPUT"
    )

    # --- Runtime ---
    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Timeouts ---
    tool_timeout_seconds: float = Field(default=10.0, alias="TOOL_TIMEOUT_SECONDS")
    llm_timeout_seconds: float = Field(default=30.0, alias="LLM_TIMEOUT_SECONDS")

    # --- Retries / loops ---
    max_retries: int = Field(default=2, alias="MAX_RETRIES")
    max_research_iterations: int = Field(default=2, alias="MAX_RESEARCH_ITERATIONS")

    # --- Limits ---
    max_question_length: int = Field(default=4000, alias="MAX_QUESTION_LENGTH")

    # --- Demo ---
    demo_mode: bool = Field(default=True, alias="DEMO_MODE")
    demo_scenario: DemoScenario = Field(
        default=DemoScenario.normal, alias="DEMO_SCENARIO"
    )

    # --- Data locations ---
    data_dir: Path = Field(default=DATA_DIR)

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def mock_search_file(self) -> Path:
        return self.data_dir / "mock_search" / "sources.json"

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def active_model(self) -> str:
        """The model name for whichever provider is active."""

        if self.llm_provider is LLMProvider.openai:
            return self.openai_model
        return self.ollama_model

    @property
    def llm_configured(self) -> bool:
        """Whether the active provider is ready to serve real requests.

        Ollama needs no key (reachability is checked at call time, same as
        any other network dependency); OpenAI needs an API key.
        """

        if self.llm_provider is LLMProvider.openai:
            return self.openai_configured
        return True

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def service_name(self) -> str:
        return "researchpilot-backend"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()


settings = get_settings()
