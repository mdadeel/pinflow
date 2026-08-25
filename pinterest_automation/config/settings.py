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

    batch_size: int = 25
    posts_per_day: int = 5
    post_hours: Annotated[list[int], NoDecode] = [8, 11, 14, 17, 20]

    @field_validator("post_hours", mode="before")
    @classmethod
    def _split_post_hours(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v

    watch_dir: Path = Path("images")
    images_dir: Path = Path("pinterest_automation/storage/images")
    log_dir: Path = Path("pinterest_automation/logs")
    reports_dir: Path = Path("pinterest_automation/logs/reports")
    db_url: str = "sqlite:///pinterest_automation/data.db"


settings = Settings()
