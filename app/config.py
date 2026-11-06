import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    app_name: str = "SYSCRAFT QR CODE STUDIO"
    secret_key: str = "development-only-change-me"
    database_url: str = f"sqlite:///{BASE_DIR / 'qr_studio.db'}"
    max_upload_bytes: int = 2 * 1024 * 1024
    rate_limit: str = "30/minute"
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

settings = Settings()
DATA_DIR = os.getenv("DATA_DIR")
RUNTIME_DIR = Path(DATA_DIR) if DATA_DIR else Path("/tmp/qr-studio") if os.getenv("VERCEL") else BASE_DIR
GENERATED_DIR = RUNTIME_DIR / "generated_qr" if DATA_DIR or os.getenv("VERCEL") else BASE_DIR / "app" / "static" / "generated_qr"
UPLOAD_DIR = RUNTIME_DIR / "uploads" if DATA_DIR or os.getenv("VERCEL") else BASE_DIR / "uploads"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

