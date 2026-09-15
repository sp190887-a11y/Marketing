import os
from pathlib import Path

import psycopg
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/ampclub_test")
os.environ["SMS_MODE"] = "test"
os.environ["OTP_PEPPER"] = "ci-test-pepper"
os.environ["ADMIN_BOOTSTRAP_TOKEN"] = "ci-bootstrap-token"
os.environ["ALLOWED_ORIGINS"] = "https://club.amplituda-nn.ru,https://sp190887-a11y.github.io"

from api.index import app, db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


@pytest.fixture(scope="session", autouse=True)
def migrate_database():
    url = os.environ["DATABASE_URL"]
    with psycopg.connect(url, autocommit=True) as con:
        with con.cursor() as cur:
            for path in sorted(MIGRATIONS.glob("*.sql")):
                cur.execute(path.read_text(encoding="utf-8"))
    yield


@pytest.fixture(autouse=True)
def clean_database():
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                auth_sessions,
                verification_codes,
                consent_ledger,
                am_ledger,
                support_tickets,
                audit_log,
                admin_users,
                customers
            RESTART IDENTITY CASCADE
            """
        )
        con.commit()
    yield


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def legal_consents(marketing=False):
    return {
        "age_18": True,
        "club_rules": True,
        "personal_data": True,
        "marketing": marketing,
    }


def register(client, phone="9991234567", pin="1234", marketing=False, name="Сергей"):
    start = client.post(
        "/api/client/register/start",
        json={"phone": phone, "consents": legal_consents(marketing)},
    )
    assert start.status_code == 200, start.get_json()
    assert start.get_json()["test_code"] == "1111"
    verify = client.post(
        "/api/client/register/verify",
        json={
            "phone": phone,
            "code": "1111",
            "pin": pin,
            "name": name,
            "birth_date": "1987-08-19",
            "gender": "male",
        },
    )
    assert verify.status_code == 200, verify.get_json()
    return verify.get_json()


def bootstrap_and_login_admin(client):
    created = client.post(
        "/api/admin/bootstrap",
        headers={"X-Bootstrap-Token": "ci-bootstrap-token"},
        json={
            "login": "owner",
            "password": "StrongPass123!",
            "display_name": "Владелец",
        },
    )
    assert created.status_code == 201, created.get_json()
    logged = client.post(
        "/api/admin/login",
        json={"login": "owner", "password": "StrongPass123!"},
    )
    assert logged.status_code == 200, logged.get_json()
    return logged.get_json()["token"]


def test_health_and_legal_documents(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["storage"] == "postgres"
    docs = client.get("/api/legal/current")
    assert docs.status_code == 200
    payload = docs.get_json()
    assert payload["minimum_age"] == 18
    assert payload["marketing_optional"] is True
    assert payload["documents"]["personal_data"]["version"] == "2026-09-15"
    assert payload["documents"]["club_rules"]["version"] == "2026-09-15"


def test_registration_requires_separate_legal_consents(client):
    response = client.post(
        "/api/client/register/start",
        json={"phone": "9991234567", "consents": {"age_18": True}},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "club_rules_required"


def test_cross_device_registration_login_and_admin_search(client):
    registered = register(client, marketing=False)
    customer_id = str(registered["customer"]["id"])

    second_device = app.test_client()
    login = second_device.post(
        "/api/client/login",
        json={"phone": "8 (999) 123-45-67", "pin": "1234"},
    )
    assert login.status_code == 200, login.get_json()
    assert str(login.get_json()["customer"]["id"]) == customer_id

    admin_token = bootstrap_and_login_admin(client)
    found = client.get(
        "/api/admin/customers?q=89991234567",
        headers=auth(admin_token),
    )
    assert found.status_code == 200
    rows = found.get_json()["customers"]
    assert len(rows) == 1
    assert str(rows[0]["id"]) == customer_id

    with db() as con, con.cursor() as cur:
        cur.execute(
            "SELECT consent_type,action FROM consent_ledger WHERE customer_id=%s ORDER BY consent_type",
            (customer_id,),
        )
        consents = {(r["consent_type"], r["action"]) for r in cur.fetchall()}
    assert ("age_18", "grant") in consents
    assert ("club_rules", "grant") in consents
    assert ("personal_data", "grant") in consents
    assert ("marketing", "decline") in consents


def test_marketing_consent_is_optional_and_revocable(client):
    registered = register(client, marketing=False)
    token = registered["token"]

    before = client.get("/api/client/consents", headers=auth(token))
    assert before.status_code == 200
    marketing = [x for x in before.get_json()["consents"] if x["consent_type"] == "marketing"][0]
    assert marketing["action"] == "decline"

    granted = client.post(
        "/api/client/consents/marketing",
        headers=auth(token),
        json={"enabled": True},
    )
    assert granted.status_code == 200
    assert granted.get_json()["enabled"] is True

    revoked = client.post(
        "/api/client/consents/marketing",
        headers=auth(token),
        json={"enabled": False},
    )
    assert revoked.status_code == 200
    assert revoked.get_json()["enabled"] is False

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT action FROM consent_ledger WHERE customer_id=%s AND consent_type='marketing' ORDER BY created_at", (registered["customer"]["id"],))
        actions = [row["action"] for row in cur.fetchall()]
    assert actions == ["decline", "grant", "revoke"]


def test_am_ledger_is_idempotent_and_balance_cannot_be_edited_directly(client):
    registered = register(client)
    customer_id = str(registered["customer"]["id"])
    client_token = registered["token"]
    admin_token = bootstrap_and_login_admin(client)

    payload = {
        "amount": 150,
        "reason": "Тестовое начисление",
        "idempotency_key": "test-adjustment-0001",
    }
    first = client.post(
        f"/api/admin/customers/{customer_id}/adjust-am",
        headers=auth(admin_token),
        json=payload,
    )
    assert first.status_code == 201, first.get_json()
    assert first.get_json()["balance_am"] == 150

    duplicate = client.post(
        f"/api/admin/customers/{customer_id}/adjust-am",
        headers=auth(admin_token),
        json=payload,
    )
    assert duplicate.status_code == 200, duplicate.get_json()
    assert duplicate.get_json()["duplicate"] is True
    assert duplicate.get_json()["balance_am"] == 150

    ledger = client.get("/api/client/ledger", headers=auth(client_token))
    assert ledger.status_code == 200
    assert len(ledger.get_json()["operations"]) == 1
    assert ledger.get_json()["operations"][0]["amount"] == 150

    with pytest.raises(psycopg.Error):
        with db() as con, con.cursor() as cur:
            cur.execute("UPDATE customers SET balance_am=999 WHERE id=%s", (customer_id,))
            con.commit()

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT cached_balance_am,ledger_balance_am,is_consistent FROM customer_ledger_balances WHERE customer_id=%s", (customer_id,))
        balance = cur.fetchone()
    assert balance["cached_balance_am"] == 150
    assert balance["ledger_balance_am"] == 150
    assert balance["is_consistent"] is True


def test_pin_recovery_revokes_old_session(client):
    registered = register(client, pin="1234")
    old_token = registered["token"]

    started = client.post(
        "/api/client/recovery/start",
        json={"phone": "9991234567", "channel": "telegram"},
    )
    assert started.status_code == 200
    assert started.get_json()["test_code"] == "2222"

    recovered = client.post(
        "/api/client/recovery/verify",
        json={"phone": "9991234567", "code": "2222", "pin": "4321"},
    )
    assert recovered.status_code == 200, recovered.get_json()

    old_me = client.get("/api/client/me", headers=auth(old_token))
    assert old_me.status_code == 401

    login_old = client.post("/api/client/login", json={"phone": "9991234567", "pin": "1234"})
    assert login_old.status_code == 401
    login_new = client.post("/api/client/login", json={"phone": "9991234567", "pin": "4321"})
    assert login_new.status_code == 200


def test_support_ticket_is_server_side(client):
    registered = register(client)
    response = client.post(
        "/api/client/support",
        headers=auth(registered["token"]),
        json={"subject": "Проверка", "message": "Нужна помощь с АМ Клубом"},
    )
    assert response.status_code == 201
    ticket_id = response.get_json()["ticket"]["id"]
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT message,status FROM support_tickets WHERE id=%s", (ticket_id,))
        row = cur.fetchone()
    assert row["message"] == "Нужна помощь с АМ Клубом"
    assert row["status"] == "new"
