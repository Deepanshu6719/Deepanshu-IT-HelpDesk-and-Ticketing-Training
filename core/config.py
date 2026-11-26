# BaseSettings is a class - read env variables ,
# convert values in declared python types,
# validate config values,load values from .env
# Settings is a class that defines how configuration should be loaded.
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL configuration
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str

    # Authentication configuration
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    SESSION_EXPIRE_DAYS: int

    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Celery configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    LOG_LEVEL: str = "INFO"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    # CORS configuration
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Security configuration
    SECURITY_HSTS_ENABLED: bool = False
    SECURITY_HSTS_MAX_AGE: int = Field(
        default=31536000,
        ge=0,
    )

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_cors_origins(
        cls,
        origins: list[str],
    ) -> list[str]:
        for origin in origins:
            if "*" in origin:
                raise ValueError("Wildcard CORS origins are not allowed")

            if not origin.startswith(("http://", "https://")):
                raise ValueError("CORS origins must use HTTP or HTTPS")

            if origin.endswith("/"):
                raise ValueError("CORS origins must not end with a slash")

        return origins


settings = Settings()  # creates an object and loads the actual configuration values.
