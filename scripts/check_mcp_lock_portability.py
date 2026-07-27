"""Exercise an MCP universal lock on CPython 3.14.

hayate-mcp intentionally retains an older rpds-py wheel for Emscripten. This
gate proves that a downstream generated project preserves that platform fork
instead of attempting the Pyodide-pinned source build on CPython.
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import tomllib
from pathlib import Path

from create_hayate.cli import main


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, check=True, cwd=cwd)


def _rpds_entries(lock: dict[str, object]) -> list[dict[str, object]]:
    packages = lock.get("package")
    assert isinstance(packages, list)
    return [
        package
        for package in packages
        if isinstance(package, dict) and package.get("name") == "rpds-py"
    ]


def _version_at_least(raw: object, minimum: tuple[int, ...]) -> bool:
    parts = tuple(int(part) for part in str(raw).split("."))
    return parts >= minimum


def main_check() -> int:
    with tempfile.TemporaryDirectory(prefix="create-hayate-mcp-lock-") as raw:
        root = Path(raw)
        original = Path.cwd()
        try:
            os.chdir(root)
            result = main(
                [
                    "portable-mcp",
                    "--template",
                    "api",
                    "--with",
                    "mcp",
                    "--no-input",
                ]
            )
        finally:
            os.chdir(original)
        if result != 0:
            return result

        project = root / "portable-mcp"
        _run(["uv", "lock", "--python", "3.14", "--no-cache"], cwd=project)
        lock = tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))
        supported_markers = lock.get("supported-markers")
        assert supported_markers == [
            "sys_platform == 'emscripten'",
            "sys_platform != 'emscripten'",
        ]
        project_metadata = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
        dev_dependencies = project_metadata["dependency-groups"]["dev"]
        assert dev_dependencies
        assert all(
            "sys_platform != 'emscripten'" in requirement for requirement in dev_dependencies
        )

        rpds_entries = _rpds_entries(lock)
        emscripten = [
            entry
            for entry in rpds_entries
            if entry.get("resolution-markers") == ["sys_platform == 'emscripten'"]
        ]
        native = [
            entry
            for entry in rpds_entries
            if entry not in emscripten and _version_at_least(entry["version"], (0, 26))
        ]
        assert [entry["version"] for entry in emscripten] == ["0.23.1"]
        assert native, rpds_entries

        _run(
            ["uv", "sync", "--locked", "--python", "3.14", "--no-cache"],
            cwd=project,
        )
        _run(["uv", "run", "--no-sync", "pytest", "-q"], cwd=project)
        _run(
            [
                "uv",
                "run",
                "--no-sync",
                "python",
                "-c",
                (
                    "from importlib.metadata import version;"
                    "raw=version('rpds-py');"
                    "assert tuple(map(int,raw.split('.'))) >= (0,26);"
                    "print(raw)"
                ),
            ],
            cwd=project,
        )
        print(
            "MCP lock preserved Emscripten rpds-py 0.23.1 and installed "
            f"native rpds-py {native[-1]['version']} on "
            f"{platform.system()} {platform.machine()} with Python 3.14."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main_check())
