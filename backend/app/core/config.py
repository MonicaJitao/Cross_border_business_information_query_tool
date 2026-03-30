from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 搜索源
    metaso_api_key: Optional[str] = Field(default=None, alias="METASO_API_KEY")
    baidu_api_key: Optional[str] = Field(default=None, alias="BAIDU_API_KEY")

    # Claude 中转站（后端预置）
    claude_proxy_base_url: Optional[str] = Field(default=None, alias="CLAUDE_PROXY_BASE_URL")
    claude_proxy_api_key: Optional[str] = Field(default=None, alias="CLAUDE_PROXY_API_KEY")
    claude_proxy_default_model: str = Field(default="claude-3-5-sonnet-20241022", alias="CLAUDE_PROXY_DEFAULT_MODEL")

    # DeepSeek 官方（后端预置）
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", alias="DEEPSEEK_BASE_URL")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_default_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_DEFAULT_MODEL")


settings = Settings()
