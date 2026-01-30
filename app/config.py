"""
Configuració de l'Agent OCR
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configuració de l'aplicació"""

    # App
    app_name: str = "OCR Agent"
    app_version: str = "1.0.0"
    debug: bool = False

    # Google Cloud Vision
    google_cloud_vision_enabled: bool = True
    google_cloud_credentials_json: Optional[str] = None
    google_cloud_project_id: Optional[str] = None

    # Tesseract
    tesseract_enabled: bool = True
    tesseract_lang: str = "spa+cat+eng"

    # API
    api_key_enabled: bool = False
    api_keys: list[str] = []

    # Limits
    max_file_size_mb: int = 10
    rate_limit_per_minute: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = False


# Singleton de configuració
settings = Settings()
