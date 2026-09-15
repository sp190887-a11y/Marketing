import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, jsonify, request

from .index import (
    ADMIN_SESSION_HOURS,
    OTP_PEPPER,
    add_audit,
    admin_from_session,
    create_session,
    db,
    password_hash,
    request_ip,
    token_hash,
    user_agent,
)

mfa_bp = Blueprint("admin_mfa", __name__)
MFA_CHALLENGE_MINUTES = 10
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def fernet():
    key = os.environ.get("APP_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("mfa_encryption_not_configured")
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("mfa_encryption_key_invalid") from exc


def recovery_pepper():
    return os.environ.get("MFA_RECOVERY_PEPPER", OTP_PEPPER).encode("utf-8")


def recovery_hash(code):
    normalized = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
    return hmac.new(recovery_pepper(), normalized.encode("ascii"), hashlib.sha256).hexdigest()


def make_recovery_code():
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def decrypt_secret(value):
    try:
        return fernet().decrypt(str(value).encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise RuntimeError("mfa_secret_unreadable") from exc


def encrypt_secret(value):
    return fernet().encrypt(str(value).encode("ascii")).decode("ascii")


def challenge_admin(cur, token, lock=True):
    sql = """
        SELECT c.id AS challenge_id,c.admin_id,a.login,a.display_name,a.role,
               a.mfa_pending_secret_encrypted,a.is_active
          FROM admin_auth_challenges c
          JOIN admin_users a ON a.id=c.admin_id
         WHERE c.token_hash=%s AND c.purpose='mfa_setup'
           AND c.used_at IS NULL AND c.expires_at>now()
    """
    if lock:
        sql += " FOR UPDATE OF c,a"
    cur.execute(sql, (token_hash(token),))
    row = cur.fetchone()
    return row if row and row["is_active"] else None


def verify_second_factor(cur, admin, code):
    supplied = str(code or "").strip()
    if re.fullmatch(r"\d{6}", supplied):
        if not admin.get("mfa_secret_encrypted"):
            return False, None
        secret = decrypt_secret(admin["mfa_secret_encrypted"])
        ok = pyotp.TOTP(secret).verify(supplied, valid_window=1)
        return bool(ok), "totp" if ok else None

    if supplied:
        cur.execute(
            """
            SELECT id FROM admin_mfa_recovery_codes
             WHERE admin_id=%s AND code_hash=%s AND used_at IS NULL
             ORDER BY created_at LIMIT 1 FOR UPDATE
            """,
            (admin["id"], recovery_hash(supplied)),
        )
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE admin_mfa_recovery_codes SET used_at=now() WHERE id=%s", (row["id"],))
            return True, "recovery"
    return False, None


def register_failure(cur, admin):
    attempts = int(admin.get("failed_login_attempts") or 0) + 1
    lock_until = datetime.now(timezone.utc) + timedelta(minutes=15) if attempts >= 5 else None
    cur.execute(
        "UPDATE admin_users SET failed_login_attempts=%s,locked_until=%s WHERE id=%s",
        (0 if lock_until else attempts, lock_until, admin["id"]),
    )
    return max(0, 5 - attempts), lock_until


@mfa_bp.post("/api/admin/auth/login")
def secure_admin_login():
    data = request.get_json(silent=True) or {}
    login = str(data.get("login") or "").strip().lower()
    password = str(data.get("password") or "")
    code = str(data.get("code") or "").strip()

    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT *, (locked_until IS NOT NULL AND locked_until>now()) AS locked
              FROM admin_users
             WHERE login=%s AND is_active=true
             FOR UPDATE
            """,
            (login,),
        )
        admin = cur.fetchone()
        if not admin:
            return jsonify(error="invalid_credentials"), 401
        if admin["locked"]:
            return jsonify(error="admin_temporarily_locked"), 423

        try:
            _, candidate = password_hash(password, admin["password_salt"])
        except ValueError:
            candidate = ""
        if not candidate or not secrets.compare_digest(candidate, admin["password_hash"]):
            attempts_left, _ = register_failure(cur, admin)
            add_audit(cur, "anonymous", None, "admin_login_failed", "admin", admin["id"], {"login": login, "stage": "password"})
            con.commit()
            return jsonify(error="invalid_credentials", attempts_left=attempts_left), 401

        if not admin.get("mfa_secret_encrypted"):
            setup_token = secrets.token_urlsafe(40)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=MFA_CHALLENGE_MINUTES)
            cur.execute(
                "UPDATE admin_auth_challenges SET used_at=now() WHERE admin_id=%s AND purpose='mfa_setup' AND used_at IS NULL",
                (admin["id"],),
            )
            cur.execute(
                """
                INSERT INTO admin_auth_challenges(admin_id,purpose,token_hash,expires_at,ip_address,user_agent)
                VALUES (%s,'mfa_setup',%s,%s,%s,%s)
                """,
                (admin["id"], token_hash(setup_token), expires_at, request_ip(), user_agent()),
            )
            add_audit(cur, "admin", admin["id"], "mfa_setup_required", "admin", admin["id"])
            con.commit()
            return jsonify(
                error="mfa_setup_required",
                setup_token=setup_token,
                expires_in=MFA_CHALLENGE_MINUTES * 60,
            ), 428

        if not code:
            return jsonify(error="mfa_code_required"), 401

        ok, method = verify_second_factor(cur, admin, code)
        if not ok:
            attempts_left, _ = register_failure(cur, admin)
            add_audit(cur, "anonymous", None, "admin_login_failed", "admin", admin["id"], {"login": login, "stage": "mfa"})
            con.commit()
            return jsonify(error="invalid_mfa_code", attempts_left=attempts_left), 401

        cur.execute(
            "UPDATE admin_users SET failed_login_attempts=0,locked_until=NULL,last_login_at=now() WHERE id=%s",
            (admin["id"],),
        )
        token, _ = create_session(cur, "admin", admin["id"], hours=ADMIN_SESSION_HOURS)
        add_audit(cur, "admin", admin["id"], "admin_login", "admin", admin["id"], {"mfa_method": method})
        con.commit()

    return jsonify(
        ok=True,
        token=token,
        admin={
            "id": admin["id"],
            "login": admin["login"],
            "display_name": admin["display_name"],
            "role": admin["role"],
        },
        mfa_method=method,
    )


@mfa_bp.post("/api/admin/mfa/setup/start")
def mfa_setup_start():
    data = request.get_json(silent=True) or {}
    setup_token = str(data.get("setup_token") or "")
    with db() as con, con.cursor() as cur:
        admin = challenge_admin(cur, setup_token)
        if not admin:
            return jsonify(error="setup_token_invalid_or_expired"), 401
        secret = pyotp.random_base32()
        encrypted = encrypt_secret(secret)
        cur.execute(
            "UPDATE admin_users SET mfa_pending_secret_encrypted=%s WHERE id=%s",
            (encrypted, admin["admin_id"]),
        )
        issuer = "АМ Клуб"
        uri = pyotp.TOTP(secret).provisioning_uri(name=admin["login"], issuer_name=issuer)
        add_audit(cur, "admin", admin["admin_id"], "mfa_setup_started", "admin", admin["admin_id"])
        con.commit()
    return jsonify(
        ok=True,
        secret=secret,
        otpauth_uri=uri,
        issuer=issuer,
        account=admin["login"],
    )


@mfa_bp.post("/api/admin/mfa/setup/confirm")
def mfa_setup_confirm():
    data = request.get_json(silent=True) or {}
    setup_token = str(data.get("setup_token") or "")
    code = str(data.get("code") or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return jsonify(error="invalid_mfa_code"), 400

    with db() as con, con.cursor() as cur:
        admin = challenge_admin(cur, setup_token)
        if not admin or not admin.get("mfa_pending_secret_encrypted"):
            return jsonify(error="mfa_setup_not_started"), 401
        secret = decrypt_secret(admin["mfa_pending_secret_encrypted"])
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            return jsonify(error="invalid_mfa_code"), 401

        cur.execute(
            """
            UPDATE admin_users
               SET mfa_secret_encrypted=mfa_pending_secret_encrypted,
                   mfa_pending_secret_encrypted=NULL,
                   mfa_required=true,
                   mfa_enabled_at=now(),
                   failed_login_attempts=0,
                   locked_until=NULL
             WHERE id=%s
            """,
            (admin["admin_id"],),
        )
        cur.execute("UPDATE admin_auth_challenges SET used_at=now() WHERE challenge_id IS NULL") if False else None
        cur.execute("UPDATE admin_auth_challenges SET used_at=now() WHERE id=%s", (admin["challenge_id"],))
        cur.execute("DELETE FROM admin_mfa_recovery_codes WHERE admin_id=%s", (admin["admin_id"],))
        recovery_codes = [make_recovery_code() for _ in range(8)]
        for recovery_code in recovery_codes:
            cur.execute(
                "INSERT INTO admin_mfa_recovery_codes(admin_id,code_hash) VALUES (%s,%s)",
                (admin["admin_id"], recovery_hash(recovery_code)),
            )
        token, _ = create_session(cur, "admin", admin["admin_id"], hours=ADMIN_SESSION_HOURS)
        add_audit(cur, "admin", admin["admin_id"], "mfa_enabled", "admin", admin["admin_id"], {"recovery_codes_created": len(recovery_codes)})
        con.commit()

    return jsonify(
        ok=True,
        token=token,
        recovery_codes=recovery_codes,
        message="Save recovery codes now; they are shown only once.",
    )


@mfa_bp.get("/api/admin/mfa/status")
def mfa_status():
    ctx = admin_from_session()
    if not ctx:
        return jsonify(error="unauthorized"), 401
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT mfa_required,mfa_enabled_at,
                   (SELECT count(*) FROM admin_mfa_recovery_codes r WHERE r.admin_id=a.id AND r.used_at IS NULL) AS recovery_codes_left
              FROM admin_users a WHERE id=%s
            """,
            (ctx["admin"]["id"],),
        )
        row = cur.fetchone()
    return jsonify(mfa=row)
