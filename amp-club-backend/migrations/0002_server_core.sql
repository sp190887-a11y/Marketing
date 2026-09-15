ALTER TABLE customers ADD COLUMN IF NOT EXISTS failed_pin_attempts integer NOT NULL DEFAULT 0;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS pin_locked_until timestamptz;

ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS role varchar(32) NOT NULL DEFAULT 'operator';
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS permissions jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS failed_login_attempts integer NOT NULL DEFAULT 0;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS locked_until timestamptz;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS mfa_required boolean NOT NULL DEFAULT false;
DO $$ BEGIN
    ALTER TABLE admin_users ADD CONSTRAINT admin_users_role_check CHECK (role IN ('owner','manager','operator','auditor'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS ip_address inet;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS user_agent text;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS last_seen_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE verification_codes ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE verification_codes ADD COLUMN IF NOT EXISTS request_ip inet;
ALTER TABLE verification_codes ADD COLUMN IF NOT EXISTS user_agent text;
ALTER TABLE verification_codes ADD COLUMN IF NOT EXISTS sent_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS document_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type text NOT NULL,
    version text NOT NULL,
    title text NOT NULL,
    public_path text NOT NULL,
    is_current boolean NOT NULL DEFAULT false,
    effective_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(doc_type, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS document_versions_one_current_idx
    ON document_versions(doc_type) WHERE is_current;

INSERT INTO document_versions(doc_type,version,title,public_path,is_current,effective_at)
VALUES
('privacy','2026-09-15','Политика обработки персональных данных','/legal/privacy.html',true,'2026-09-15T00:00:00+03'),
('personal_data','2026-09-15','Согласие на обработку персональных данных','/legal/personal-data-consent.html',true,'2026-09-15T00:00:00+03'),
('marketing','2026-09-15','Согласие на рекламные и информационные сообщения','/legal/marketing-consent.html',true,'2026-09-15T00:00:00+03'),
('club_rules','2026-09-15','Правила АМ Клуба','/legal/club-rules.html',true,'2026-09-15T00:00:00+03'),
('cookies','2026-09-15','Правила использования технических данных','/legal/cookies.html',true,'2026-09-15T00:00:00+03')
ON CONFLICT(doc_type,version) DO UPDATE SET
    title=EXCLUDED.title,
    public_path=EXCLUDED.public_path,
    is_current=EXCLUDED.is_current,
    effective_at=EXCLUDED.effective_at;

CREATE TABLE IF NOT EXISTS consent_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES customers(id),
    consent_type text NOT NULL,
    action varchar(16) NOT NULL CHECK (action IN ('grant','revoke','decline')),
    document_version text NOT NULL,
    source varchar(32) NOT NULL DEFAULT 'web',
    ip_address inet,
    user_agent text,
    session_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS consent_ledger_customer_idx ON consent_ledger(customer_id, consent_type, created_at DESC);

CREATE TABLE IF NOT EXISTS am_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES customers(id),
    amount bigint NOT NULL CHECK (amount <> 0),
    operation_type text NOT NULL,
    source_type text NOT NULL,
    source_id text,
    idempotency_key text NOT NULL UNIQUE,
    reason text,
    actor_type varchar(32) NOT NULL DEFAULT 'system',
    actor_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS am_ledger_customer_idx ON am_ledger(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS am_ledger_source_idx ON am_ledger(source_type, source_id);

CREATE TABLE IF NOT EXISTS support_tickets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid REFERENCES customers(id),
    channel varchar(32) NOT NULL DEFAULT 'club',
    subject text NOT NULL DEFAULT 'Обращение в поддержку',
    message text NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'new' CHECK (status IN ('new','in_progress','resolved','closed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS support_tickets_customer_idx ON support_tickets(customer_id, created_at DESC);

CREATE OR REPLACE FUNCTION amp_deny_immutable_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'immutable_table';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS consent_ledger_immutable ON consent_ledger;
CREATE TRIGGER consent_ledger_immutable
BEFORE UPDATE OR DELETE ON consent_ledger
FOR EACH ROW EXECUTE FUNCTION amp_deny_immutable_mutation();

DROP TRIGGER IF EXISTS am_ledger_immutable ON am_ledger;
CREATE TRIGGER am_ledger_immutable
BEFORE UPDATE OR DELETE ON am_ledger
FOR EACH ROW EXECUTE FUNCTION amp_deny_immutable_mutation();

CREATE OR REPLACE FUNCTION amp_protect_customer_balance() RETURNS trigger AS $$
BEGIN
    IF NEW.balance_am IS DISTINCT FROM OLD.balance_am
       AND COALESCE(current_setting('amp.ledger_balance_write', true),'off') <> 'on' THEN
        RAISE EXCEPTION 'balance_must_be_changed_through_ledger';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS customers_balance_guard ON customers;
CREATE TRIGGER customers_balance_guard
BEFORE UPDATE OF balance_am ON customers
FOR EACH ROW EXECUTE FUNCTION amp_protect_customer_balance();

CREATE OR REPLACE FUNCTION amp_apply_ledger_balance() RETURNS trigger AS $$
BEGIN
    PERFORM set_config('amp.ledger_balance_write','on',true);
    UPDATE customers
       SET balance_am = balance_am + NEW.amount,
           updated_at = now()
     WHERE id = NEW.customer_id;
    PERFORM set_config('amp.ledger_balance_write','off',true);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS am_ledger_apply_balance ON am_ledger;
CREATE TRIGGER am_ledger_apply_balance
AFTER INSERT ON am_ledger
FOR EACH ROW EXECUTE FUNCTION amp_apply_ledger_balance();

CREATE OR REPLACE VIEW customer_ledger_balances AS
SELECT c.id AS customer_id,
       c.balance_am AS cached_balance_am,
       COALESCE(SUM(l.amount),0)::bigint AS ledger_balance_am,
       (c.balance_am = COALESCE(SUM(l.amount),0)::bigint) AS is_consistent
FROM customers c
LEFT JOIN am_ledger l ON l.customer_id=c.id
GROUP BY c.id,c.balance_am;

CREATE OR REPLACE VIEW current_consents AS
SELECT DISTINCT ON (customer_id, consent_type)
       customer_id, consent_type, action, document_version, source, created_at
FROM consent_ledger
ORDER BY customer_id, consent_type, created_at DESC, id DESC;
