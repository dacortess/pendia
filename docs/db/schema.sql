-- Pendia — Schema PostgreSQL (MVP) — v3
-- Cambios respecto a v2: ver docs/adr/ADR-014 (invitación por código+QR) y
-- ADR-015 (monedas soportadas). v1→v2: ver ADR-013. Convención: snake_case,
-- PK bigserial, timestamps con timezone, soft-delete NO se usa (borrado
-- real + AuditLog cubre trazabilidad) salvo donde se indica.

CREATE TYPE membership_role AS ENUM ('owner', 'admin', 'member');

CREATE TYPE periodicity AS ENUM ('MONTHLY', 'BIMONTHLY', 'QUARTERLY', 'SEMIANNUAL', 'ANNUAL');

CREATE TYPE period_status AS ENUM ('PENDIENTE', 'PAGADO', 'VENCIDO');

CREATE TYPE payment_method_kind AS ENUM (
    'CASH', 'BANK_ACCOUNT', 'DIGITAL_WALLET', 'DEBIT_CARD', 'CREDIT_CARD', 'BRE_B', 'PSE', 'OTHER'
);

CREATE TYPE notification_event_type AS ENUM ('DUE_SOON', 'DUE_TODAY', 'OVERDUE');
CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'FAILED', 'SKIPPED');
CREATE TYPE notification_channel AS ENUM ('WHATSAPP', 'EMAIL');

-- v3 (ADR-015): moneda restringida a un catálogo cerrado, no ISO-4217 abierto.
CREATE TYPE supported_currency AS ENUM ('COP', 'USD');

CREATE TABLE users (
    id                  BIGSERIAL PRIMARY KEY,
    email               CITEXT NOT NULL UNIQUE,
    password_hash       TEXT NOT NULL,               -- Argon2id
    full_name           TEXT NOT NULL,
    phone_number        TEXT
        CHECK (phone_number IS NULL OR phone_number ~ '^\+[0-9]{8,15}$'),
    whatsapp_opt_in     BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id) WHERE revoked_at IS NULL;

CREATE TABLE groups (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    created_by      BIGINT NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- v3 (ADR-014): invitación a grupo por código alfanumérico (el QR solo
-- codifica una URL que contiene este mismo código; no se genera ni
-- almacena imagen, se sirve al vuelo desde un endpoint).
CREATE TABLE group_invite_codes (
    id                  BIGSERIAL PRIMARY KEY,
    group_id            BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    code                TEXT NOT NULL UNIQUE,          -- 8 caracteres, alfabeto sin ambigüedades (ADR-014)
    role_to_assign      membership_role NOT NULL DEFAULT 'member'
        CHECK (role_to_assign <> 'owner'),             -- un código nunca puede otorgar ownership
    created_by_user_id  BIGINT NOT NULL REFERENCES users(id),
    max_uses            SMALLINT,                       -- NULL = ilimitado (código familiar reutilizable)
    uses_count          INT NOT NULL DEFAULT 0,
    expires_at          TIMESTAMPTZ,                    -- NULL = sin expiración
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,  -- revocación manual sin borrar el registro (historial)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_uses_within_max CHECK (max_uses IS NULL OR uses_count <= max_uses)
);
CREATE INDEX idx_group_invite_codes_lookup ON group_invite_codes(code) WHERE is_active;

CREATE TABLE group_memberships (
    user_id                     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id                    BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    role                        membership_role NOT NULL,
    joined_via_invite_code_id   BIGINT REFERENCES group_invite_codes(id) ON DELETE SET NULL,  -- NULL = agregado directo por admin (email)
    joined_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, group_id)
);
CREATE UNIQUE INDEX uq_one_owner_per_group ON group_memberships(group_id) WHERE role = 'owner';

