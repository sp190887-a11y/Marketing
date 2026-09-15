import os
from pathlib import Path

import psycopg
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/ampclub_test")
os.environ["SMS_MODE"] = "test"
os.environ["OTP_PEPPER"] = "ci-test-pepper"
os.environ["CRM_WEBHOOK_SECRET"] = "ci-crm-secret"

from api.app import app  # noqa: E402
from api.index import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
CRM_HEADERS = {"X-AMP-CRM-Secret": "ci-crm-secret"}


@pytest.fixture(scope="module", autouse=True)
def schema():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as con:
        with con.cursor() as cur:
            for path in sorted(MIGRATIONS.glob("*.sql")):
                cur.execute(path.read_text(encoding="utf-8"))
    yield


@pytest.fixture(autouse=True)
def clean():
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                crm_events, crm_orders, crm_customer_links, reward_accounts,
                auth_sessions, verification_codes, consent_ledger, am_ledger,
                support_tickets, audit_log, admin_users, customers
            RESTART IDENTITY CASCADE
            """
        )
        con.commit()
    yield


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def crm_event(client, *, event_id, order_id, version, amount, status="paid", phone="9991234567"):
    return client.post(
        "/api/integrations/crm/order-event",
        headers=CRM_HEADERS,
        json={
            "event_id": event_id,
            "event_type": "order_changed",
            "event_version": version,
            "external_order_id": order_id,
            "external_customer_id": "CRM-CUSTOMER-1001",
            "crm_number": "1001",
            "phone": phone,
            "customer_name": "Сергей",
            "eligible_amount_kopecks": amount,
            "status": status,
            "occurred_at": "2026-09-15T12:00:00+03:00",
        },
    )


def test_crm_connector_requires_server_secret(client):
    response = client.post(
        "/api/integrations/crm/order-event",
        headers={"X-AMP-CRM-Secret": "wrong"},
        json={},
    )
    assert response.status_code == 403


def test_crm_accrual_carry_remainder_refund_and_idempotency(client):
    first = crm_event(
        client,
        event_id="crm-e1",
        order_id="order-1",
        version=1,
        amount=5_000,
    )
    assert first.status_code == 201, first.get_json()
    assert first.get_json()["event"]["am_delta"] == 0
    assert first.get_json()["event"]["remainder_after_kopecks"] == 5_000
    assert first.get_json()["event"]["balance_am"] == 0

    second = crm_event(
        client,
        event_id="crm-e2",
        order_id="order-2",
        version=1,
        amount=7_500,
    )
    assert second.status_code == 201, second.get_json()
    assert second.get_json()["event"]["am_delta"] == 1
    assert second.get_json()["event"]["remainder_after_kopecks"] == 2_500
    assert second.get_json()["event"]["balance_am"] == 1

    duplicate = crm_event(
        client,
        event_id="crm-e2",
        order_id="order-2",
        version=1,
        amount=7_500,
    )
    assert duplicate.status_code == 200
    assert duplicate.get_json()["event"]["duplicate"] is True
    assert duplicate.get_json()["event"]["balance_am"] == 1

    refund = crm_event(
        client,
        event_id="crm-e3",
        order_id="order-2",
        version=2,
        amount=0,
        status="refunded",
    )
    assert refund.status_code == 201, refund.get_json()
    assert refund.get_json()["event"]["am_delta"] == -1
    assert refund.get_json()["event"]["remainder_after_kopecks"] == 5_000
    assert refund.get_json()["event"]["balance_am"] == 0

    cancel = crm_event(
        client,
        event_id="crm-e4",
        order_id="order-1",
        version=2,
        amount=0,
        status="cancelled",
    )
    assert cancel.status_code == 201, cancel.get_json()
    assert cancel.get_json()["event"]["am_delta"] == 0
    assert cancel.get_json()["event"]["remainder_after_kopecks"] == 0
    assert cancel.get_json()["event"]["balance_am"] == 0

    stale = crm_event(
        client,
        event_id="crm-e5",
        order_id="order-1",
        version=1,
        amount=5_000,
    )
    assert stale.status_code == 409
    assert stale.get_json()["error"] == "stale_event"

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT amount FROM am_ledger ORDER BY created_at,id")
        ledger = [row["amount"] for row in cur.fetchall()]
        cur.execute("SELECT count(*) AS n FROM crm_events")
        events = cur.fetchone()["n"]
        cur.execute("SELECT remainder_kopecks FROM reward_accounts")
        remainder = cur.fetchone()["remainder_kopecks"]
    assert ledger == [1, -1]
    assert events == 4
    assert remainder == 0


def test_crm_shadow_customer_becomes_same_club_account_on_registration(client):
    event = crm_event(
        client,
        event_id="crm-shadow-1",
        order_id="order-shadow",
        version=1,
        amount=12_500,
    )
    assert event.status_code == 201, event.get_json()
    shadow_id = str(event.get_json()["event"]["customer_id"])

    start = client.post(
        "/api/client/register/start",
        json={
            "phone": "9991234567",
            "consents": {
                "age_18": True,
                "club_rules": True,
                "personal_data": True,
                "marketing": False,
            },
        },
    )
    assert start.status_code == 200, start.get_json()

    verified = client.post(
        "/api/client/register/verify",
        json={
            "phone": "9991234567",
            "code": "1111",
            "pin": "1234",
            "name": "Сергей Сергеевич",
            "birth_date": "1987-08-19",
            "gender": "male",
        },
    )
    assert verified.status_code == 200, verified.get_json()
    assert str(verified.get_json()["customer"]["id"]) == shadow_id
    assert verified.get_json()["customer"]["balance_am"] == 1
    assert float(verified.get_json()["customer"]["ruble_remainder"]) == 25.0

    token = verified.get_json()["token"]
    orders = client.get(
        "/api/client/orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert orders.status_code == 200
    assert orders.get_json()["source"] == "crm"
    assert orders.get_json()["manual_creation"] is False
    assert len(orders.get_json()["orders"]) == 1
    assert orders.get_json()["orders"][0]["external_order_id"] == "order-shadow"
