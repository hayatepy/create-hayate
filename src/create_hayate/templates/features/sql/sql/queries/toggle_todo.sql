-- name: toggle_todo :exec
-- param: owner str
-- param: todo_id str
UPDATE todos
SET done = CASE done WHEN 0 THEN 1 ELSE 0 END
WHERE owner = ?1 AND id = ?2
