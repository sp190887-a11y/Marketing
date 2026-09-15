from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import traceback
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, unquote

from .auth import AuthService
from .config import settings
from .database import Database, utc_now
from .legal_documents import LEGAL_VERSION, get_documents


db = Database(settings.database_path)
db.initialize()
auth = AuthService(db, settings)
settings.uploads_dir.mkdir(parents=True, exist_ok=True)

ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,80}$")
PAGE_RE = re.compile(r"^/api/projects/([A-Za-z0-9_-]{6,80})/pages/(\d{1,2})/(source|processed)$")


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def response(start_response: Callable, status: str, body: bytes, content_type: str, extra: list[tuple[str, str]] | None = None) -> list[bytes]:
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ("Permissions-Policy", "camera=(self), microphone=(), geolocation=()"),
        ("Cache-Control", "no-store" if content_type.startswith("application/json") else "public, max-age=300"),
    ]
    if extra:
        headers.extend(extra)
    start_response(status, headers)
    return [body]


def json_response(start_response: Callable, status: str, payload: Any) -> list[bytes]:
    return response(start_response, status, json_bytes(payload), "application/json; charset=utf-8")


def owner_key(environ: dict[str, Any]) -> str:
    user = auth.session_user(environ.get("HTTP_AUTHORIZATION") or "")
    if user:
        return "user_" + str(user["id"])
    value = (environ.get("HTTP_X_DEVICE_ID") or "").strip()
    if not ID_RE.fullmatch(value):
        raise ValueError("Требуется корректный заголовок X-Device-Id")
    return value


def read_body(environ: dict[str, Any], limit: int) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError as exc:
        raise ValueError("Некорректный Content-Length") from exc
    if length < 0 or length > limit:
        raise OverflowError("Размер запроса превышает допустимый")
    body = environ["wsgi.input"].read(length)
    if len(body) != length:
        raise ValueError("Запрос получен не полностью")
    return body


def read_json(environ: dict[str, Any]) -> dict[str, Any]:
    body = read_body(environ, settings.max_json_bytes)
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Требуется корректный JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON должен быть объектом")
    return value


def clean_text(value: Any, name: str, maximum: int, minimum: int = 0) -> str:
    text = str(value or "").strip()
    if len(text) < minimum or len(text) > maximum:
        raise ValueError(f"Поле {name} должно содержать от {minimum} до {maximum} символов")
    return text


def file_path(owner: str, project_id: str, page: int, kind: str) -> Path:
    folder = settings.uploads_dir / owner / project_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{page:02d}-{kind}.jpg"


def serve_static(path: str, start_response: Callable) -> list[bytes]:
    requested = "index.html" if path in ("", "/") else unquote(path.lstrip("/"))
    candidate = (settings.frontend_dir / requested).resolve()
    try:
        candidate.relative_to(settings.frontend_dir)
    except ValueError:
        return json_response(start_response, "403 Forbidden", {"error": "Доступ запрещён"})
    if candidate.is_dir():
        candidate = candidate / "index.html"
    if not candidate.is_file():
        return json_response(start_response, "404 Not Found", {"error": "Файл не найден"})
    mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    body = candidate.read_bytes()
    return response(start_response, "200 OK", body, f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)


