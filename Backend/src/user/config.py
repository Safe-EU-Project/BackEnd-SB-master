from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PUBLIC → issuer validation
    keycloak_public_url: str

    # INTERNAL → SAME docker Network
    keycloak_internal_url: str

    keycloak_realm: str
    keycloak_client_id: str
    keycloak_client_secret: str
    strict_audience: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
