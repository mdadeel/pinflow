from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    pinterest_access_token: str = ""
    pinterest_board_id: str = ""
    openrouter_model: str = "google/gemini-2.5-flash"

    # LLM provider overrides. OpenRouter is the default; set these to use any
    # OpenAI-chat or Anthropic-messages compatible endpoint (see mini.md).
    # LLM_API_KEY / LLM_MODEL fall back to the openrouter_* values when unset.
    llm_base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_protocol: str = "openai"  # "openai" (chat/completions) | "anthropic" (messages)

    # JSON list of providers for automatic failover (see mini.md). When one key
    # runs out of credits / is rate-limited, the next working key is used.
    # Each entry: {"name", "protocol" ("openai"|"anthropic"), "base_url",
    #              "api_key", "model"}.
    llm_providers: str = ""

    batch_size: int = 25
    analysis_workers: int = 3
    posts_per_day: int = 5
    post_hours: Annotated[list[int], NoDecode] = [8, 11, 14, 17, 20]

    @field_validator("post_hours", mode="before")
    @classmethod
    def _split_post_hours(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_allowed_origins(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    watch_dir: Path = Path("images")
    images_dir: Path = Path("pinterest_automation/storage/images")
    log_dir: Path = Path("pinterest_automation/logs")
    reports_dir: Path = Path("pinterest_automation/logs/reports")
    db_url: str = "sqlite:///pinterest_automation/data.db"

    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    ws_secret: str = ""
    api_key: str = ""

    board_overrides: dict[str, str] = {}


settings = Settings()