def api(environ: dict[str, Any], start_response: Callable, method: str, path: str) -> list[bytes]:
    if method == "GET" and path == "/api/health":
        return json_response(start_response, "200 OK", {"ok": True, "app": settings.app_name, "version": settings.app_version, "legal_version": LEGAL_VERSION})

    if method == "GET" and path == "/api/config":
        return json_response(start_response, "200 OK", {
            "app": settings.app_name,
            "version": settings.app_version,
            "guest_mode": True,
            "pdf_formats": ["A4", "A3"],
            "auth": auth.providers(),
            "operator_ready": not settings.operator_inn.startswith("["),
        })

    if method == "GET" and path == "/api/auth/providers":
        return json_response(start_response, "200 OK", {"providers": auth.providers()})

    if method == "POST" and path == "/api/auth/email/request":
        data = read_json(environ)
        return json_response(start_response, "200 OK", auth.request_email_code(data.get("email")))

    if method == "POST" and path == "/api/auth/email/verify":
        data = read_json(environ)
        return json_response(start_response, "200 OK", auth.verify_email_code(data.get("email"), data.get("code")))

    if method == "GET" and path == "/api/auth/session":
        user = auth.session_user(environ.get("HTTP_AUTHORIZATION") or "")
        if not user:
            return json_response(start_response, "401 Unauthorized", {"error": "Требуется вход"})
        return json_response(start_response, "200 OK", {"ok": True, "user": user})

    if method == "POST" and path == "/api/auth/logout":
        auth.logout(environ.get("HTTP_AUTHORIZATION") or "")
        return json_response(start_response, "200 OK", {"ok": True})

    if method == "GET" and path == "/api/legal":
        docs = get_documents(settings)
        return json_response(start_response, "200 OK", {"version": LEGAL_VERSION, "documents": [{"slug": slug, **data} for slug, data in docs.items()]})

    if method == "GET" and path.startswith("/api/legal/"):
        slug = path.removeprefix("/api/legal/")
        document = get_documents(settings).get(slug)
        if not document:
            return json_response(start_response, "404 Not Found", {"error": "Документ не найден"})
        return json_response(start_response, "200 OK", {"slug": slug, **document})

    if method == "POST" and path == "/api/support":
        owner = owner_key(environ)
        data = read_json(environ)
        message = clean_text(data.get("message"), "message", 10000, 5)
        item = {
            "id": "SUP-" + secrets.token_hex(6).upper(),
            "owner_key": owner,
            "project_id": clean_text(data.get("project_id"), "project_id", 80) or None,
            "page_number": data.get("page_number") if isinstance(data.get("page_number"), int) else None,
            "step": clean_text(data.get("step"), "step", 80) or None,
            "contact": clean_text(data.get("contact"), "contact", 200) or None,
            "message": message,
            "context": data.get("context") if isinstance(data.get("context"), dict) else {},
            "created_at": utc_now(),
        }
        db.create_support_request(item)
        return json_response(start_response, "201 Created", {"ok": True, "id": item["id"], "status": "new"})

    if method == "POST" and path == "/api/consents":
        owner = owner_key(environ)
        data = read_json(environ)
        slug = clean_text(data.get("document_slug"), "document_slug", 80, 1)
        if slug not in get_documents(settings):
            raise ValueError("Неизвестный документ")
        accepted = data.get("accepted")
        if not isinstance(accepted, bool):
            raise ValueError("Поле accepted должно быть логическим")
        source = clean_text(data.get("source"), "source", 80) or "web"
        db.save_consent(owner, slug, LEGAL_VERSION, accepted, source)
        return json_response(start_response, "201 Created", {"ok": True, "document_slug": slug, "version": LEGAL_VERSION, "accepted": accepted})

    if path == "/api/projects" and method == "GET":
        return json_response(start_response, "200 OK", {"projects": db.list_projects(owner_key(environ))})

    if path == "/api/projects" and method == "POST":
        owner = owner_key(environ)
        data = read_json(environ)
        project_id = clean_text(data.get("id"), "id", 80, 6)
        if not ID_RE.fullmatch(project_id):
            raise ValueError("Некорректный идентификатор проекта")
        title = clean_text(data.get("title"), "title", 120, 1)
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Поле payload должно быть объектом")
        saved = db.save_project(project_id, owner, title, payload)
        return json_response(start_response, "200 OK", {"ok": True, "project": saved})

    if path.startswith("/api/projects/") and "/pages/" not in path and method == "GET":
        project_id = path.removeprefix("/api/projects/")
        if not ID_RE.fullmatch(project_id):
            raise ValueError("Некорректный идентификатор проекта")
        project = db.get_project(project_id, owner_key(environ))
        if not project:
            return json_response(start_response, "404 Not Found", {"error": "Проект не найден"})
        return json_response(start_response, "200 OK", {"project": project})

    match = PAGE_RE.fullmatch(path)
    if match:
        project_id, page_raw, kind = match.groups()
        page = int(page_raw)
        if page < 0 or page > 12:
            raise ValueError("Номер страницы должен быть от 0 до 12")
        owner = owner_key(environ)
        target = file_path(owner, project_id, page, kind)
        if method == "PUT":
            content_type = environ.get("CONTENT_TYPE", "")
            if content_type != "image/jpeg":
                raise ValueError("Для страниц используется формат JPEG")
            body = read_body(environ, settings.max_image_bytes)
            if len(body) < 100:
                raise ValueError("Файл изображения слишком мал")
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(body)
            os.replace(temporary, target)
            return json_response(start_response, "201 Created", {"ok": True, "page": page, "kind": kind, "bytes": len(body)})
        if method == "GET":
            if not target.is_file():
                return json_response(start_response, "404 Not Found", {"error": "Изображение не найдено"})
            body = target.read_bytes()
            return response(start_response, "200 OK", body, "image/jpeg", [("Cache-Control", "private, max-age=300")])

    return json_response(start_response, "404 Not Found", {"error": "Маршрут не найден"})


def application(environ: dict[str, Any], start_response: Callable) -> Iterable[bytes]:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    try:
        if path.startswith("/api/"):
            return api(environ, start_response, method, path)
        if method not in ("GET", "HEAD"):
            return json_response(start_response, "405 Method Not Allowed", {"error": "Метод не поддерживается"})
        result = serve_static(path, start_response)
        return [] if method == "HEAD" else result
    except OverflowError as exc:
        return json_response(start_response, "413 Payload Too Large", {"error": str(exc)})
    except ValueError as exc:
        return json_response(start_response, "400 Bad Request", {"error": str(exc)})
    except Exception:
        incident = "ERR-" + secrets.token_hex(6).upper()
        traceback.print_exc()
        return json_response(start_response, "500 Internal Server Error", {"error": "Внутренняя ошибка", "incident_id": incident})
