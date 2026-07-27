-- name: list_admin_todos_title_asc :many
-- param: owner str
-- param: search str
-- param: limit int
-- param: offset int
-- column: id str
-- column: title str
-- column: done int
SELECT id, title, done
FROM todos
WHERE owner = ?1
  AND (?2 = '' OR instr(lower(title), lower(?2)) > 0)
ORDER BY lower(title) ASC, id ASC
LIMIT ?3 OFFSET ?4
