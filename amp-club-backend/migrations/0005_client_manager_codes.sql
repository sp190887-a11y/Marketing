CREATE SEQUENCE IF NOT EXISTS club_member_number_seq START WITH 1;

CREATE TABLE IF NOT EXISTS club_managers (
    code smallint PRIMARY KEY CHECK (code >= 0 AND code <= 99),
    name text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO club_managers(code,name,is_active,sort_order)
VALUES
(0,'Не закреплён',true,0),
(1,'Настя',true,1),
(2,'Ирина',true,2),
(3,'Алёна',true,3)
ON CONFLICT(code) DO UPDATE SET
    name=EXCLUDED.name,
    is_active=EXCLUDED.is_active,
    sort_order=EXCLUDED.sort_order,
    updated_at=now();

ALTER TABLE customers ADD COLUMN IF NOT EXISTS club_member_no bigint;
UPDATE customers
   SET club_member_no = nextval('club_member_number_seq')
 WHERE club_member_no IS NULL;
ALTER TABLE customers ALTER COLUMN club_member_no SET DEFAULT nextval('club_member_number_seq');
ALTER TABLE customers ALTER COLUMN club_member_no SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS customers_club_member_no_uidx ON customers(club_member_no);

ALTER TABLE customers ADD COLUMN IF NOT EXISTS manager_code smallint NOT NULL DEFAULT 0;
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_manager_code_fkey;
ALTER TABLE customers ADD CONSTRAINT customers_manager_code_fkey
    FOREIGN KEY (manager_code) REFERENCES club_managers(code);

CREATE TABLE IF NOT EXISTS customer_manager_history (
    id bigserial PRIMARY KEY,
    customer_id uuid NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    old_manager_code smallint REFERENCES club_managers(code),
    new_manager_code smallint NOT NULL REFERENCES club_managers(code),
    actor_admin_id uuid REFERENCES admin_users(id),
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS customer_manager_history_customer_idx
    ON customer_manager_history(customer_id, created_at DESC);

CREATE OR REPLACE VIEW customer_club_identity AS
SELECT
    c.id AS customer_id,
    c.club_member_no,
    c.manager_code,
    ('A' || c.manager_code::text || '-' || lpad(c.club_member_no::text,5,'0')) AS club_code,
    m.name AS manager_name,
    m.is_active AS manager_active
FROM customers c
JOIN club_managers m ON m.code=c.manager_code;