CREATE TABLE categories (
    id              BIGSERIAL PRIMARY KEY,
    group_id        BIGINT REFERENCES groups(id) ON DELETE CASCADE,  -- NULL = categoría del sistema
    name            TEXT NOT NULL,
    icon            TEXT,
    is_system       BOOLEAN NOT NULL GENERATED ALWAYS AS (group_id IS NULL) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_category_name_per_group ON categories(group_id, name) WHERE group_id IS NOT NULL;
CREATE UNIQUE INDEX uq_system_category_name ON categories(name) WHERE group_id IS NULL;

CREATE TABLE payment_methods (
    id              BIGSERIAL PRIMARY KEY,
    group_id        BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    kind            payment_method_kind NOT NULL,
    provider_name   TEXT NOT NULL,
    label           TEXT NOT NULL,
    last4           CHAR(4),
    masked_key      TEXT
        CHECK (masked_key IS NULL OR length(masked_key) <= 20),
    holder_name     TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- CRÍTICO: jamás agregar columnas de PAN completo, CVV, PIN ni credenciales bancarias.
    CONSTRAINT chk_payment_method_reference CHECK (
        (kind = 'CASH' AND last4 IS NULL AND masked_key IS NULL)
        OR (kind IN ('BANK_ACCOUNT', 'DEBIT_CARD', 'CREDIT_CARD') AND last4 IS NOT NULL)
        OR (kind IN ('DIGITAL_WALLET', 'BRE_B', 'PSE') AND masked_key IS NOT NULL)
        OR (kind = 'OTHER')
    )
);

CREATE TABLE obligations (
    id                      BIGSERIAL PRIMARY KEY,
    group_id                BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    category_id             BIGINT REFERENCES categories(id) ON DELETE SET NULL,
    payment_method_id       BIGINT REFERENCES payment_methods(id) ON DELETE SET NULL,
    responsible_user_id     BIGINT,

    name                    TEXT NOT NULL,
    provider_name           TEXT,
    external_reference      TEXT,
    notes                   TEXT,

    -- v3 (ADR-015): antes CHAR(3) libre, ahora catálogo cerrado COP/USD.
    currency                supported_currency NOT NULL DEFAULT 'COP',
    expected_amount_cents   BIGINT NOT NULL CHECK (expected_amount_cents >= 0),
    is_variable_amount      BOOLEAN NOT NULL DEFAULT FALSE,

    is_subscription         BOOLEAN NOT NULL DEFAULT FALSE,
    auto_debit              BOOLEAN NOT NULL DEFAULT FALSE,
    is_essential            BOOLEAN NOT NULL DEFAULT TRUE,

    periodicity             periodicity NOT NULL DEFAULT 'MONTHLY',
    due_day                 SMALLINT NOT NULL CHECK (due_day BETWEEN 1 AND 31),
    due_month               SMALLINT CHECK (due_month BETWEEN 1 AND 12),

    start_date              DATE NOT NULL,
    end_date                DATE,

    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    FOREIGN KEY (responsible_user_id, group_id)
        REFERENCES group_memberships(user_id, group_id) DEFERRABLE INITIALLY IMMEDIATE,

    CONSTRAINT chk_due_month_only_if_annual CHECK (
        (periodicity = 'ANNUAL' AND due_month IS NOT NULL)
        OR (periodicity <> 'ANNUAL' AND due_month IS NULL)
    ),
    CONSTRAINT chk_end_date_after_start CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE obligation_periods (
    id              BIGSERIAL PRIMARY KEY,
    obligation_id   BIGINT NOT NULL REFERENCES obligations(id) ON DELETE CASCADE,
    period_month    DATE NOT NULL,
    due_date        DATE NOT NULL,
    status          period_status NOT NULL DEFAULT 'PENDIENTE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (obligation_id, period_month)
);
CREATE INDEX idx_obligation_periods_status ON obligation_periods(status, due_date);

CREATE TABLE payments (
    id                          BIGSERIAL PRIMARY KEY,
    obligation_period_id        BIGINT NOT NULL REFERENCES obligation_periods(id) ON DELETE RESTRICT,
    registered_by_user_id       BIGINT NOT NULL REFERENCES users(id),
    amount_cents                BIGINT NOT NULL CHECK (amount_cents >= 0),
    currency                    supported_currency NOT NULL,   -- v3: antes CHAR(3) libre
    paid_at                     DATE NOT NULL,
    notes                       TEXT,
    receipt_url                 TEXT,
    voided_at                   TIMESTAMPTZ,
    voided_by_user_id           BIGINT REFERENCES users(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_payments_period ON payments(obligation_period_id) WHERE voided_at IS NULL;

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    group_id        BIGINT REFERENCES groups(id) ON DELETE SET NULL,
    actor_user_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       BIGINT NOT NULL,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_group_time ON audit_logs(group_id, created_at DESC);

-- ============================================================
-- Terreno preparado para alertas (ADR-012). No se activa ningún
-- envío en el MVP.
-- ============================================================

CREATE TABLE notification_rules (
    id                          BIGSERIAL PRIMARY KEY,
    group_id                    BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    obligation_id               BIGINT REFERENCES obligations(id) ON DELETE CASCADE,
    days_before_due             SMALLINT[] NOT NULL DEFAULT '{3,1}',
    notify_on_due_day           BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_overdue           BOOLEAN NOT NULL DEFAULT TRUE,
    overdue_repeat_every_days   SMALLINT,
    channel                     notification_channel NOT NULL DEFAULT 'WHATSAPP',
    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notification_rules_group ON notification_rules(group_id) WHERE is_active;

CREATE TABLE notification_events (
    id                      BIGSERIAL PRIMARY KEY,
    obligation_period_id    BIGINT NOT NULL REFERENCES obligation_periods(id) ON DELETE CASCADE,
    rule_id                 BIGINT REFERENCES notification_rules(id) ON DELETE SET NULL,
    event_type              notification_event_type NOT NULL,
    channel                 notification_channel NOT NULL DEFAULT 'WHATSAPP',
    scheduled_for           DATE NOT NULL,
    status                  notification_status NOT NULL DEFAULT 'PENDING',
    sent_at                 TIMESTAMPTZ,
    error_detail            TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (obligation_period_id, event_type, scheduled_for)
);
CREATE INDEX idx_notification_events_pending ON notification_events(status, scheduled_for) WHERE status = 'PENDING';

-- Extensión requerida para CITEXT (email case-insensitive):
-- CREATE EXTENSION IF NOT EXISTS citext;
