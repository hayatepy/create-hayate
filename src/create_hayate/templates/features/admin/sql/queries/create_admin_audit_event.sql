-- name: create_admin_audit_event :exec
-- param: owner str
-- param: occurred_at str
-- param: phase str
-- param: action str
-- param: operation str?
-- param: resource str
-- param: object_id str?
-- param: actor_id str?
-- param: error_type str?
INSERT INTO admin_audit_events (
    owner,
    occurred_at,
    phase,
    action,
    operation,
    resource,
    object_id,
    actor_id,
    error_type
)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
