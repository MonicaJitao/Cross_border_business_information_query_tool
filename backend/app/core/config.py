from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # 搜索源
    metaso_api_key: Optional[str] = Field(default=None, alias="METASO_API_KEY")
    baidu_api_key: Optional[str] = Field(default=None, alias="BAIDU_API_KEY")
    volcengine_api_key: Optional[str] = Field(default=None, alias="VOLCENGINE_API_KEY")

    # Claude 中转站（后端预置）
    claude_proxy_base_url: Optional[str] = Field(default=None, alias="CLAUDE_PROXY_BASE_URL")
    claude_proxy_api_key: Optional[str] = Field(default=None, alias="CLAUDE_PROXY_API_KEY")
    claude_proxy_default_model: str = Field(default="claude-3-5-sonnet-20241022", alias="CLAUDE_PROXY_DEFAULT_MODEL")

    # DeepSeek 官方（后端预置）
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", alias="DEEPSEEK_BASE_URL")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_default_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_DEFAULT_MODEL")

    @field_validator(
        "metaso_api_key",
        "baidu_api_key",
        "volcengine_api_key",
        "claude_proxy_api_key",
        "deepseek_api_key",
        mode="before",
    )
    @classmethod
    def _normalize_optional_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


settings = Settings()


def get_settings(refresh: bool = False) -> Settings:
    global settings
    if refresh:
        settings = Settings()
    return settings


def get_env_file_value(key: str) -> Optional[str]:
    """
    直接从项目根目录 .env 读取指定变量。
    作为 Settings 读取失败时的兜底来源。
    """
    try:
        if not ENV_FILE.exists():
            return None
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() != key:
                continue
            value = v.strip().strip('"').strip("'").strip()
            return value or None
    except Exception:
        return None
    return None

# 调试输出：检查环境变量加载情况
print("=" * 60)
print("[配置加载诊断]")
print(f"  metaso_api_key: {'已配置 (长度: ' + str(len(settings.metaso_api_key)) + ')' if settings.metaso_api_key else '未配置'}")
print(f"  baidu_api_key: {'已配置 (长度: ' + str(len(settings.baidu_api_key)) + ')' if settings.baidu_api_key else '未配置'}")
print(f"  volcengine_api_key: {'已配置 (长度: ' + str(len(settings.volcengine_api_key)) + ')' if settings.volcengine_api_key else '未配置'}")
if settings.volcengine_api_key:
    print(f"  volcengine_api_key 值: {settings.volcengine_api_key}")
else:
    print(f"  ✗ 火山引擎 API Key 未加载，请检查 .env 文件！")
print("=" * 60)
