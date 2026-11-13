from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Competitive Programming Platform"
    DEBUG: bool = True

    # Backend & CORS
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Security & Tokens
    SECRET_KEY: str = "change-this-to-a-very-secure-random-secret-key-in-production"
    JWT_SECRET_KEY: str = "change-this-to-a-very-secure-jwt-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_DOMAIN: str = "localhost"
    COOKIE_SECURE: bool = False

    # Database
    POSTGRES_SERVER: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cp_platform"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_secure_password"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_secure_password@postgres:5432/cp_platform"

    # Redis & Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Judge0
    JUDGE0_URL: str = "http://judge0-server:2358"
    JUDGE0_AUTH_TOKEN: str = ""
    JUDGE0_CALLBACK_SECRET: str = "change-this-judge0-callback-hmac-secret-in-production"
    JUDGE0_TIMEOUT_SECONDS: int = 10
    JUDGE0_MAX_BATCH_SIZE: int = 20

    # S3 Object Storage
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_REGION: str = "us-east-1"
    S3_BUCKET_EVIDENCE: str = "cp-evidence-screenshots"
    S3_BUCKET_TESTCASES: str = "cp-hidden-testcases"
    S3_PRESIGNED_EXPIRATION_SECONDS: int = 900

    # Proctoring
    PROCTORING_SCREENSHOT_INTERVAL_SEC: int = 60
    PROCTORING_SCREENSHOT_MAX_WIDTH: int = 640
    PROCTORING_SCREENSHOT_MAX_HEIGHT: int = 360
    PROCTORING_SCREENSHOT_MAX_KB: int = 100
    PROCTORING_TAB_COOLDOWN_SECONDS: int = 30
    PROCTORING_EVIDENCE_RETENTION_DAYS: int = 7

    # Email
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = False
    EMAILS_FROM_EMAIL: str = "no-reply@cpplatform.local"
    EMAILS_FROM_NAME: str = "Competitive Programming Platform"


settings = Settings()
