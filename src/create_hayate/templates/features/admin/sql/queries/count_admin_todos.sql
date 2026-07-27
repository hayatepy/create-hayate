-- name: count_admin_todos :one
-- param: owner str
-- param: search str
-- column: total int
SELECT COUNT(*) AS total
FROM todos
WHERE owner = ?1
  AND (?2 = '' OR instr(lower(title), lower(?2)) > 0)
