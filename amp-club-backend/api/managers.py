import re

from flask import Blueprint, jsonify, request

from .index import add_audit, admin_from_session, db, norm_phone, session_subject

manager_bp = Blueprint("client_managers", __name__)


def club_code(manager_code, member_no):
    return f"A{int(manager_code)}-{int(member_no):05d}"


@manager_bp.get("/api/admin/managers")
def list_managers():
    ctx = admin_from_session("customer_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT code,name,phone,email,telegram_url,vk_url,max_url,is_active,sort_order
              FROM club_managers
             WHERE is_active=true
             ORDER BY sort_order,code
            """
        )
        rows = cur.fetchall()
    return jsonify(managers=rows)


def _clean_contact_url(value):
    value = str(value or "").strip()
    if not value:
        return None
    if len(value) > 500 or not re.match(r"^https://", value, re.I):
        raise ValueError("invalid_contact_url")
    return value


def _clean_email(value):
    value = str(value or "").strip().lower()
    if not value:
        return None
    if len(value) > 254 or not re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", value):
        raise ValueError("invalid_email")
    return value


def _clean_phone(value):
    value = str(value or "").strip()
    if not value:
        return None
    if len(value) > 40 or not re.fullmatch(r"[+0-9() .-]{5,40}", value):
        raise ValueError("invalid_contact_phone")
    return value


@manager_bp.patch("/api/admin/managers/<int:code>")
def update_manager_contacts(code):
    ctx = admin_from_session()
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["admin"].get("role") != "owner":
        return jsonify(error="forbidden"), 403

    data = request.get_json(silent=True) or {}
    try:
        phone = _clean_phone(data.get("phone")) if "phone" in data else None
        email = _clean_email(data.get("email")) if "email" in data else None
        telegram_url = _clean_contact_url(data.get("telegram_url")) if "telegram_url" in data else None
        vk_url = _clean_contact_url(data.get("vk_url")) if "vk_url" in data else None
        max_url = _clean_contact_url(data.get("max_url")) if "max_url" in data else None
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT * FROM club_managers WHERE code=%s FOR UPDATE", (code,))
        before = cur.fetchone()
        if not before:
            return jsonify(error="manager_not_found"), 404
        fields = []
        params = []
        for key, value in (
            ("phone", phone), ("email", email), ("telegram_url", telegram_url),
            ("vk_url", vk_url), ("max_url", max_url),
        ):
            if key in data:
                fields.append(f"{key}=%s")
                params.append(value)
        if not fields:
            return jsonify(error="nothing_to_update"), 400
        params.append(code)
        cur.execute(
            f"UPDATE club_managers SET {', '.join(fields)},updated_at=now() WHERE code=%s RETURNING code,name,phone,email,telegram_url,vk_url,max_url,is_active,sort_order",
            tuple(params),
        )
        manager = cur.fetchone()
        add_audit(cur, "admin", ctx["admin"]["id"], "manager_contacts_updated", "club_manager", str(code), {"fields": [x.split("=")[0] for x in fields]})
        con.commit()
    return jsonify(ok=True, manager=manager)


@manager_bp.get("/api/client/manager")
def client_manager():
    subject = session_subject("client")
    if not subject:
        return jsonify(error="unauthorized"), 401
    with db() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT i.club_member_no,i.club_code,i.manager_code,i.manager_name,
                   i.manager_phone,i.manager_email,i.manager_telegram_url,
                   i.manager_vk_url,i.manager_max_url,i.manager_active
              FROM customer_club_identity i
             WHERE i.customer_id=%s
            """,
            (subject["id"],),
        )
        row = cur.fetchone()
    if not row:
        return jsonify(error="not_found"), 404
    assigned = int(row["manager_code"]) != 0 and bool(row["manager_active"])
    return jsonify(
        assigned=assigned,
        club_member_no=row["club_member_no"],
        club_code=row["club_code"],
        manager=None if not assigned else {
            "code": row["manager_code"],
            "name": row["manager_name"],
            "phone": row["manager_phone"],
            "email": row["manager_email"],
            "telegram_url": row["manager_telegram_url"],
            "vk_url": row["manager_vk_url"],
            "max_url": row["manager_max_url"],
        },
    )


