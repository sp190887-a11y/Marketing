import re

from flask import Blueprint, jsonify, request

from .index import add_audit, admin_from_session, db, norm_phone

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
            SELECT code,name,is_active,sort_order
              FROM club_managers
             WHERE is_active=true
             ORDER BY sort_order,code
            """
        )
        rows = cur.fetchall()
    return jsonify(managers=rows)


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
