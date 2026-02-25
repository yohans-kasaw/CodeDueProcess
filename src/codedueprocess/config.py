from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for the CodeDueProcess application."""

    # LLM Settings
    LLM_MODEL: str = "gpt-4o"
    TEMPERATURE: float = 0.0

    # LangChain / LangSmith Settings
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "CodeDueProcess"

    # Environment
    APP_ENV: str = "development"

    # Paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    DB_PATH: str = str(PROJECT_ROOT / ".langchain.db")
    CHROMA_PATH: str = "./chroma_db"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
