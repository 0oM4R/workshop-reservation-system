"""Application configuration loaded from the environment."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Settings read from the environment, then the repo-root `.env` if present."""

    model_config = SettingsConfigDict(env_file=REPO_ROOT_ENV_FILE)

    database_url: str = (
        "postgresql+asyncpg://workshops:workshops@localhost:5432/workshops"
    )
    test_database_url: str = (
        "postgresql+asyncpg://workshops:workshops@localhost:5432/workshops_test"
    )
    seed_data: bool = False


settings = Settings()
