-- name: update_admin_todo :one?
-- param: owner str
-- param: todo_id str
-- param: title str
-- param: done bool
-- column: id str
-- column: title str
-- column: done int
UPDATE todos
SET title = ?3, done = ?4
WHERE owner = ?1 AND id = ?2
RETURNING id, title, done
