"""Configuración de la aplicación, leída desde variables de entorno / .env."""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
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

    # Autorización por API key (si no se configuran, las operaciones protegidas se rechazan)
    api_key_admin: Optional[SecretStr] = None
    api_key_control: Optional[SecretStr] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
