import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    Field,
    ConfigDict,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class MonitoringSettings(BaseSettings):
    """
    Configuration settings for monitoring services like Grafana and Prometheus.
    """

    # Grafana Settings
    GRAFANA_PORT: int = Field(default=3000, validation_alias="GRAFANA_PORT")
    GRAFANA_URL: str = Field(
        default="http://localhost:3000", validation_alias="GRAFANA_URL"
    )
    GRAFANA_API_KEY: str = Field(
        default="your_default_api_key", validation_alias="GRAFANA_API_KEY"
    )

    # Prometheus Settings
    PROMETHEUS_PORT: int = Field(default=9090, validation_alias="PROMETHEUS_PORT")
    PROMETHEUS_URL: str = Field(
        default="http://localhost:9090", validation_alias="PROMETHEUS_URL"
    )

    model_config = ConfigDict(
        env_prefix="",  # No prefix, uses validation_alias directly
        case_sensitive=False,
        extra="ignore",
    )


class PulsarSettings(BaseSettings):
    """
    Configuration settings for Apache Pulsar messaging service.
    """

    # Connection settings
    PULSAR_ADVERTISED_ADDRESS: str = Field(
        default="localhost", validation_alias="PULSAR_ADVERTISED_ADDRESS"
    )
    PULSAR_BROKER_PORT: int = Field(
        default=6650, validation_alias="PULSAR_BROKER_PORT"
    )

    # TLS settings
    PULSAR_TLS_CERT_PATH: str = Field(
        default="", validation_alias="PULSAR_TLS_CERT_PATH"
    )
    PULSAR_TLS_KEY_PATH: str = Field(default="", validation_alias="PULSAR_TLS_KEY_PATH")
    PULSAR_TLS_CA_PATH: str = Field(default="", validation_alias="PULSAR_TLS_CA_PATH")

    # Authentication settings
    PULSAR_AUTH_TOKEN: str = Field(default="", validation_alias="PULSAR_AUTH_TOKEN")
    PULSAR_JWT_TOKEN: str = Field(default="", validation_alias="PULSAR_JWT_TOKEN")

    class Config:
        env_file = ".env"
        case_sensitive = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: EmailStr | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    # Add these URLs for health checks
    monitoring: MonitoringSettings = MonitoringSettings()
    
    # Pulsar messaging settings
    pulsar: PulsarSettings = PulsarSettings()

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
