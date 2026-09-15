ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS mfa_secret_encrypted text;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS mfa_pending_secret_encrypted text;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS mfa_enabled_at timestamptz;

CREATE TABLE IF NOT EXISTS admin_auth_challenges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id uuid NOT NULL REFERENCES admin_users(id),
    purpose varchar(32) NOT NULL CHECK (purpose IN ('mfa_setup')),
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    ip_address inet,
    user_agent text,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_auth_challenges_admin_idx
    ON admin_auth_challenges(admin_id, purpose, created_at DESC);

CREATE TABLE IF NOT EXISTS admin_mfa_recovery_codes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id uuid NOT NULL REFERENCES admin_users(id),
    code_hash text NOT NULL UNIQUE,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_mfa_recovery_codes_admin_idx
    ON admin_mfa_recovery_codes(admin_id, used_at);
