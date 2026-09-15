from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from .config import Settings
from .database import Database, utc_now


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CODE_TTL_MINUTES = 10
SESSION_TTL_DAYS = 30


class AuthService:
    def __init__(self, database: Database, settings: Settings):
        self.db = database
        self.settings = settings

    def providers(self) -> dict[str, bool]:
        return {
            "email": self.settings.email_auth_ready or self.settings.environment == "development",
            "telegram": bool(self.settings.telegram_bot_token),
            "max": bool(self.settings.max_client_id),
            "vk": bool(self.settings.vk_client_id),
        }

    @staticmethod
    def normalize_email(value: object) -> str:
        email = str(value or "").strip().lower()
        if len(email) > 254 or not EMAIL_RE.fullmatch(email):
            raise ValueError("Проверьте адрес электронной почты")
        return email

    def _digest(self, value: str) -> str:
        return hmac.new(self.settings.app_secret.encode(), value.encode(), hashlib.sha256).hexdigest()

    def request_email_code(self, value: object) -> dict[str, object]:
        email = self.normalize_email(value)
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
        self.db.save_email_code(email, self._digest(email + ":" + code), expires.isoformat())
        if self.settings.email_auth_ready:
            self._send_code(email, code)
            return {"ok": True, "delivery": "email", "expires_in": CODE_TTL_MINUTES * 60}
        if self.settings.environment == "development":
            return {"ok": True, "delivery": "development", "expires_in": CODE_TTL_MINUTES * 60, "development_code": code}
        raise ValueError("Вход по почте временно не настроен")

    def _send_code(self, recipient: str, code: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Код входа — Нарисуй сам"
        message["From"] = self.settings.smtp_from
        message["To"] = recipient
        message.set_content(f"Код входа: {code}\n\nКод действует {CODE_TTL_MINUTES} минут.")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, context=context, timeout=15) as smtp:
            if self.settings.smtp_user:
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(message)

    def verify_email_code(self, value: object, raw_code: object) -> dict[str, object]:
        email = self.normalize_email(value)
        code = str(raw_code or "").strip()
        if not re.fullmatch(r"\d{6}", code):
            raise ValueError("Введите шестизначный код")
        saved = self.db.get_email_code(email)
        if not saved or saved["expires_at"] <= utc_now() or saved["attempts"] >= 5:
            raise ValueError("Код истёк. Запросите новый")
        if not hmac.compare_digest(saved["code_hash"], self._digest(email + ":" + code)):
            self.db.increment_email_attempts(email)
            raise ValueError("Неверный код")
        self.db.consume_email_code(email)
        user = self.db.get_or_create_user(email)
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
        self.db.save_session(self._digest(token), user["id"], expires.isoformat())
        return {"ok": True, "token": token, "expires_at": expires.isoformat(), "user": user}

    def session_user(self, authorization: str) -> dict[str, object] | None:
        if not authorization.startswith("Bearer "):
            return None
        token = authorization[7:].strip()
        return self.db.get_session_user(self._digest(token), utc_now()) if token else None

    def logout(self, authorization: str) -> None:
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
            if token:
                self.db.delete_session(self._digest(token))
