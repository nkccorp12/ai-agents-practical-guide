-- Schema for the tool-agent reference (customer-support agent).
-- Run once: psql "$DATABASE_URL" -f schema.sql

CREATE TABLE IF NOT EXISTS orders (
    id          UUID PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    total_usd   NUMERIC(10, 2) NOT NULL,
    status      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS refunds (
    id           UUID PRIMARY KEY,
    order_id     UUID NOT NULL REFERENCES orders(id),
    tenant_id    TEXT NOT NULL,
    amount       NUMERIC(10, 2) NOT NULL,
    reason       TEXT NOT NULL,
    approved_by  TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pending_approvals (
    token            TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL,
    tenant_id        TEXT NOT NULL,
    requested_by     TEXT NOT NULL,
    tool_use_id      TEXT NOT NULL,
    tool             TEXT NOT NULL,
    args             JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escalations (
    id          UUID PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    reason      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         UUID PRIMARY KEY,
    ts         TIMESTAMPTZ NOT NULL,
    tenant_id  TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    role       TEXT NOT NULL,
    tool       TEXT NOT NULL,
    args_hash  TEXT NOT NULL,
    status     TEXT NOT NULL,
    result     TEXT,
    trace_id   TEXT NOT NULL
);

-- Row-Level-Security: each statement is restricted to the tenant in app.tenant_id.
ALTER TABLE orders            ENABLE ROW LEVEL SECURITY;
ALTER TABLE refunds           ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE pending_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations       ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log         ENABLE ROW LEVEL SECURITY;

CREATE POLICY orders_tenant            ON orders            USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY refunds_tenant           ON refunds           USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY conversations_tenant     ON conversations     USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY pending_approvals_tenant ON pending_approvals USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY escalations_tenant       ON escalations       USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY audit_log_tenant         ON audit_log         USING (tenant_id = current_setting('app.tenant_id', true));
