from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://taskmanager@localhost:5433/taskmanager_dev"
    test_database_url: str = "postgresql+asyncpg://taskmanager@localhost:5433/taskmanager_test"
    auth_header_name: str = "X-User-Id"
    max_page_size: int = 100


settings = Settings()
