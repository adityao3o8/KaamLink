import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_llm_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    groq_stt_model: str = "whisper-large-v3"
    database_url: str = f"sqlite:///{BASE_DIR / 'kaamlink.db'}"
    alert_timeout_seconds: int = 60
    demo_mode: bool = False
    enable_twilio: bool = False
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    cors_origins: str = "*"
    port: int = 8000
    auto_seed: bool = True

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "*").strip()
        if raw == "*":
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]


settings = Settings()
# Allow PORT from hosting platforms
if os.getenv("PORT"):
    try:
        settings.port = int(os.getenv("PORT"))
    except ValueError:
        pass
