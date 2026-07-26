-- name: create_todo :exec
-- param: todo_id str
-- param: owner str
-- param: title str
INSERT INTO todos (id, owner, title, done)
VALUES (?1, ?2, ?3, 0)
