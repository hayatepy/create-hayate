-- name: list_admin_audit_events :many
-- param: owner str
-- param: resource str
-- param: object_id str
-- param: limit int
-- param: offset int
-- column: occurred_at str
-- column: phase str
-- column: action str
-- column: operation str?
-- column: resource str
-- column: object_id str?
-- column: actor_id str?
-- column: error_type str?
SELECT occurred_at, phase, action, operation, resource, object_id, actor_id, error_type
FROM admin_audit_events
WHERE owner = ?1 AND resource = ?2 AND object_id = ?3
ORDER BY id DESC
LIMIT ?4 OFFSET ?5
