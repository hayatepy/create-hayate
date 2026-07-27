-- name: update_todo :exec
-- param: owner str
-- param: todo_id str
-- param: title str
UPDATE todos
SET title = ?3
WHERE owner = ?1 AND id = ?2
