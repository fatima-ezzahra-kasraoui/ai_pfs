-- AS-S1-016 : schema initial AgentShield AI (PostgreSQL 16).
-- Les valeurs d'enumeration sont verifiees par des contraintes CHECK : la base refuse toute valeur hors contrat
-- (docs/contract/openapi-public.yaml). Aucune donnee sensible en clair : `events.excerpt` est stocke deja MASQUE.

CREATE TABLE users (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(100) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,          -- hash BCrypt, jamais le mot de passe
    role          VARCHAR(20)  NOT NULL,
    email         VARCHAR(255),
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT ck_users_role CHECK (role IN ('ANALYST', 'APPROVER', 'ADMIN'))
);

CREATE TABLE simulations (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id  VARCHAR(40)  NOT NULL,
    status       VARCHAR(20)  NOT NULL,
    created_by   UUID         REFERENCES users (id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error        VARCHAR(200),                    -- message generique si FAILED, sans detail interne
    result_json  TEXT,                            -- resultats des executions sans / avec protection (JSON)
    CONSTRAINT ck_simulations_status
        CHECK (status IN ('SUBMITTED', 'RUNNING', 'AWAITING_APPROVAL', 'COMPLETED', 'FAILED'))
);
CREATE INDEX idx_simulations_created_at ON simulations (created_at DESC);

CREATE TABLE events (
    id             UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at    TIMESTAMPTZ      NOT NULL DEFAULT now(),
    module         VARCHAR(10)      NOT NULL,
    attack_type    VARCHAR(30)      NOT NULL,
    decision       VARCHAR(10)      NOT NULL,
    risk_level     VARCHAR(10)      NOT NULL,
    score          DOUBLE PRECISION NOT NULL,
    reason         TEXT             NOT NULL,
    correlation_id VARCHAR(128),
    simulation_id  UUID             REFERENCES simulations (id) ON DELETE SET NULL,
    tool_name      VARCHAR(100),
    excerpt        TEXT,                          -- extrait MASQUE du contenu analyse (jamais le contenu brut)
    CONSTRAINT ck_events_module CHECK (module IN ('A', 'B', 'C', 'D', 'ENGINE')),
    CONSTRAINT ck_events_attack_type
        CHECK (attack_type IN ('direct_injection', 'indirect_injection', 'data_leak', 'tool_abuse', 'none')),
    CONSTRAINT ck_events_decision CHECK (decision IN ('ALLOW', 'SANITIZE', 'CONFIRM', 'BLOCK')),
    CONSTRAINT ck_events_risk_level CHECK (risk_level IN ('low', 'medium', 'high')),
    CONSTRAINT ck_events_score CHECK (score >= 0 AND score <= 1)
);
CREATE INDEX idx_events_occurred_at ON events (occurred_at DESC);
CREATE INDEX idx_events_decision    ON events (decision);
CREATE INDEX idx_events_module      ON events (module);

CREATE TABLE approvals (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    status          VARCHAR(10)  NOT NULL,
    tool_name       VARCHAR(100) NOT NULL,
    parameters_json TEXT,                         -- parametres de l'appel d'outil (masques selon le role a l'affichage)
    parameters_hash VARCHAR(64)  NOT NULL,        -- SHA-256 des parametres exacts soumis a validation
    risk_level      VARCHAR(10)  NOT NULL,
    reason          TEXT         NOT NULL,
    simulation_id   UUID         REFERENCES simulations (id) ON DELETE SET NULL,
    event_id        UUID         REFERENCES events (id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ  NOT NULL,
    decided_by      UUID         REFERENCES users (id) ON DELETE SET NULL,
    decided_at      TIMESTAMPTZ,
    decision_comment VARCHAR(500),
    CONSTRAINT ck_approvals_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    CONSTRAINT ck_approvals_risk_level CHECK (risk_level IN ('low', 'medium', 'high'))
);
CREATE INDEX idx_approvals_status ON approvals (status, created_at DESC);
