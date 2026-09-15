CREATE TABLE IF NOT EXISTS reward_accounts (
    customer_id uuid PRIMARY KEY REFERENCES customers(id),
    remainder_kopecks bigint NOT NULL DEFAULT 0 CHECK (remainder_kopecks >= 0 AND remainder_kopecks < 10000),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crm_customer_links (
    external_customer_id text PRIMARY KEY,
    customer_id uuid NOT NULL REFERENCES customers(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crm_customer_links_customer_idx ON crm_customer_links(customer_id);

CREATE TABLE IF NOT EXISTS crm_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_order_id text NOT NULL UNIQUE,
    external_customer_id text NOT NULL,
    customer_id uuid NOT NULL REFERENCES customers(id),
    status text NOT NULL DEFAULT 'unknown',
    eligible_amount_kopecks bigint NOT NULL DEFAULT 0 CHECK (eligible_amount_kopecks >= 0),
    last_event_version bigint NOT NULL DEFAULT 0,
    occurred_at timestamptz,
    raw jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crm_orders_customer_idx ON crm_orders(customer_id, occurred_at DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS crm_orders_external_customer_idx ON crm_orders(external_customer_id);

CREATE TABLE IF NOT EXISTS crm_events (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    event_version bigint NOT NULL,
    external_order_id text NOT NULL,
    customer_id uuid NOT NULL REFERENCES customers(id),
    old_amount_kopecks bigint NOT NULL,
    new_amount_kopecks bigint NOT NULL,
    delta_kopecks bigint NOT NULL,
    am_delta bigint NOT NULL,
    remainder_before_kopecks bigint NOT NULL,
    remainder_after_kopecks bigint NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    processed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crm_events_customer_idx ON crm_events(customer_id, processed_at DESC);
CREATE INDEX IF NOT EXISTS crm_events_order_idx ON crm_events(external_order_id, event_version DESC);

CREATE OR REPLACE RULE crm_events_no_update AS
ON UPDATE TO crm_events DO INSTEAD NOTHING;
CREATE OR REPLACE RULE crm_events_no_delete AS
ON DELETE TO crm_events DO INSTEAD NOTHING;
