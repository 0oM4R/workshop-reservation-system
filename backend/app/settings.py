"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings read from environment variables; the defaults suit local development."""

    database_url: str = (
        "postgresql+asyncpg://workshops:workshops@localhost:5432/workshops"
    )
    test_database_url: str = (
        "postgresql+asyncpg://workshops:workshops@localhost:5432/workshops_test"
    )


settings = Settings()
