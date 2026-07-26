-- name: delete_todo :exec
-- param: owner str
-- param: todo_id str
DELETE FROM todos
WHERE owner = ?1 AND id = ?2
