import os
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/ampclub_test",
)
ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@pytest.fixture(scope="module", autouse=True)
def ensure_schema():
    with psycopg.connect(DATABASE_URL, autocommit=True) as con:
        with con.cursor() as cur:
            for path in sorted(MIGRATIONS.glob("*.sql")):
                cur.execute(path.read_text(encoding="utf-8"))
    yield


def test_ledger_rules_are_append_only_and_balance_cache_matches_sum():
    with connect() as con, con.cursor() as cur:
        cur.execute(
            "INSERT INTO customers(phone,name) VALUES ('9000000099','LEDGER RULE TEST') RETURNING id"
        )
        customer_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO am_ledger(
                customer_id,amount,operation_type,source_type,source_id,
                idempotency_key,reason
            ) VALUES (%s,125,'test','ci','portable','portable-ledger-rule-0001','CI')
            RETURNING id
            """,
            (customer_id,),
        )
        operation_id = cur.fetchone()["id"]
        con.commit()

    with connect() as con, con.cursor() as cur:
        cur.execute(
            "SELECT cached_balance_am,ledger_balance_am,is_consistent FROM customer_ledger_balances WHERE customer_id=%s",
            (customer_id,),
        )
        balance = cur.fetchone()
        assert balance["cached_balance_am"] == 125
        assert balance["ledger_balance_am"] == 125
        assert balance["is_consistent"] is True

        cur.execute("UPDATE am_ledger SET amount=999 WHERE id=%s", (operation_id,))
        cur.execute("DELETE FROM am_ledger WHERE id=%s", (operation_id,))
        con.commit()

    with connect() as con, con.cursor() as cur:
        cur.execute("SELECT amount FROM am_ledger WHERE id=%s", (operation_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["amount"] == 125

        cur.execute(
            "SELECT cached_balance_am,ledger_balance_am,is_consistent FROM customer_ledger_balances WHERE customer_id=%s",
            (customer_id,),
        )
        balance = cur.fetchone()
        assert balance["cached_balance_am"] == 125
        assert balance["ledger_balance_am"] == 125
        assert balance["is_consistent"] is True


def test_ledger_idempotency_key_is_unique():
    with connect() as con, con.cursor() as cur:
        cur.execute(
            "INSERT INTO customers(phone,name) VALUES ('9000000098','IDEMPOTENCY TEST') RETURNING id"
        )
        customer_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO am_ledger(
                customer_id,amount,operation_type,source_type,source_id,
                idempotency_key,reason
            ) VALUES (%s,10,'test','ci','first','portable-ledger-idempotency-0001','CI')
            """,
            (customer_id,),
        )
        con.commit()

    with pytest.raises(psycopg.errors.UniqueViolation):
        with connect() as con, con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO am_ledger(
                    customer_id,amount,operation_type,source_type,source_id,
                    idempotency_key,reason
                ) VALUES (%s,10,'test','ci','duplicate','portable-ledger-idempotency-0001','CI')
                """,
                (customer_id,),
            )
            con.commit()
