"""Configuración de la aplicación, leída desde variables de entorno / .env."""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# El .env vive en la RAÍZ del proyecto (junto a la carpeta app/), sin importar
# desde qué carpeta se ejecute uvicorn.
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Amazon RDS
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: SecretStr
    db_name: str = "vehiculo_iot"
    db_pool_size: int = 10
    db_connect_timeout: int = 10

    # Autorización por API key
    api_key_admin: Optional[SecretStr] = None
    api_key_control: Optional[SecretStr] = None

    # Sesiones del dashboard. Genera el secreto con:
    # python -c "import secrets; print(secrets.token_urlsafe(48))"
    dashboard_session_secret: Optional[SecretStr] = None
    dashboard_session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    # Debe permanecer en true en EC2 cuando el sitio use HTTPS.
    # Solo usa false para pruebas locales por HTTP en localhost.
    dashboard_cookie_secure: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
