CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE agent_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES projects(id),
    agent_name  TEXT NOT NULL,
    input       TEXT,
    output      TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tasks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID REFERENCES projects(id),
    title        TEXT NOT NULL,
    status       TEXT DEFAULT 'backlog',
    ai_generated BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT NOW()
);
