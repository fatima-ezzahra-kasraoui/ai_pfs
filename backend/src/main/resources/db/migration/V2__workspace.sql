CREATE TABLE workspace_conversations (
 id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title VARCHAR(100) NOT NULL DEFAULT 'New conversation', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 archived BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX workspace_owner_idx ON workspace_conversations(owner_id, created_at DESC);
CREATE TABLE workspace_runs (
 id UUID PRIMARY KEY, conversation_id UUID NOT NULL REFERENCES workspace_conversations(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ,
 status VARCHAR(20) NOT NULL CHECK(status IN ('RUNNING','COMPLETED','FAILED','REVIEW_REQUIRED')),
 user_text TEXT NOT NULL DEFAULT '[Message not retained]', result_json TEXT,
 final_decision VARCHAR(10), correlation_id VARCHAR(128) NOT NULL UNIQUE
);
CREATE UNIQUE INDEX workspace_one_running ON workspace_runs(conversation_id) WHERE status='RUNNING';
