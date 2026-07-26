-- name: get_todo :one?
-- param: owner str
-- param: todo_id str
-- column: id str
-- column: title str
-- column: done int
SELECT id, title, done
FROM todos
WHERE owner = ?1 AND id = ?2
