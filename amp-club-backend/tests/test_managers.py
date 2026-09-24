import os
from pathlib import Path

import psycopg
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/ampclub_test")
os.environ["SMS_MODE"] = "test"
os.environ["OTP_PEPPER"] = "ci-test-pepper"
os.environ["ADMIN_BOOTSTRAP_TOKEN"] = "ci-bootstrap-token"

from api.app import app  # noqa: E402
from api.index import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


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
                admin_mfa_recovery_codes, admin_auth_challenges,
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


def bootstrap_admin(client):
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
    login = client.post(
        "/api/admin/login",
        json={"login": "owner", "password": "StrongPass123!"},
    )
    assert login.status_code == 200, login.get_json()
    return login.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_customer():
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO customers(phone,name,crm_number)
            VALUES ('9991234567','Тестовый клиент','3862')
            RETURNING id,club_member_no,manager_code
            """
        )
        row = cur.fetchone()
        con.commit()
    return row


def test_default_club_number_and_manager_catalog(client):
    customer = create_customer()
    assert customer["manager_code"] == 0
    assert int(customer["club_member_no"]) > 0

    admin_token = bootstrap_admin(client)
    response = client.get("/api/admin/managers", headers=auth(admin_token))
    assert response.status_code == 200
    managers = {int(row["code"]): row["name"] for row in response.get_json()["managers"]}
    assert managers[0] == "Не закреплён"
    assert managers[1] == "Настя"
    assert managers[2] == "Ирина"
    assert managers[3] == "Алёна"


def test_assign_change_unassign_manager_keeps_permanent_member_number(client):
    customer = create_customer()
    member_no = int(customer["club_member_no"])
    admin_token = bootstrap_admin(client)

    assigned = client.post(
        f"/api/admin/customers/{customer['id']}/manager",
        headers=auth(admin_token),
        json={"manager_code": 1, "reason": "Закрепили клиента за Настей"},
    )
    assert assigned.status_code == 200, assigned.get_json()
    assert assigned.get_json()["changed"] is True
    assert assigned.get_json()["club_code"] == f"A1-{member_no:05d}"

    changed = client.post(
        f"/api/admin/customers/{customer['id']}/manager",
        headers=auth(admin_token),
        json={"manager_code": 3, "reason": "Передали Алёне"},
    )
    assert changed.status_code == 200, changed.get_json()
    assert changed.get_json()["club_code"] == f"A3-{member_no:05d}"

    unassigned = client.post(
        f"/api/admin/customers/{customer['id']}/manager",
        headers=auth(admin_token),
        json={"manager_code": 0, "reason": "Временно без менеджера"},
    )
    assert unassigned.status_code == 200, unassigned.get_json()
    assert unassigned.get_json()["club_code"] == f"A0-{member_no:05d}"

    history = client.get(
        f"/api/admin/customers/{customer['id']}/manager-history",
        headers=auth(admin_token),
    )
    assert history.status_code == 200
    rows = history.get_json()["history"]
    assert len(rows) == 3
    assert int(rows[0]["new_manager_code"]) == 0
    assert int(rows[1]["new_manager_code"]) == 3
    assert int(rows[2]["new_manager_code"]) == 1

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT club_member_no,manager_code FROM customers WHERE id=%s", (customer["id"],))
        current = cur.fetchone()
    assert int(current["club_member_no"]) == member_no
    assert int(current["manager_code"]) == 0


def test_lookup_by_club_code_phone_crm_and_permanent_number(client):
    customer = create_customer()
    member_no = int(customer["club_member_no"])
    admin_token = bootstrap_admin(client)

    assigned = client.post(
        f"/api/admin/customers/{customer['id']}/manager",
        headers=auth(admin_token),
        json={"manager_code": 2},
    )
    assert assigned.status_code == 200
    code = f"A2-{member_no:05d}"

    for query in (code, "89991234567", "3862", str(member_no)):
        found = client.get(
            "/api/admin/customer-lookup",
            query_string={"q": query},
            headers=auth(admin_token),
        )
        assert found.status_code == 200, (query, found.get_json())
        rows = found.get_json()["customers"]
        assert any(str(row["id"]) == str(customer["id"]) for row in rows), query

    code_result = client.get(
        "/api/admin/customer-lookup",
        query_string={"q": code},
        headers=auth(admin_token),
    ).get_json()["customers"][0]
    assert code_result["club_code"] == code
    assert code_result["manager_name"] == "Ирина"
