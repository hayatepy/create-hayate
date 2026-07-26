CREATE TABLE todos (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
);

CREATE INDEX todos_owner_id_idx ON todos (owner, id);
