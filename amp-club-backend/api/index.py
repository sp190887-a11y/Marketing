import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone

import psycopg
from flask import Flask, jsonify, request
from psycopg import errors
from psycopg.rows import dict_row

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SMS_MODE = os.environ.get("SMS_MODE", "test").strip().lower()
OTP_PEPPER = os.environ.get("OTP_PEPPER", "amp-club-test-pepper")
ADMIN_BOOTSTRAP_TOKEN = os.environ.get("ADMIN_BOOTSTRAP_TOKEN", "")
ALLOWED_ORIGINS = {
    x.strip()
    for x in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://sp190887-a11y.github.io,https://club.amplituda-nn.ru",
    ).split(",")
    if x.strip()
}
OTP_TTL_MINUTES = int(os.environ.get("OTP_TTL_MINUTES", "5"))
OTP_RESEND_SECONDS = int(os.environ.get("OTP_RESEND_SECONDS", "60"))
CLIENT_SESSION_DAYS = int(os.environ.get("CLIENT_SESSION_DAYS", "90"))
ADMIN_SESSION_HOURS = int(os.environ.get("ADMIN_SESSION_HOURS", "12"))

CLIENT_FIELDS = """
id,phone,name,birth_date,gender,discount_percent,balance_am,ruble_remainder,
crm_number,telegram_linked,max_linked,is_active,created_at,updated_at
""".replace("\n", "")

ROLE_PERMISSIONS = {
    "owner": {"customer_read", "ledger_adjust", "audit_read", "support_read"},
    "manager": {"customer_read", "ledger_adjust", "support_read"},
    "operator": {"customer_read", "ledger_adjust", "support_read"},
    "auditor": {"customer_read", "audit_read"},
}


def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def norm_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if not re.fullmatch(r"\d{10}", digits):
        raise ValueError("invalid_phone")
    return digits


def encode_secret(secret, salt_b64=None, rounds=310_000):
    salt = base64.urlsafe_b64decode(salt_b64.encode()) if salt_b64 else secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac("sha256", str(secret).encode("utf-8"), salt, rounds)
    return (
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(value).decode("ascii"),
    )


def pin_hash(pin, salt_b64=None):
    if not re.fullmatch(r"\d{4}", str(pin or "")):
        raise ValueError("invalid_pin")
    return encode_secret(str(pin), salt_b64=salt_b64)


def password_hash(password, salt_b64=None):
    value = str(password or "")
    if len(value) < 10:
        raise ValueError("weak_password")
    return encode_secret(value, salt_b64=salt_b64)


