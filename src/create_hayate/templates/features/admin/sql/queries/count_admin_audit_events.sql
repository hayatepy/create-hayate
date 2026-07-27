-- name: count_admin_audit_events :one
-- param: owner str
-- param: resource str
-- param: object_id str
-- column: total int
SELECT COUNT(*) AS total
FROM admin_audit_events
WHERE owner = ?1 AND resource = ?2 AND object_id = ?3
