CREATE TABLE IF NOT EXISTS admin_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN ('attempt', 'success', 'failure')),
    action TEXT NOT NULL,
    operation TEXT,
    resource TEXT NOT NULL,
    object_id TEXT,
    actor_id TEXT,
    error_type TEXT
);

CREATE INDEX IF NOT EXISTS admin_audit_events_object_idx
ON admin_audit_events (owner, resource, object_id, id DESC);
