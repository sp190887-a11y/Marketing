import json
import os
import secrets
from datetime import datetime

from flask import Blueprint, jsonify, request

from .index import add_audit, admin_from_session, db, norm_phone, session_subject

crm_bp = Blueprint("crm", __name__)
AM_STEP_KOPECKS = 10_000  # 100 RUB = 1 AM


def crm_secret_ok():
    expected = os.environ.get("CRM_WEBHOOK_SECRET", "")
    supplied = request.headers.get("X-AMP-CRM-Secret", "")
    if not expected:
        return None
    return secrets.compare_digest(expected, supplied)


def text(value, field, max_len=300):
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field}_required")
    if len(result) > max_len:
        raise ValueError(f"{field}_too_long")
    return result


def nonnegative_int(value, field):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid_{field}")
    if result < 0:
        raise ValueError(f"invalid_{field}")
    return result


def positive_int(value, field):
    result = nonnegative_int(value, field)
    if result < 1:
        raise ValueError(f"invalid_{field}")
    return result


def resolve_customer(cur, payload):
    external_customer_id = text(payload.get("external_customer_id"), "external_customer_id", 200)
    cur.execute(
        "SELECT customer_id FROM crm_customer_links WHERE external_customer_id=%s FOR UPDATE",
        (external_customer_id,),
    )
    linked = cur.fetchone()
    if linked:
        return linked["customer_id"], external_customer_id

    phone = norm_phone(payload.get("phone"))
    name = str(payload.get("customer_name") or "").strip()[:300]
    crm_number = str(payload.get("crm_number") or "").strip()[:100] or None

    cur.execute("SELECT id,name,crm_number FROM customers WHERE phone=%s FOR UPDATE", (phone,))
    customer = cur.fetchone()
    if customer:
        customer_id = customer["id"]
        cur.execute(
            """
            UPDATE customers
               SET name=CASE WHEN name='' AND %s<>'' THEN %s ELSE name END,
                   crm_number=CASE WHEN crm_number IS NULL THEN %s ELSE crm_number END,
                   updated_at=now()
             WHERE id=%s
            """,
            (name, name, crm_number, customer_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO customers(phone,name,crm_number)
            VALUES (%s,%s,%s)
            RETURNING id
            """,
            (phone, name, crm_number),
        )
        customer_id = cur.fetchone()["id"]

    cur.execute(
        """
        INSERT INTO crm_customer_links(external_customer_id,customer_id)
        VALUES (%s,%s)
        ON CONFLICT(external_customer_id) DO NOTHING
        """,
        (external_customer_id, customer_id),
    )
    cur.execute(
        "SELECT customer_id FROM crm_customer_links WHERE external_customer_id=%s",
        (external_customer_id,),
    )
    actual = cur.fetchone()
    if not actual or actual["customer_id"] != customer_id:
        raise ValueError("crm_customer_link_conflict")
    return customer_id, external_customer_id


def event_response(cur, event_id, duplicate):
    cur.execute(
        """
        SELECT e.event_id,e.event_type,e.event_version,e.external_order_id,e.customer_id,
               e.old_amount_kopecks,e.new_amount_kopecks,e.delta_kopecks,e.am_delta,
               e.remainder_before_kopecks,e.remainder_after_kopecks,e.processed_at,
               c.balance_am
          FROM crm_events e
          JOIN customers c ON c.id=e.customer_id
         WHERE e.event_id=%s
        """,
        (event_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    row["duplicate"] = duplicate
    row["remainder_rubles"] = row["remainder_after_kopecks"] / 100
    return row


@crm_bp.post("/api/integrations/crm/order-event")
def crm_order_event():
    secret_state = crm_secret_ok()
    if secret_state is None:
        return jsonify(error="crm_connector_disabled"), 503
    if secret_state is False:
        return jsonify(error="forbidden"), 403

    payload = request.get_json(silent=True) or {}
    try:
        event_id = text(payload.get("event_id"), "event_id", 200)
        event_type = text(payload.get("event_type") or "order_changed", "event_type", 100)
        event_version = positive_int(payload.get("event_version"), "event_version")
        external_order_id = text(payload.get("external_order_id"), "external_order_id", 200)
        new_amount = nonnegative_int(payload.get("eligible_amount_kopecks"), "eligible_amount_kopecks")
        status = text(payload.get("status") or "unknown", "status", 100)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    occurred_at = payload.get("occurred_at")
    if occurred_at:
        try:
            datetime.fromisoformat(str(occurred_at).replace("Z", "+00:00"))
        except ValueError:
            return jsonify(error="invalid_occurred_at"), 400

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (event_id,))
        existing = event_response(cur, event_id, True)
        if existing:
            con.commit()
            return jsonify(ok=True, event=existing)

        try:
            customer_id, external_customer_id = resolve_customer(cur, payload)
        except ValueError as exc:
            con.rollback()
            return jsonify(error=str(exc)), 409 if str(exc).endswith("conflict") else 400

        cur.execute(
            "INSERT INTO reward_accounts(customer_id) VALUES (%s) ON CONFLICT(customer_id) DO NOTHING",
            (customer_id,),
        )
        cur.execute(
            "SELECT remainder_kopecks FROM reward_accounts WHERE customer_id=%s FOR UPDATE",
            (customer_id,),
        )
        remainder_before = cur.fetchone()["remainder_kopecks"]

        cur.execute(
            "SELECT customer_id,eligible_amount_kopecks,last_event_version FROM crm_orders WHERE external_order_id=%s FOR UPDATE",
            (external_order_id,),
        )
        order = cur.fetchone()
        if order and order["customer_id"] != customer_id:
            con.rollback()
            return jsonify(error="order_customer_mismatch"), 409
        if order and event_version <= order["last_event_version"]:
            con.rollback()
            return jsonify(
                error="stale_event",
                current_event_version=order["last_event_version"],
            ), 409

        old_amount = order["eligible_amount_kopecks"] if order else 0
        delta = new_amount - old_amount
        reward_total = remainder_before + delta
        am_delta, remainder_after = divmod(reward_total, AM_STEP_KOPECKS)

        if am_delta:
            cur.execute(
                """
                INSERT INTO am_ledger(
                    customer_id,amount,operation_type,source_type,source_id,
                    idempotency_key,reason,actor_type,metadata
                ) VALUES (%s,%s,'crm_order_accrual','crm',%s,%s,%s,'crm',%s::jsonb)
                """,
                (
                    customer_id,
                    am_delta,
                    external_order_id,
                    f"crm:event:{event_id}",
                    f"CRM order {external_order_id}: delta {delta} kopecks",
                    json.dumps(
                        {
                            "event_id": event_id,
                            "event_version": event_version,
                            "old_amount_kopecks": old_amount,
                            "new_amount_kopecks": new_amount,
                            "delta_kopecks": delta,
                            "remainder_before_kopecks": remainder_before,
                            "remainder_after_kopecks": remainder_after,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        cur.execute(
            "UPDATE reward_accounts SET remainder_kopecks=%s,updated_at=now() WHERE customer_id=%s",
            (remainder_after, customer_id),
        )
        cur.execute(
            "UPDATE customers SET ruble_remainder=%s/100.0,updated_at=now() WHERE id=%s",
            (remainder_after, customer_id),
        )
        cur.execute(
            """
            INSERT INTO crm_orders(
                external_order_id,external_customer_id,customer_id,status,
                eligible_amount_kopecks,last_event_version,occurred_at,raw
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT(external_order_id) DO UPDATE SET
                external_customer_id=EXCLUDED.external_customer_id,
                customer_id=EXCLUDED.customer_id,
                status=EXCLUDED.status,
                eligible_amount_kopecks=EXCLUDED.eligible_amount_kopecks,
                last_event_version=EXCLUDED.last_event_version,
                occurred_at=EXCLUDED.occurred_at,
                raw=EXCLUDED.raw,
                updated_at=now()
            """,
            (
                external_order_id,
                external_customer_id,
                customer_id,
                status,
                new_amount,
                event_version,
                occurred_at,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        cur.execute(
            """
            INSERT INTO crm_events(
                event_id,event_type,event_version,external_order_id,customer_id,
                old_amount_kopecks,new_amount_kopecks,delta_kopecks,am_delta,
                remainder_before_kopecks,remainder_after_kopecks,payload
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            """,
            (
                event_id,
                event_type,
                event_version,
                external_order_id,
                customer_id,
                old_amount,
                new_amount,
                delta,
                am_delta,
                remainder_before,
                remainder_after,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        add_audit(
            cur,
            "crm",
            None,
            "crm_order_event_processed",
            "customer",
            customer_id,
            {
                "event_id": event_id,
                "external_order_id": external_order_id,
                "event_version": event_version,
                "delta_kopecks": delta,
                "am_delta": am_delta,
            },
        )
        result = event_response(cur, event_id, False)
        con.commit()
    return jsonify(ok=True, event=result), 201


@crm_bp.get("/api/client/orders")
def client_orders():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    limit = min(max(int(request.args.get("limit", "50")), 1), 100)
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT external_order_id,status,eligible_amount_kopecks,last_event_version,
                   occurred_at,created_at,updated_at
              FROM crm_orders
             WHERE customer_id=%s
             ORDER BY COALESCE(occurred_at,updated_at) DESC
             LIMIT %s
            """,
            (subject["id"], limit),
        )
        rows = cur.fetchall()
    return jsonify(orders=rows, source="crm", manual_creation=False)


@crm_bp.get("/api/admin/crm/orders")
def admin_crm_orders():
    ctx = admin_from_session("customer_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403
    customer_id = str(request.args.get("customer_id") or "").strip()
    limit = min(max(int(request.args.get("limit", "100")), 1), 500)
    with db() as con, con.cursor() as cur:
        if customer_id:
            cur.execute(
                """
                SELECT external_order_id,external_customer_id,customer_id,status,
                       eligible_amount_kopecks,last_event_version,occurred_at,updated_at
                  FROM crm_orders
                 WHERE customer_id=%s
                 ORDER BY COALESCE(occurred_at,updated_at) DESC LIMIT %s
                """,
                (customer_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT external_order_id,external_customer_id,customer_id,status,
                       eligible_amount_kopecks,last_event_version,occurred_at,updated_at
                  FROM crm_orders
                 ORDER BY COALESCE(occurred_at,updated_at) DESC LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()
    return jsonify(orders=rows, source="crm", manual_creation=False)
