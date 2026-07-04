from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    # parameters:
    LLM_BASE_URL: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# @lru_cache
def get_LLM_settings() -> LLMSettings:
    return LLMSettings()


if __name__ == "__main__":
    pass
