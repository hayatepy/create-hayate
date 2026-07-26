-- name: list_todos :many
-- param: owner str
-- column: id str
-- column: title str
-- column: done int
SELECT id, title, done
FROM todos
WHERE owner = ?1
ORDER BY rowid ASC
