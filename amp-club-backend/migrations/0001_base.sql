CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS customers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone varchar(10) NOT NULL UNIQUE CHECK (phone ~ '^[0-9]{10}$'),
    name text NOT NULL DEFAULT '',
    birth_date date,
    gender varchar(16) CHECK (gender IN ('male','female') OR gender IS NULL),
    discount_percent numeric NOT NULL DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent <= 100),
    balance_am bigint NOT NULL DEFAULT 0,
    ruble_remainder numeric NOT NULL DEFAULT 0,
    crm_number text UNIQUE,
    pin_salt text,
    pin_hash text,
    telegram_linked boolean NOT NULL DEFAULT false,
    max_linked boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    login text NOT NULL UNIQUE,
    display_name text NOT NULL DEFAULT '',
    password_salt text NOT NULL,
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type varchar(16) NOT NULL CHECK (subject_type IN ('client','admin')),
    subject_id uuid NOT NULL,
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS auth_sessions_subject_idx ON auth_sessions(subject_type, subject_id, expires_at);

CREATE TABLE IF NOT EXISTS verification_codes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone varchar(10) NOT NULL,
    purpose varchar(32) NOT NULL CHECK (purpose IN ('register','recover_pin')),
    channel varchar(32) NOT NULL CHECK (channel IN ('test','sms','telegram','max')),
    code_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS verification_codes_phone_idx ON verification_codes(phone, purpose, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_log (
    id bigserial PRIMARY KEY,
    actor_type varchar(32) NOT NULL,
    actor_id uuid,
    action text NOT NULL,
    target_type text,
    target_id text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
