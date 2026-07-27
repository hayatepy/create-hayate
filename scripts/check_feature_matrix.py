"""Resolve and import every supported feature composition."""

import itertools
import os
import subprocess
import tempfile
from pathlib import Path

from create_hayate.cli import FEATURES, main


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, cwd=cwd, env=env)


def _python(environment: Path) -> Path:
    posix = environment / ".venv" / "bin" / "python"
    return posix if posix.exists() else environment / ".venv" / "Scripts" / "python.exe"


def main_check() -> int:
    names = sorted(FEATURES)
    combinations = [
        combination
        for size in range(len(names) + 1)
        for combination in itertools.combinations(names, size)
    ]
    with tempfile.TemporaryDirectory(prefix="create-hayate-matrix-") as raw:
        root = Path(raw)
        union = root / "union"
        union.mkdir()
        (union / "pyproject.toml").write_text(
            """
[project]
name = "create-hayate-feature-matrix"
version = "0"
requires-python = ">=3.13,<3.14"
dependencies = [
  "hayate>=0.12.1,<0.13",
  "hayate-mcp>=0.11,<0.12",
  "hayate-openapi>=0.6,<0.7",
  "hayate-sql>=0.1,<0.2",
]
""".lstrip(),
            encoding="utf-8",
        )
        _run(["uv", "sync", "--project", str(union), "--no-dev"])
        interpreter = _python(union)

        projects: list[Path] = []
        counter = 0
        original = Path.cwd()
        try:
            os.chdir(root)
            for template in ("api", "workers"):
                auths = ("none",) if template == "api" else ("none", "cloudflare-access")
                entrypoints = ("class",) if template == "api" else ("class", "global")
                for auth, combination, entrypoint in itertools.product(
                    auths,
                    combinations,
                    entrypoints,
                ):
                    counter += 1
                    project_name = f"matrix-{counter}"
                    arguments = [project_name, "--template", template, "--no-input"]
                    if combination:
                        arguments.extend(["--with", ",".join(combination)])
                    if auth != "none":
                        arguments.extend(["--auth", auth])
                    if entrypoint == "global":
                        arguments.extend(["--workers-entrypoint", "global"])
                    if main(arguments) != 0:
                        return 1
                    projects.append(root / project_name)

            production = "matrix-production"
            if (
                main(
                    [
                        production,
                        "--template",
                        "workers",
                        "--preset",
                        "production",
                        "--no-input",
                    ]
                )
                != 0
            ):
                return 1
            projects.append(root / production)

            production_global = "matrix-production-global"
            if (
                main(
                    [
                        production_global,
                        "--template",
                        "workers",
                        "--preset",
                        "production",
                        "--workers-entrypoint",
                        "global",
                        "--no-input",
                    ]
                )
                != 0
            ):
                return 1
            projects.append(root / production_global)
        finally:
            os.chdir(original)

        for project in projects:
            _run(["uv", "lock", "--project", str(project)])
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(project / "src")
            _run(
                [
                    str(interpreter),
                    "-c",
                    "from app import app; assert app.routes",
                ],
                cwd=project,
                env=environment,
            )
        print(f"resolved and imported {len(projects)} supported compositions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_check())
