import os, re, secrets, hashlib, base64
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
import psycopg
from psycopg.rows import dict_row

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SMS_MODE = os.environ.get("SMS_MODE", "test")
ADMIN_LOGIN = os.environ.get("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ALLOWED_ORIGINS = {x.strip() for x in os.environ.get("ALLOWED_ORIGINS", "https://sp190887-a11y.github.io").split(",") if x.strip()}

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def norm_phone(v):
    d = re.sub(r"\D", "", str(v or ""))
    if len(d) == 11 and d[0] in "78":
        d = d[1:]
    if not re.fullmatch(r"\d{10}", d):
        raise ValueError("invalid_phone")
    return d

def pin_hash(pin, salt_b64=None):
    if not re.fullmatch(r"\d{4}", str(pin or "")):
        raise ValueError("invalid_pin")
    salt = base64.urlsafe_b64decode(salt_b64.encode()) if salt_b64 else secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt, 220000)
    return base64.urlsafe_b64encode(salt).decode(), base64.urlsafe_b64encode(value).decode()

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def create_session(cur, kind, subject_id, days=90):
    token = secrets.token_urlsafe(36)
    cur.execute(
        "INSERT INTO auth_sessions(subject_type,subject_id,token_hash,expires_at) VALUES (%s,%s,%s,%s)",
        (kind, subject_id, token_hash(token), datetime.now(timezone.utc) + timedelta(days=days)),
    )
    return token

def bearer():
    h = request.headers.get("Authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else ""

def require_session(kind):
    token = bearer()
    if not token:
        return None
    with db() as con, con.cursor() as cur:
        cur.execute(
            "SELECT subject_id FROM auth_sessions WHERE subject_type=%s AND token_hash=%s AND revoked_at IS NULL AND expires_at>now() ORDER BY created_at DESC LIMIT 1",
            (kind, token_hash(token)),
        )
        row = cur.fetchone()
        return str(row["subject_id"]) if row else None

@app.after_request
def cors(resp):
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,OPTIONS"
    resp.headers["Cache-Control"] = "no-store"
    return resp

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
            n = cur.fetchone()["n"]
        return jsonify(ok=True, service="amp-club-python", customers=n, storage="postgres")
    except Exception:
        return jsonify(ok=False, error="db_unavailable"), 500

@app.post("/api/client/register/start")
def register_start():
    try:
        phone = norm_phone((request.get_json(silent=True) or {}).get("phone"))
    except ValueError:
        return jsonify(error="invalid_phone"), 400
    return jsonify(ok=True, phone=phone, channel="test" if SMS_MODE == "test" else "sms", test_code="1111" if SMS_MODE == "test" else None)

@app.post("/api/client/register/verify")
def register_verify():
    data = request.get_json(silent=True) or {}
    try:
        phone = norm_phone(data.get("phone"))
        salt, ph = pin_hash(str(data.get("pin") or ""))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if SMS_MODE == "test" and str(data.get("code") or "") != "1111":
        return jsonify(error="wrong_code"), 400
    name = str(data.get("name") or "").strip()
    with db() as con, con.cursor() as cur:
        cur.execute(
            "INSERT INTO customers(phone,name,pin_salt,pin_hash,updated_at) VALUES (%s,%s,%s,%s,now()) ON CONFLICT(phone) DO UPDATE SET name=CASE WHEN EXCLUDED.name<>'' THEN EXCLUDED.name ELSE customers.name END,pin_salt=EXCLUDED.pin_salt,pin_hash=EXCLUDED.pin_hash,updated_at=now() RETURNING id,phone,name,balance_am,discount_percent,crm_number",
            (phone, name, salt, ph),
        )
        customer = cur.fetchone()
        token = create_session(cur, "client", customer["id"])
        con.commit()
    return jsonify(ok=True, token=token, customer=customer)

@app.post("/api/client/login")
def client_login():
    data = request.get_json(silent=True) or {}
    try:
        phone = norm_phone(data.get("phone"))
        pin = str(data.get("pin") or "")
        pin_hash(pin)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT id,phone,name,pin_salt,pin_hash,balance_am,discount_percent,crm_number FROM customers WHERE phone=%s AND is_active=true", (phone,))
        customer = cur.fetchone()
        if not customer or not customer["pin_salt"] or not customer["pin_hash"]:
            return jsonify(error="not_found"), 404
        _, ph = pin_hash(pin, customer["pin_salt"])
        if not secrets.compare_digest(ph, customer["pin_hash"]):
            return jsonify(error="wrong_pin"), 401
        token = create_session(cur, "client", customer["id"])
        cur.execute("UPDATE customers SET updated_at=now() WHERE id=%s", (customer["id"],))
        con.commit()
        customer.pop("pin_salt", None)
        customer.pop("pin_hash", None)
    return jsonify(ok=True, token=token, customer=customer)

@app.get("/api/client/me")
def client_me():
    customer_id = require_session("client")
    if not customer_id:
        return jsonify(error="unauthorized"), 401
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT id,phone,name,birth_date,gender,discount_percent,balance_am,ruble_remainder,crm_number,telegram_linked,max_linked,created_at FROM customers WHERE id=%s", (customer_id,))
        customer = cur.fetchone()
    return jsonify(customer=customer) if customer else (jsonify(error="not_found"), 404)

@app.post("/api/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    if not ADMIN_PASSWORD:
        return jsonify(error="admin_not_configured"), 503
    if not secrets.compare_digest(str(data.get("login") or ""), ADMIN_LOGIN) or not secrets.compare_digest(str(data.get("password") or ""), ADMIN_PASSWORD):
        return jsonify(error="invalid_credentials"), 401
    admin_id = "00000000-0000-0000-0000-000000000001"
    with db() as con, con.cursor() as cur:
        token = create_session(cur, "admin", admin_id, days=7)
        cur.execute("INSERT INTO audit_log(actor_type,actor_id,action) VALUES ('admin',%s,'admin_login')", (admin_id,))
        con.commit()
    return jsonify(ok=True, token=token, admin={"login": ADMIN_LOGIN})

@app.get("/api/admin/customers")
def admin_customers():
    if not require_session("admin"):
        return jsonify(error="unauthorized"), 401
    q = str(request.args.get("q") or "").strip()
    try:
        phone = norm_phone(q) if q else None
    except ValueError:
        phone = None
    with db() as con, con.cursor() as cur:
        if phone:
            cur.execute("SELECT id,phone,name,birth_date,gender,discount_percent,balance_am,ruble_remainder,crm_number,telegram_linked,max_linked,created_at FROM customers WHERE phone=%s LIMIT 20", (phone,))
        elif q:
            cur.execute("SELECT id,phone,name,birth_date,gender,discount_percent,balance_am,ruble_remainder,crm_number,telegram_linked,max_linked,created_at FROM customers WHERE lower(name) LIKE lower(%s) OR crm_number=%s ORDER BY created_at DESC LIMIT 20", ("%" + q + "%", q))
        else:
            cur.execute("SELECT id,phone,name,birth_date,gender,discount_percent,balance_am,ruble_remainder,crm_number,telegram_linked,max_linked,created_at FROM customers ORDER BY created_at DESC LIMIT 50")
        rows = cur.fetchall()
    return jsonify(customers=rows)

@app.post("/api/logout")
def logout():
    token = bearer()
    if token and DATABASE_URL:
        with db() as con, con.cursor() as cur:
            cur.execute("UPDATE auth_sessions SET revoked_at=now() WHERE token_hash=%s AND revoked_at IS NULL", (token_hash(token),))
            con.commit()
    return jsonify(ok=True)
