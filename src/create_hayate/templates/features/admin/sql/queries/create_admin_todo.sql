-- name: create_admin_todo :one
-- param: todo_id str
-- param: owner str
-- param: title str
-- param: done bool
-- column: id str
-- column: title str
-- column: done int
INSERT INTO todos (id, owner, title, done)
VALUES (?1, ?2, ?3, ?4)
RETURNING id, title, done
