from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://reprox:reprox_dev_password@localhost:5432/reprox"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    sandbox_image: str = "reprox-sklearn-runner:latest"
    sandbox_timeout_seconds: int = 120
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: str = "1"

    workloads_dir: str = "../workloads"
    artifacts_dir: str = "../.data/artifacts"

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
