"""Check SQL contracts against migrations and keep the typed facade synchronized."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from hayate_sql.__main__ import main as hayate_sql_main

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "sql" / "queries"
MIGRATIONS = ROOT / "migrations"
GENERATED = ROOT / "src" / "queries.py"


def _generate(output: Path) -> int:
    generated = hayate_sql_main(["generate", str(QUERIES), "--output", str(output)])
    if generated != 0:
        return generated
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--config",
            str(ROOT / "pyproject.toml"),
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="update src/queries.py")
    args = parser.parse_args(argv)

    checked = hayate_sql_main(
        [
            "check",
            str(QUERIES),
            "--dialect",
            "d1",
            "--migrations",
            str(MIGRATIONS),
        ]
    )
    if checked != 0:
        return checked
    if args.write:
        return _generate(GENERATED)

    with tempfile.TemporaryDirectory(prefix="hayate-sql-") as directory:
        candidate = Path(directory) / "queries.py"
        generated = _generate(candidate)
        if generated != 0:
            return generated
        if candidate.read_bytes() != GENERATED.read_bytes():
            print(
                "src/queries.py is stale; run "
                "`uv run python scripts/check_sql_contracts.py --write`",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