def token_hash(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def otp_hash(phone, purpose, code):
    msg = f"{phone}:{purpose}:{code}".encode("utf-8")
    return hmac.new(OTP_PEPPER.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def request_ip():
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    candidate = forwarded or request.remote_addr or None
    if not candidate:
        return None
    if len(candidate) > 64 or not re.fullmatch(r"[0-9a-fA-F:.]+", candidate):
        return None
    return candidate


def user_agent():
    return str(request.headers.get("User-Agent", ""))[:1000]


def source_name():
    value = str(request.headers.get("X-AMP-Client", "web")).strip().lower()
    return value if value in {"web", "pwa", "admin", "telegram", "max", "vk"} else "web"


def json_body():
    return request.get_json(silent=True) or {}


def bearer():
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else ""


def create_session(cur, subject_type, subject_id, *, days=None, hours=None):
    token = secrets.token_urlsafe(40)
    now = datetime.now(timezone.utc)
    if hours is not None:
        expires_at = now + timedelta(hours=hours)
    else:
        expires_at = now + timedelta(days=days or CLIENT_SESSION_DAYS)
    cur.execute(
        """
        INSERT INTO auth_sessions(subject_type,subject_id,token_hash,expires_at,ip_address,user_agent,last_seen_at)
        VALUES (%s,%s,%s,%s,%s,%s,now()) RETURNING id
        """,
        (subject_type, subject_id, token_hash(token), expires_at, request_ip(), user_agent()),
    )
    row = cur.fetchone()
    return token, row["id"]


def session_subject(subject_type):
    token = bearer()
    if not token:
        return None
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT id,subject_id FROM auth_sessions
             WHERE subject_type=%s AND token_hash=%s
               AND revoked_at IS NULL AND expires_at>now()
             ORDER BY created_at DESC LIMIT 1
            """,
            (subject_type, token_hash(token)),
        )
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("UPDATE auth_sessions SET last_seen_at=now() WHERE id=%s", (row["id"],))
        con.commit()
        return {"id": str(row["subject_id"]), "session_id": str(row["id"])}


def current_documents(cur):
    cur.execute(
        "SELECT doc_type,version,title,public_path FROM document_versions WHERE is_current=true ORDER BY doc_type"
    )
    return {row["doc_type"]: row for row in cur.fetchall()}


def current_doc_version(cur, doc_type):
    cur.execute(
        "SELECT version FROM document_versions WHERE doc_type=%s AND is_current=true LIMIT 1",
        (doc_type,),
    )
    row = cur.fetchone()
    return row["version"] if row else "unknown"


def add_audit(cur, actor_type, actor_id, action, target_type=None, target_id=None, details=None):
    cur.execute(
        """
        INSERT INTO audit_log(actor_type,actor_id,action,target_type,target_id,details)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb)
        """,
        (
            actor_type,
            actor_id,
            action,
            target_type,
            str(target_id) if target_id is not None else None,
            json.dumps(details or {}, ensure_ascii=False),
        ),
    )


def add_consent(cur, customer_id, consent_type, action, version, session_id=None, metadata=None):
    cur.execute(
        """
        INSERT INTO consent_ledger(
            customer_id,consent_type,action,document_version,source,ip_address,user_agent,session_id,metadata
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        RETURNING id,created_at
        """,
        (
            customer_id,
            consent_type,
            action,
            version,
            source_name(),
            request_ip(),
            user_agent(),
            session_id,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    return cur.fetchone()


def validate_registration_consents(data):
    consents = data.get("consents") or {}
    if consents.get("age_18") is not True:
        raise ValueError("age_18_required")
    if consents.get("club_rules") is not True:
        raise ValueError("club_rules_required")
    if consents.get("personal_data") is not True:
        raise ValueError("personal_data_consent_required")
    return {
        "age_18": True,
        "club_rules": True,
        "personal_data": True,
        "marketing": consents.get("marketing") is True,
    }


def is_adult_birth_date(value):
    if not value:
        return True
    try:
        born = date.fromisoformat(str(value))
    except ValueError:
        raise ValueError("invalid_birth_date")
    today = datetime.now(timezone.utc).date()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return years >= 18


def create_verification(cur, phone, purpose, channel, metadata):
    cur.execute(
        """
        SELECT EXTRACT(EPOCH FROM (now()-created_at))::int AS age_seconds
          FROM verification_codes
         WHERE phone=%s AND purpose=%s
         ORDER BY created_at DESC LIMIT 1
        """,
        (phone, purpose),
    )
    recent = cur.fetchone()
    if recent and recent["age_seconds"] < OTP_RESEND_SECONDS:
        return None, OTP_RESEND_SECONDS - recent["age_seconds"]

    if SMS_MODE == "test":
        code = "1111" if purpose == "register" else "2222"
        real_channel = "test"
    else:
        code = f"{secrets.randbelow(1_000_000):06d}"
        real_channel = channel
        # Реальный SMS/Telegram/MAX адаптер подключается отдельно. До этого production mode не включаем.
        if real_channel == "sms":
            raise RuntimeError("sms_provider_not_configured")
        raise RuntimeError("recovery_channel_not_configured")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
    cur.execute(
        """
        INSERT INTO verification_codes(
            phone,purpose,channel,code_hash,expires_at,metadata,request_ip,user_agent,sent_at
        ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,now()) RETURNING id
        """,
        (
            phone,
            purpose,
            real_channel,
            otp_hash(phone, purpose, code),
            expires_at,
            json.dumps(metadata or {}, ensure_ascii=False),
            request_ip(),
            user_agent(),
        ),
    )
    return {"code": code, "channel": real_channel, "expires_at": expires_at}, None


def verify_code(cur, phone, purpose, code):
    cur.execute(
        """
        SELECT * FROM verification_codes
         WHERE phone=%s AND purpose=%s AND used_at IS NULL AND expires_at>now()
         ORDER BY created_at DESC LIMIT 1 FOR UPDATE
        """,
        (phone, purpose),
    )
    row = cur.fetchone()
    if not row:
        return None, "code_not_found_or_expired"
    if row["attempts"] >= 5:
        return None, "code_locked"
    expected = otp_hash(phone, purpose, str(code or ""))
    if not secrets.compare_digest(expected, row["code_hash"]):
        cur.execute("UPDATE verification_codes SET attempts=attempts+1 WHERE id=%s", (row["id"],))
        return None, "wrong_code"
    cur.execute("UPDATE verification_codes SET used_at=now() WHERE id=%s", (row["id"],))
    return row, None


def admin_from_session(permission=None):
    subject = session_subject("admin")
    if not subject:
        return None
    with db() as con, con.cursor() as cur:
        cur.execute(
            "SELECT id,login,display_name,role,permissions,is_active FROM admin_users WHERE id=%s",
            (subject["id"],),
        )
        admin = cur.fetchone()
    if not admin or not admin["is_active"]:
        return None
    allowed = set(ROLE_PERMISSIONS.get(admin["role"], set()))
    custom = admin.get("permissions") or {}
    allowed.update(k for k, v in custom.items() if v is True)
    allowed.difference_update(k for k, v in custom.items() if v is False)
    if permission and permission not in allowed:
        return {"forbidden": True, "admin": admin, "session": subject}
    return {"forbidden": False, "admin": admin, "session": subject, "permissions": sorted(allowed)}


@app.after_request
def security_headers(resp):
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-AMP-Client, X-Bootstrap-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,PUT,OPTIONS"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.errorhandler(RuntimeError)
def runtime_error(exc):
    known = {
        "sms_provider_not_configured": 503,
        "recovery_channel_not_configured": 503,
        "DATABASE_URL is not configured": 503,
    }
    code = known.get(str(exc), 500)
    return jsonify(error=str(exc) if code != 500 else "server_error"), code


@app.route("/api/<path:_>", methods=["OPTIONS"])
@app.route("/api", methods=["OPTIONS"])
def options(_=None):
    return ("", 204)


@app.get("/api/health")
def health():
    if not DATABASE_URL:
        return jsonify(ok=False, error="database_not_configured"), 503
    try:
        with db() as con, con.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM customers")
            customers = cur.fetchone()["n"]
            cur.execute("SELECT count(*) AS n FROM am_ledger")
            ledger = cur.fetchone()["n"]
        return jsonify(ok=True, service="amp-club-python", storage="postgres", customers=customers, ledger=ledger)
    except Exception:
        return jsonify(ok=False, error="db_unavailable"), 500


@app.get("/api/legal/current")
def legal_current():
    with db() as con, con.cursor() as cur:
        docs = current_documents(cur)
    return jsonify(documents=docs, minimum_age=18, marketing_optional=True)


@app.post("/api/client/register/start")
def register_start():
    data = json_body()
    try:
        phone = norm_phone(data.get("phone"))
        consents = validate_registration_consents(data)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT id,pin_hash FROM customers WHERE phone=%s AND is_active=true", (phone,))
        existing = cur.fetchone()
        if existing and existing["pin_hash"]:
            return jsonify(error="already_registered"), 409
        docs = current_documents(cur)
        required = {"personal_data", "club_rules", "marketing"}
        if not required.issubset(docs):
            return jsonify(error="legal_documents_not_configured"), 503
        metadata = {
            "consents": consents,
            "versions": {
                "personal_data": docs["personal_data"]["version"],
                "club_rules": docs["club_rules"]["version"],
                "marketing": docs["marketing"]["version"],
                "privacy": docs.get("privacy", {}).get("version"),
            },
        }
        result, retry_after = create_verification(cur, phone, "register", "sms", metadata)
        if retry_after is not None:
            con.commit()
            return jsonify(error="too_many_requests", retry_after=retry_after), 429
        add_audit(cur, "anonymous", None, "registration_code_created", "phone", phone, {"channel": result["channel"]})
        con.commit()

    payload = {
        "ok": True,
        "phone": phone,
        "channel": result["channel"],
        "expires_in": OTP_TTL_MINUTES * 60,
    }
    if SMS_MODE == "test":
        payload["test_code"] = result["code"]
    return jsonify(payload)


@app.post("/api/client/register/verify")
def register_verify():
    data = json_body()
    try:
        phone = norm_phone(data.get("phone"))
        salt, hashed_pin = pin_hash(data.get("pin"))
        if not is_adult_birth_date(data.get("birth_date")):
            return jsonify(error="minimum_age_18"), 400
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    name = str(data.get("name") or "").strip()[:300]
    gender = data.get("gender") if data.get("gender") in {"male", "female", None, ""} else "invalid"
    if gender == "invalid":
        return jsonify(error="invalid_gender"), 400
    gender = gender or None

    with db() as con, con.cursor() as cur:
        code_row, error = verify_code(cur, phone, "register", data.get("code"))
        if error:
            con.commit()
            return jsonify(error=error), 401
        meta = code_row.get("metadata") or {}
        consents = meta.get("consents") or {}
        if not (consents.get("age_18") and consents.get("club_rules") and consents.get("personal_data")):
            return jsonify(error="registration_consent_evidence_missing"), 409

        cur.execute("SELECT id,pin_hash FROM customers WHERE phone=%s FOR UPDATE", (phone,))
        customer = cur.fetchone()
        if customer and customer["pin_hash"]:
            return jsonify(error="already_registered"), 409

        if customer:
            cur.execute(
                """
                UPDATE customers
                   SET name=CASE WHEN %s<>'' THEN %s ELSE name END,
                       birth_date=COALESCE(%s,birth_date), gender=COALESCE(%s,gender),
                       pin_salt=%s,pin_hash=%s,failed_pin_attempts=0,pin_locked_until=NULL,updated_at=now()
                 WHERE id=%s RETURNING """ + CLIENT_FIELDS,
                (name, name, data.get("birth_date") or None, gender, salt, hashed_pin, customer["id"]),
            )
        else:
            cur.execute(
                """
                INSERT INTO customers(phone,name,birth_date,gender,pin_salt,pin_hash)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING """ + CLIENT_FIELDS,
                (phone, name, data.get("birth_date") or None, gender, salt, hashed_pin),
            )
        customer = cur.fetchone()
        token, session_id = create_session(cur, "client", customer["id"])
        versions = meta.get("versions") or {}
        add_consent(cur, customer["id"], "age_18", "grant", "18+", session_id, {"confirmed": True})
        add_consent(cur, customer["id"], "club_rules", "grant", versions.get("club_rules", "unknown"), session_id)
        add_consent(cur, customer["id"], "personal_data", "grant", versions.get("personal_data", "unknown"), session_id)
        add_consent(
            cur,
            customer["id"],
            "marketing",
            "grant" if consents.get("marketing") else "decline",
            versions.get("marketing", "unknown"),
            session_id,
        )
        add_audit(cur, "client", customer["id"], "registered", "customer", customer["id"], {"marketing": bool(consents.get("marketing"))})
        con.commit()
    return jsonify(ok=True, token=token, customer=customer)


@app.post("/api/client/login")
def client_login():
    data = json_body()
    try:
        phone = norm_phone(data.get("phone"))
        pin = str(data.get("pin") or "")
        pin_hash(pin)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    with db() as con, con.cursor() as cur:
        cur.execute(
            "SELECT *, (pin_locked_until IS NOT NULL AND pin_locked_until>now()) AS locked FROM customers WHERE phone=%s AND is_active=true FOR UPDATE",
            (phone,),
        )
        customer = cur.fetchone()
        if not customer or not customer.get("pin_hash"):
            return jsonify(error="not_found"), 404
        if customer["locked"]:
            return jsonify(error="pin_temporarily_locked"), 423
        _, candidate = pin_hash(pin, customer["pin_salt"])
        if not secrets.compare_digest(candidate, customer["pin_hash"]):
            attempts = int(customer["failed_pin_attempts"] or 0) + 1
            lock_until = datetime.now(timezone.utc) + timedelta(minutes=15) if attempts >= 5 else None
            cur.execute(
                "UPDATE customers SET failed_pin_attempts=%s,pin_locked_until=%s WHERE id=%s",
                (0 if lock_until else attempts, lock_until, customer["id"]),
            )
            add_audit(cur, "anonymous", None, "client_login_failed", "customer", customer["id"], {"phone": phone})
            con.commit()
            return jsonify(error="wrong_pin", attempts_left=max(0, 5 - attempts)), 401
        cur.execute("UPDATE customers SET failed_pin_attempts=0,pin_locked_until=NULL,updated_at=now() WHERE id=%s", (customer["id"],))
        token, _ = create_session(cur, "client", customer["id"])
        add_audit(cur, "client", customer["id"], "client_login", "customer", customer["id"])
        cur.execute("SELECT " + CLIENT_FIELDS + " FROM customers WHERE id=%s", (customer["id"],))
        public_customer = cur.fetchone()
        con.commit()
    return jsonify(ok=True, token=token, customer=public_customer)


@app.post("/api/client/recovery/start")
def recovery_start():
    data = json_body()
    try:
        phone = norm_phone(data.get("phone"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    channel = str(data.get("channel") or "sms").lower()
    if channel not in {"sms", "telegram", "max"}:
        return jsonify(error="invalid_channel"), 400
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT id,telegram_linked,max_linked FROM customers WHERE phone=%s AND is_active=true", (phone,))
        customer = cur.fetchone()
        if not customer:
            return jsonify(error="not_found"), 404
        if SMS_MODE != "test":
            if channel == "telegram" and not customer["telegram_linked"]:
                return jsonify(error="telegram_not_linked"), 409
            if channel == "max" and not customer["max_linked"]:
                return jsonify(error="max_not_linked"), 409
        result, retry_after = create_verification(cur, phone, "recover_pin", channel, {"customer_id": str(customer["id"])})
        if retry_after is not None:
            con.commit()
            return jsonify(error="too_many_requests", retry_after=retry_after), 429
        add_audit(cur, "anonymous", None, "pin_recovery_code_created", "customer", customer["id"], {"channel": channel})
        con.commit()
    payload = {"ok": True, "channel": result["channel"], "expires_in": OTP_TTL_MINUTES * 60}
    if SMS_MODE == "test":
        payload["test_code"] = result["code"]
    return jsonify(payload)


@app.post("/api/client/recovery/verify")
def recovery_verify():
    data = json_body()
    try:
        phone = norm_phone(data.get("phone"))
        salt, hashed_pin = pin_hash(data.get("pin"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    with db() as con, con.cursor() as cur:
        row, error = verify_code(cur, phone, "recover_pin", data.get("code"))
        if error:
            con.commit()
            return jsonify(error=error), 401
        cur.execute("SELECT id FROM customers WHERE phone=%s AND is_active=true FOR UPDATE", (phone,))
        customer = cur.fetchone()
        if not customer:
            return jsonify(error="not_found"), 404
        cur.execute(
            "UPDATE customers SET pin_salt=%s,pin_hash=%s,failed_pin_attempts=0,pin_locked_until=NULL,updated_at=now() WHERE id=%s",
            (salt, hashed_pin, customer["id"]),
        )
        cur.execute("UPDATE auth_sessions SET revoked_at=now() WHERE subject_type='client' AND subject_id=%s AND revoked_at IS NULL", (customer["id"],))
        token, _ = create_session(cur, "client", customer["id"])
        add_audit(cur, "client", customer["id"], "pin_recovered", "customer", customer["id"], {"channel": row["channel"]})
        con.commit()
    return jsonify(ok=True, token=token)


@app.get("/api/client/me")
def client_me():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT " + CLIENT_FIELDS + " FROM customers WHERE id=%s AND is_active=true", (subject["id"],))
        customer = cur.fetchone()
    return jsonify(customer=customer) if customer else (jsonify(error="not_found"), 404)


@app.patch("/api/client/me")
def client_update_profile():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    data = json_body()
    name = str(data.get("name") or "").strip()[:300] if "name" in data else None
    birth = data.get("birth_date") if "birth_date" in data else None
    gender = data.get("gender") if "gender" in data else None
    if birth is not None:
        try:
            if birth and not is_adult_birth_date(birth):
                return jsonify(error="minimum_age_18"), 400
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
    if gender not in {None, "", "male", "female"}:
        return jsonify(error="invalid_gender"), 400
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            UPDATE customers SET
                name=CASE WHEN %s IS NULL THEN name ELSE %s END,
                birth_date=CASE WHEN %s IS NULL THEN birth_date ELSE NULLIF(%s,'')::date END,
                gender=CASE WHEN %s IS NULL THEN gender ELSE NULLIF(%s,'') END,
                updated_at=now()
            WHERE id=%s RETURNING """ + CLIENT_FIELDS,
            (name, name, birth, birth, gender, gender, subject["id"]),
        )
        customer = cur.fetchone()
        add_audit(cur, "client", subject["id"], "profile_updated", "customer", subject["id"])
        con.commit()
    return jsonify(ok=True, customer=customer)


@app.get("/api/client/consents")
def client_consents():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    with db() as con, con.cursor() as cur:
        cur.execute(
            "SELECT consent_type,action,document_version,source,created_at FROM current_consents WHERE customer_id=%s ORDER BY consent_type",
            (subject["id"],),
        )
        rows = cur.fetchall()
    return jsonify(consents=rows)


@app.post("/api/client/consents/marketing")
def client_marketing_consent():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    enabled = json_body().get("enabled") is True
    with db() as con, con.cursor() as cur:
        version = current_doc_version(cur, "marketing")
        event = add_consent(cur, subject["id"], "marketing", "grant" if enabled else "revoke", version, subject["session_id"])
        add_audit(cur, "client", subject["id"], "marketing_consent_changed", "customer", subject["id"], {"enabled": enabled})
        con.commit()
    return jsonify(ok=True, enabled=enabled, event=event)


@app.get("/api/client/ledger")
def client_ledger():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    limit = min(max(int(request.args.get("limit", "50")), 1), 100)
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT id,amount,operation_type,source_type,source_id,reason,metadata,created_at
              FROM am_ledger WHERE customer_id=%s ORDER BY created_at DESC LIMIT %s
            """,
            (subject["id"], limit),
        )
        rows = cur.fetchall()
    return jsonify(operations=rows)


@app.post("/api/client/support")
def client_support():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    data = json_body()
    message = str(data.get("message") or "").strip()
    subject_text = str(data.get("subject") or "Обращение в поддержку").strip()[:300]
    if len(message) < 3 or len(message) > 5000:
        return jsonify(error="invalid_message"), 400
    with db() as con, con.cursor() as cur:
        cur.execute(
            "INSERT INTO support_tickets(customer_id,subject,message) VALUES (%s,%s,%s) RETURNING id,status,created_at",
            (subject["id"], subject_text, message),
        )
        ticket = cur.fetchone()
        add_audit(cur, "client", subject["id"], "support_ticket_created", "support_ticket", ticket["id"])
        con.commit()
    return jsonify(ok=True, ticket=ticket), 201


@app.post("/api/admin/bootstrap")
def admin_bootstrap():
    if not ADMIN_BOOTSTRAP_TOKEN:
        return jsonify(error="bootstrap_disabled"), 404
    supplied = str(request.headers.get("X-Bootstrap-Token", ""))
    if not secrets.compare_digest(supplied, ADMIN_BOOTSTRAP_TOKEN):
        return jsonify(error="forbidden"), 403
    data = json_body()
    login = str(data.get("login") or "").strip().lower()
    display_name = str(data.get("display_name") or login).strip()[:300]
    if not re.fullmatch(r"[a-zA-Z0-9_.@-]{3,100}", login):
        return jsonify(error="invalid_login"), 400
    try:
        salt, hashed = password_hash(data.get("password"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM admin_users")
        if cur.fetchone()["n"]:
            return jsonify(error="already_bootstrapped"), 409
        cur.execute(
            """
            INSERT INTO admin_users(login,display_name,password_salt,password_hash,role)
            VALUES (%s,%s,%s,%s,'owner') RETURNING id,login,display_name,role
            """,
            (login, display_name, salt, hashed),
        )
        admin = cur.fetchone()
        add_audit(cur, "system", None, "admin_bootstrapped", "admin", admin["id"], {"login": login})
        con.commit()
    return jsonify(ok=True, admin=admin), 201


@app.post("/api/admin/login")
def admin_login():
    data = json_body()
    login = str(data.get("login") or "").strip().lower()
    password = str(data.get("password") or "")
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT *, (locked_until IS NOT NULL AND locked_until>now()) AS locked FROM admin_users WHERE login=%s AND is_active=true FOR UPDATE", (login,))
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
            attempts = int(admin["failed_login_attempts"] or 0) + 1
            lock_until = datetime.now(timezone.utc) + timedelta(minutes=15) if attempts >= 5 else None
            cur.execute(
                "UPDATE admin_users SET failed_login_attempts=%s,locked_until=%s WHERE id=%s",
                (0 if lock_until else attempts, lock_until, admin["id"]),
            )
            add_audit(cur, "anonymous", None, "admin_login_failed", "admin", admin["id"], {"login": login})
            con.commit()
            return jsonify(error="invalid_credentials"), 401
        if admin.get("mfa_required"):
            return jsonify(error="mfa_required_not_configured"), 503
        cur.execute("UPDATE admin_users SET failed_login_attempts=0,locked_until=NULL,last_login_at=now() WHERE id=%s", (admin["id"],))
        token, _ = create_session(cur, "admin", admin["id"], hours=ADMIN_SESSION_HOURS)
        add_audit(cur, "admin", admin["id"], "admin_login", "admin", admin["id"])
        con.commit()
    return jsonify(ok=True, token=token, admin={"id": admin["id"], "login": admin["login"], "display_name": admin["display_name"], "role": admin["role"]})


@app.get("/api/admin/me")
def admin_me():
    ctx = admin_from_session()
    if not ctx:
        return jsonify(error="unauthorized"), 401
    return jsonify(admin=ctx["admin"], permissions=ctx["permissions"])


@app.get("/api/admin/customers")
def admin_customers():
    ctx = admin_from_session("customer_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403
    q = str(request.args.get("q") or "").strip()
    if not q:
        return jsonify(customers=[])
    try:
        phone = norm_phone(q)
    except ValueError:
        phone = None
    with db() as con, con.cursor() as cur:
        if phone:
            cur.execute("SELECT " + CLIENT_FIELDS + " FROM customers WHERE phone=%s LIMIT 20", (phone,))
        else:
            cur.execute(
                "SELECT " + CLIENT_FIELDS + " FROM customers WHERE lower(name) LIKE lower(%s) OR crm_number=%s ORDER BY created_at DESC LIMIT 20",
                ("%" + q + "%", q),
            )
        rows = cur.fetchall()
    return jsonify(customers=rows)


@app.get("/api/admin/customers/<customer_id>")
def admin_customer(customer_id):
    ctx = admin_from_session("customer_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT " + CLIENT_FIELDS + " FROM customers WHERE id=%s", (customer_id,))
        customer = cur.fetchone()
        if not customer:
            return jsonify(error="not_found"), 404
        cur.execute("SELECT id,amount,operation_type,source_type,source_id,reason,actor_type,created_at FROM am_ledger WHERE customer_id=%s ORDER BY created_at DESC LIMIT 100", (customer_id,))
        ledger = cur.fetchall()
        cur.execute("SELECT consent_type,action,document_version,source,created_at FROM consent_ledger WHERE customer_id=%s ORDER BY created_at DESC LIMIT 100", (customer_id,))
        consents = cur.fetchall()
    return jsonify(customer=customer, ledger=ledger, consents=consents)


@app.post("/api/admin/customers/<customer_id>/adjust-am")
def admin_adjust_am(customer_id):
    ctx = admin_from_session("ledger_adjust")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403
    data = json_body()
    try:
        amount = int(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify(error="invalid_amount"), 400
    reason = str(data.get("reason") or "").strip()
    key = str(data.get("idempotency_key") or "").strip()
    if amount == 0 or abs(amount) > 10_000_000:
        return jsonify(error="invalid_amount"), 400
    if len(reason) < 3:
        return jsonify(error="reason_required"), 400
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,200}", key):
        return jsonify(error="idempotency_key_required"), 400
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT id FROM customers WHERE id=%s AND is_active=true", (customer_id,))
        if not cur.fetchone():
            return jsonify(error="not_found"), 404
        try:
            cur.execute(
                """
                INSERT INTO am_ledger(customer_id,amount,operation_type,source_type,source_id,idempotency_key,reason,actor_type,actor_id,metadata)
                VALUES (%s,%s,'admin_adjustment','admin',%s,%s,%s,'admin',%s,%s::jsonb)
                RETURNING id,amount,created_at
                """,
                (customer_id, amount, str(ctx["admin"]["id"]), key, reason, ctx["admin"]["id"], json.dumps({"admin_login": ctx["admin"]["login"]}, ensure_ascii=False)),
            )
            operation = cur.fetchone()
        except errors.UniqueViolation:
            con.rollback()
            with con.cursor() as cur2:
                cur2.execute("SELECT id,amount,created_at FROM am_ledger WHERE idempotency_key=%s", (key,))
                operation = cur2.fetchone()
                if not operation:
                    raise
                cur2.execute("SELECT balance_am FROM customers WHERE id=%s", (customer_id,))
                balance = cur2.fetchone()["balance_am"]
            return jsonify(ok=True, duplicate=True, operation=operation, balance_am=balance)
        add_audit(cur, "admin", ctx["admin"]["id"], "am_adjusted", "customer", customer_id, {"amount": amount, "reason": reason, "idempotency_key": key})
        cur.execute("SELECT balance_am FROM customers WHERE id=%s", (customer_id,))
        balance = cur.fetchone()["balance_am"]
        con.commit()
    return jsonify(ok=True, duplicate=False, operation=operation, balance_am=balance), 201


@app.get("/api/admin/audit")
def admin_audit():
    ctx = admin_from_session("audit_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403
    limit = min(max(int(request.args.get("limit", "100")), 1), 500)
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT id,actor_type,actor_id,action,target_type,target_id,details,created_at FROM audit_log ORDER BY id DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
    return jsonify(events=rows)


@app.get("/api/admin/orders")
def admin_orders():
    ctx = admin_from_session("customer_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403
    return jsonify(error="crm_not_connected", manual_order_creation=False), 501


@app.post("/api/logout")
def logout():
    token = bearer()
    if token and DATABASE_URL:
        with db() as con, con.cursor() as cur:
            cur.execute("UPDATE auth_sessions SET revoked_at=now() WHERE token_hash=%s AND revoked_at IS NULL", (token_hash(token),))
            con.commit()
    return jsonify(ok=True)
