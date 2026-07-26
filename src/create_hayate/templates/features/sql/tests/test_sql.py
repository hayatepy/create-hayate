import sqlite3
from pathlib import Path

from hayate_sql.__main__ import main as hayate_sql_main


def test_queries_compile_against_the_complete_migration_history():
    root = Path(__file__).resolve().parents[1]
    assert (
        hayate_sql_main(
            [
                "check",
                str(root / "sql" / "queries"),
                "--dialect",
                "d1",
                "--migrations",
                str(root / "migrations"),
            ]
        )
        == 0
    )


def test_local_bootstrap_migration_is_safe_across_process_restarts():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations" / "0001_create_todos.sql").read_text(encoding="utf-8")
    database = sqlite3.connect(":memory:")

    database.executescript(migration)
    database.executescript(migration)