@manager_bp.post("/api/admin/customers/<customer_id>/manager")
def assign_manager(customer_id):
    ctx = admin_from_session("manager_assign")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403

    data = request.get_json(silent=True) or {}
    try:
        new_code = int(data.get("manager_code"))
    except (TypeError, ValueError):
        return jsonify(error="invalid_manager_code"), 400
    reason = str(data.get("reason") or "").strip()[:500]

    with db() as con, con.cursor() as cur:
        cur.execute(
            "SELECT code,name,is_active FROM club_managers WHERE code=%s",
            (new_code,),
        )
        manager = cur.fetchone()
        if not manager or not manager["is_active"]:
            return jsonify(error="manager_not_found"), 404

        cur.execute(
            """
            SELECT id,manager_code,club_member_no
              FROM customers
             WHERE id=%s AND is_active=true
             FOR UPDATE
            """,
            (customer_id,),
        )
        customer = cur.fetchone()
        if not customer:
            return jsonify(error="not_found"), 404

        old_code = int(customer["manager_code"])
        member_no = int(customer["club_member_no"])
        if old_code == new_code:
            return jsonify(
                ok=True,
                changed=False,
                manager=manager,
                club_member_no=member_no,
                club_code=club_code(new_code, member_no),
            )

        cur.execute(
            "UPDATE customers SET manager_code=%s,updated_at=now() WHERE id=%s",
            (new_code, customer_id),
        )
        cur.execute(
            """
            INSERT INTO customer_manager_history(
                customer_id,old_manager_code,new_manager_code,actor_admin_id,reason
            ) VALUES (%s,%s,%s,%s,%s)
            RETURNING id,created_at
            """,
            (customer_id, old_code, new_code, ctx["admin"]["id"], reason or None),
        )
        history = cur.fetchone()

        if old_code == 0 and new_code != 0:
            action = "manager_assigned"
        elif new_code == 0:
            action = "manager_unassigned"
        else:
            action = "manager_changed"
        add_audit(
            cur,
            "admin",
            ctx["admin"]["id"],
            action,
            "customer",
            customer_id,
            {
                "old_manager_code": old_code,
                "new_manager_code": new_code,
                "old_club_code": club_code(old_code, member_no),
                "new_club_code": club_code(new_code, member_no),
                "reason": reason or None,
            },
        )
        con.commit()

    return jsonify(
        ok=True,
        changed=True,
        manager=manager,
        club_member_no=member_no,
        club_code=club_code(new_code, member_no),
        history=history,
    )


@manager_bp.get("/api/admin/customers/<customer_id>/manager-history")
def manager_history(customer_id):
    ctx = admin_from_session("customer_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403

    with db() as con, con.cursor() as cur:
        cur.execute("SELECT 1 FROM customers WHERE id=%s", (customer_id,))
        if not cur.fetchone():
            return jsonify(error="not_found"), 404
        cur.execute(
            """
            SELECT h.id,h.old_manager_code,h.new_manager_code,
                   oldm.name AS old_manager_name,newm.name AS new_manager_name,
                   h.reason,h.created_at,
                   a.login AS actor_login,a.display_name AS actor_name
              FROM customer_manager_history h
              LEFT JOIN club_managers oldm ON oldm.code=h.old_manager_code
              JOIN club_managers newm ON newm.code=h.new_manager_code
              LEFT JOIN admin_users a ON a.id=h.actor_admin_id
             WHERE h.customer_id=%s
             ORDER BY h.created_at DESC,h.id DESC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()
    return jsonify(history=rows)


@manager_bp.get("/api/admin/customer-lookup")
def customer_lookup():
    ctx = admin_from_session("customer_read")
    if not ctx:
        return jsonify(error="unauthorized"), 401
    if ctx["forbidden"]:
        return jsonify(error="forbidden"), 403

    q = str(request.args.get("q") or "").strip()
    if not q:
        return jsonify(customers=[])

    manager_code = None
    member_no = None
    code_match = re.fullmatch(r"[Aa](\d{1,2})-(\d+)", q)
    if code_match:
        manager_code = int(code_match.group(1))
        member_no = int(code_match.group(2))

    try:
        phone = norm_phone(q)
    except ValueError:
        phone = None

    numeric_member = int(q) if q.isdigit() else None

    with db() as con, con.cursor() as cur:
        if manager_code is not None:
            cur.execute(
                """
                SELECT c.id,c.phone,c.name,c.crm_number,c.club_member_no,c.manager_code,
                       i.club_code,i.manager_name,c.balance_am,c.discount_percent,c.is_active
                  FROM customers c
                  JOIN customer_club_identity i ON i.customer_id=c.id
                 WHERE c.manager_code=%s AND c.club_member_no=%s
                 LIMIT 20
                """,
                (manager_code, member_no),
            )
        else:
            conditions = ["lower(c.name) LIKE lower(%s)", "c.crm_number=%s"]
            params = ["%" + q + "%", q]
            if phone:
                conditions.append("c.phone=%s")
                params.append(phone)
            if numeric_member is not None:
                conditions.append("c.club_member_no=%s")
                params.append(numeric_member)
            cur.execute(
                f"""
                SELECT c.id,c.phone,c.name,c.crm_number,c.club_member_no,c.manager_code,
                       i.club_code,i.manager_name,c.balance_am,c.discount_percent,c.is_active
                  FROM customers c
                  JOIN customer_club_identity i ON i.customer_id=c.id
                 WHERE {" OR ".join(conditions)}
                 ORDER BY c.created_at DESC
                 LIMIT 20
                """,
                tuple(params),
            )
        rows = cur.fetchall()
    return jsonify(customers=rows)
