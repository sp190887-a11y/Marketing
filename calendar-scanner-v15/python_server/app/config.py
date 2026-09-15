from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Нарисуй сам"
    app_version: str = "15.4"
    environment: str = os.getenv("APP_ENV", "development")
    frontend_dir: Path = Path(os.getenv("FRONTEND_DIR", str(ROOT))).resolve()
    data_dir: Path = Path(os.getenv("DATA_DIR", str(SERVER_ROOT / "data"))).resolve()
    max_json_bytes: int = int(os.getenv("MAX_JSON_BYTES", "1048576"))
    max_image_bytes: int = int(os.getenv("MAX_IMAGE_BYTES", "26214400"))
    operator_full_name: str = os.getenv("OPERATOR_FULL_NAME", "[ФИО индивидуального предпринимателя]")
    operator_inn: str = os.getenv("OPERATOR_INN", "[ИНН]")
    operator_ogrnip: str = os.getenv("OPERATOR_OGRNIP", "[ОГРНИП]")
    operator_address: str = os.getenv("OPERATOR_ADDRESS", "[адрес оператора]")
    operator_email: str = os.getenv("OPERATOR_EMAIL", "[электронная почта]")
    operator_phone: str = os.getenv("OPERATOR_PHONE", "[телефон]")
    site_url: str = os.getenv("SITE_URL", "[адрес приложения]")
    app_secret: str = os.getenv("APP_SECRET", "development-secret-change-before-production")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    max_client_id: str = os.getenv("MAX_CLIENT_ID", "")
    vk_client_id: str = os.getenv("VK_CLIENT_ID", "")

    @property
    def email_auth_ready(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "calendar.sqlite3"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


settings = Settings()
