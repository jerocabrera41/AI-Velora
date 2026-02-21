from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token")

    # Anthropic
    anthropic_api_key: str = Field(default="", description="Anthropic API key")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./hotel_agent.db",
        description="Database connection URL",
    )

    # App
    secret_key: str = Field(default="dev-secret-key", description="App secret key")
    debug: bool = Field(default=True, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # LangSmith (optional)
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str = Field(default="")

    # Agent
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use",
    )
    max_conversation_history: int = Field(
        default=10,
        description="Max messages to keep in conversation context",
    )
    conversation_timeout_hours: int = Field(
        default=2,
        description="Hours before auto-closing inactive conversation",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
