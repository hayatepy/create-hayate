-- name: list_admin_todos_cursor_title_asc :many
-- param: owner str
-- param: search str
-- param: cursor_id str
-- param: cursor_title str
-- param: limit int
-- column: id str
-- column: title str
-- column: done int
-- column: cursor_title str
SELECT id, title, done, lower(title) AS cursor_title
FROM todos
WHERE owner = ?1
  AND (?2 = '' OR instr(lower(title), lower(?2)) > 0)
  AND (
    ?3 = ''
    OR lower(title) > ?4
    OR (lower(title) = ?4 AND id > ?3)
  )
ORDER BY lower(title), id
LIMIT ?5
