from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # DeepL
    deepl_api_key: Optional[str] = Field(default=None, alias="DEEPL_API_KEY")

    # bit.ly
    bitly_api_key: Optional[str] = Field(default=None, alias="BITLY_API_KEY")

    # Viber
    viber_bot_token: Optional[str] = Field(default=None, alias="VIBER_BOT_TOKEN")
    viber_bot_name: str = Field(default="BuyerAnons", alias="VIBER_BOT_NAME")
    viber_webhook_url: Optional[str] = Field(default=None, alias="VIBER_WEBHOOK_URL")

    # Defaults
    default_top_count: int = Field(default=10, alias="DEFAULT_TOP_COUNT")
    default_min_discount: int = Field(default=30, alias="DEFAULT_MIN_DISCOUNT")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
