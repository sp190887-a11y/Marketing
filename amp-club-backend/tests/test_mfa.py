import os
from pathlib import Path

import psycopg
import pyotp
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/ampclub_test")
os.environ["SMS_MODE"] = "test"
os.environ["OTP_PEPPER"] = "ci-test-pepper"
os.environ["MFA_RECOVERY_PEPPER"] = "ci-recovery-pepper"
os.environ["ADMIN_BOOTSTRAP_TOKEN"] = "ci-bootstrap-token"
os.environ["APP_ENCRYPTION_KEY"] = "Ao5usHPfyp5ORBzsg2YD6AwAIGouc1BEhWqDM_kPG9o="

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


def bootstrap(client):
    response = client.post(
        "/api/admin/bootstrap",
        headers={"X-Bootstrap-Token": "ci-bootstrap-token"},
        json={
            "login": "owner",
            "password": "UnitTestOwnerPassword123",
            "display_name": "Владелец",
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["admin"]


def secure_login(client, code=None):
    body = {"login": "owner", "password": "UnitTestOwnerPassword123"}
    if code is not None:
        body["code"] = code
    return client.post("/api/admin/auth/login", json=body)


def test_admin_mfa_setup_totp_login_recovery_and_no_legacy_bypass(client):
    admin = bootstrap(client)

    first_login = secure_login(client)
    assert first_login.status_code == 428, first_login.get_json()
    assert first_login.get_json()["error"] == "mfa_setup_required"
    setup_token = first_login.get_json()["setup_token"]

    setup = client.post(
        "/api/admin/mfa/setup/start",
        json={"setup_token": setup_token},
    )
    assert setup.status_code == 200, setup.get_json()
    secret = setup.get_json()["secret"]
    assert setup.get_json()["otpauth_uri"].startswith("otpauth://totp/")

    code = pyotp.TOTP(secret).now()
    confirmed = client.post(
        "/api/admin/mfa/setup/confirm",
        json={"setup_token": setup_token, "code": code},
    )
    assert confirmed.status_code == 200, confirmed.get_json()
    recovery_codes = confirmed.get_json()["recovery_codes"]
    assert len(recovery_codes) == 8
    admin_token = confirmed.get_json()["token"]

    with db() as con, con.cursor() as cur:
        cur.execute(
            "SELECT mfa_secret_encrypted,mfa_required,mfa_enabled_at FROM admin_users WHERE id=%s",
            (admin["id"],),
        )
        stored = cur.fetchone()
    assert stored["mfa_required"] is True
    assert stored["mfa_enabled_at"] is not None
    assert stored["mfa_secret_encrypted"] != secret
    assert secret not in stored["mfa_secret_encrypted"]

    status = client.get(
        "/api/admin/mfa/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status.status_code == 200
    assert status.get_json()["mfa"]["recovery_codes_left"] == 8

    missing = secure_login(client)
    assert missing.status_code == 401
    assert missing.get_json()["error"] == "mfa_code_required"

    wrong = secure_login(client, "000000")
    assert wrong.status_code == 401
    assert wrong.get_json()["error"] == "invalid_mfa_code"

    good = secure_login(client, pyotp.TOTP(secret).now())
    assert good.status_code == 200, good.get_json()
    assert good.get_json()["mfa_method"] == "totp"

    recovery = secure_login(client, recovery_codes[0])
    assert recovery.status_code == 200, recovery.get_json()
    assert recovery.get_json()["mfa_method"] == "recovery"

    reused = secure_login(client, recovery_codes[0])
    assert reused.status_code == 401
    assert reused.get_json()["error"] == "invalid_mfa_code"

    legacy = client.post(
        "/api/admin/login",
        json={"login": "owner", "password": "UnitTestOwnerPassword123"},
    )
    assert legacy.status_code == 503
    assert legacy.get_json()["error"] == "mfa_required_not_configured"
