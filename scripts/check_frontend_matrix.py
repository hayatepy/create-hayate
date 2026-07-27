"""Drive the released-artifact frontend compatibility matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from create_hayate.frontend_compatibility import (
    FRONTEND_PROFILES,
    FULL_SHARDS,
    RENDERER_CASES,
    SCHEMA_VERSION,
    SMOKE_IDS,
    SUPPORTED_FRONTEND_CASES,
    TOOLCHAINS,
    FrontendCase,
    smoke_frontend_cases,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENT = ROOT / "docs" / "FRONTEND_COMPATIBILITY.md"


def _command_text(command: list[str]) -> str:
    return shlex.join(command)


def _run(
    command: list[str],
    *,
    cwd: Path,
    phase: str,
    commands: list[dict[str, Any]],
    env: dict[str, str] | None = None,
    expect_failure: bool = False,
) -> None:
    started = time.monotonic()
    print(f"::group::{phase}", flush=True)
    print(f"$ {_command_text(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    print("::endgroup::", flush=True)
    elapsed = round(time.monotonic() - started, 3)
    commands.append(
        {
            "phase": phase,
            "command": _command_text(command),
            "seconds": elapsed,
            "exit_code": completed.returncode,
            "expected_failure": expect_failure,
        }
    )
    succeeded = completed.returncode == 0
    if expect_failure and succeeded:
        raise RuntimeError(f"{phase}: command unexpectedly succeeded")
    if not expect_failure and not succeeded:
        raise RuntimeError(f"{phase}: command exited {completed.returncode}")


def _capture(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _expected_toolchains(python_version: str) -> dict[str, str]:
    return {
        "python": python_version,
        "uv": TOOLCHAINS["uv"],
        "node": TOOLCHAINS["node"],
        "npm": TOOLCHAINS["npm"],
    }


def _actual_toolchains() -> dict[str, str]:
    uv_output = _capture(["uv", "--version"]).split()
    if len(uv_output) < 2:
        raise RuntimeError("toolchain-check: uv --version returned an unexpected value")
    return {
        "python": platform.python_version(),
        "uv": uv_output[1],
        "node": _capture(["node", "--version"]).removeprefix("v"),
        "npm": _capture(["npm", "--version"]),
    }


def _verify_toolchains(actual: dict[str, str], expected: dict[str, str]) -> None:
    mismatches = {
        name: {"expected": expected[name], "actual": actual.get(name, "missing")}
        for name in expected
        if actual.get(name) != expected[name]
    }
    if mismatches:
        rendered = ", ".join(
            f"{name}: expected {versions['expected']}, got {versions['actual']}"
            for name, versions in mismatches.items()
        )
        raise RuntimeError(f"toolchain-check: {rendered}")


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _browser_environment() -> dict[str, str]:
    backend_port = _free_port()
    frontend_port = _free_port()
    while frontend_port == backend_port:
        frontend_port = _free_port()
    environment = os.environ.copy()
    environment.update(
        {
            "HAYATE_E2E_BACKEND_PORT": str(backend_port),
            "HAYATE_E2E_FRONTEND_PORT": str(frontend_port),
            "HAYATE_E2E_ISOLATED": "1",
            "HAYATE_DEV_ORIGIN": f"http://127.0.0.1:{backend_port}",
        }
    )
    return environment


def _project_arguments(case: FrontendCase, project_name: str) -> list[str]:
    arguments = [
        project_name,
        "--template",
        case.template,
        "--frontend",
        case.frontend,
        "--no-input",
    ]
    if case.requested_features:
        arguments.extend(["--with", ",".join(case.requested_features)])
    if case.auth != "none":
        arguments.extend(["--auth", case.auth])
    if case.entrypoint != "class":
        arguments.extend(["--workers-entrypoint", case.entrypoint])
    if case.frontend == "htmx" and case.renderer != "jinja":
        arguments.extend(["--renderer", case.renderer])
    return arguments


def _expected_assets(case: FrontendCase) -> tuple[str, ...]:
    common = ("frontend/profile.toml",)
    if case.frontend == "htmx":
        assets = (
            *common,
            "public/assets/vendor/htmx-2.0.10.min.js",
            "tests/browser/test_htmx_browser.py",
        )
        if case.renderer != "jinja":
            return (*assets, "frontend/renderer.toml", "src/identity.pyi")
        return assets
    if case.frontend == "react":
        return (
            *common,
            "frontend/package-lock.json",
            "frontend/openapi.json",
            "frontend/src/api/schema.d.ts",
            "frontend/dist/index.html",
        )
    return (
        *common,
        "frontend/package-lock.json",
        "frontend/openapi.json",
        "frontend/src/api/schema.d.ts",
        "frontend/dist/index.html",
        "frontend/dist/404.html",
        "frontend/dist/principles/index.html",
    )


def _run_case(
    case: FrontendCase,
    *,
    wheel: Path,
    evidence_dir: Path,
    python_version: str,
) -> bool:
    commands: list[dict[str, Any]] = []
    phase = "initialize"
    expected_toolchains = _expected_toolchains(python_version)
    record: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "case": {
            "id": case.id,
            "frontend": case.frontend,
            "template": case.template,
            "runtime": case.runtime,
            "requested_features": case.requested_features,
            "effective_features": case.effective_features,
            "auth": case.auth,
            "entrypoint": case.entrypoint,
            "renderer": case.renderer,
            "browser": case.browser,
            "workerd": case.workerd,
        },
        "artifact": {
            "file": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        },
        "declared_toolchains": TOOLCHAINS,
        "matrix_python": python_version,
        "expected_toolchains": expected_toolchains,
        "actual_toolchains": {},
        "commands": commands,
        "status": "running",
    }
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"{case.id}.json"
    try:
        phase = "toolchain-check"
        actual_toolchains = _actual_toolchains()
        record["actual_toolchains"] = actual_toolchains
        toolchains_match = actual_toolchains == expected_toolchains
        commands.append(
            {
                "phase": phase,
                "command": "verify exact Python, uv, Node.js, and npm versions",
                "seconds": 0,
                "exit_code": 0 if toolchains_match else 1,
                "expected_failure": False,
            }
        )
        _verify_toolchains(actual_toolchains, expected_toolchains)
        with tempfile.TemporaryDirectory(prefix=f"create-hayate-{case.frontend}-") as raw:
            workspace = Path(raw)
            project_name = "matrix-app"
            phase = "generate-from-wheel"
            _run(
                [
                    "uvx",
                    "--from",
                    str(wheel),
                    "create-hayate",
                    *_project_arguments(case, project_name),
                ],
                cwd=workspace,
                phase=phase,
                commands=commands,
            )
            project = workspace / project_name

            phase = "python-lock"
            _run(
                ["uv", "lock", "--python", python_version],
                cwd=project,
                phase=phase,
                commands=commands,
            )
            phase = "python-sync-locked"
            _run(
                ["uv", "sync", "--locked", "--python", python_version],
                cwd=project,
                phase=phase,
                commands=commands,
            )
            for phase, command in (
                ("python-tests", ["uv", "run", "--no-sync", "pytest", "-q"]),
                ("python-lint", ["uv", "run", "--no-sync", "ruff", "check", "."]),
                (
                    "python-format",
                    ["uv", "run", "--no-sync", "ruff", "format", "--check", "."],
                ),
            ):
                _run(command, cwd=project, phase=phase, commands=commands)

            if case.frontend == "htmx" and case.renderer != "jinja":
                renderer_targets = ["src/feature_htmx.py"]
                if case.renderer in {"htpy", "tdom"}:
                    renderer_targets.append("src/htmx_views.py")
                phase = "renderer-mypy"
                _run(
                    ["uv", "run", "--no-sync", "mypy", "--strict", *renderer_targets],
                    cwd=project,
                    phase=phase,
                    commands=commands,
                )
                phase = "renderer-import"
                _run(
                    [
                        "uv",
                        "run",
                        "--no-sync",
                        "python",
                        "-c",
                        "import app, feature_htmx; assert app.app is not None",
                    ],
                    cwd=project,
                    phase=phase,
                    commands=commands,
                )

            if case.frontend in {"react", "astro"}:
                frontend = project / "frontend"
                for phase, command in (
                    ("node-sync-locked", ["npm", "ci", "--ignore-scripts"]),
                    ("openapi-drift-check", ["npm", "run", "api:check"]),
                ):
                    _run(command, cwd=frontend, phase=phase, commands=commands)

                document = frontend / "openapi.json"
                document.write_text(
                    document.read_text(encoding="utf-8") + "\n",
                    encoding="utf-8",
                )
                phase = "openapi-stale-rejection"
                _run(
                    ["npm", "run", "api:check"],
                    cwd=frontend,
                    phase=phase,
                    commands=commands,
                    expect_failure=True,
                )
                for phase, command in (
                    ("openapi-regenerate", ["npm", "run", "api:generate"]),
                    ("openapi-regenerated-check", ["npm", "run", "api:check"]),
                    ("typescript-typecheck", ["npm", "run", "typecheck"]),
                    ("frontend-build", ["npm", "run", "build"]),
                    ("node-audit", ["npm", "audit", "--audit-level=high"]),
                ):
                    _run(command, cwd=frontend, phase=phase, commands=commands)

                if case.browser:
                    phase = "browser-install"
                    _run(
                        ["npx", "playwright", "install", "--with-deps", "chromium"],
                        cwd=frontend,
                        phase=phase,
                        commands=commands,
                    )
                    phase = "browser-smoke"
                    browser_env = _browser_environment()
                    record["browser_environment"] = {
                        name: browser_env[name]
                        for name in (
                            "HAYATE_E2E_BACKEND_PORT",
                            "HAYATE_E2E_FRONTEND_PORT",
                            "HAYATE_E2E_ISOLATED",
                            "HAYATE_DEV_ORIGIN",
                        )
                    }
                    _run(
                        ["npm", "run", "test:e2e"],
                        cwd=frontend,
                        phase=phase,
                        commands=commands,
                        env=browser_env,
                    )
            elif case.browser:
                phase = "browser-install"
                _run(
                    ["uv", "run", "--no-sync", "playwright", "install", "--with-deps", "chromium"],
                    cwd=project,
                    phase=phase,
                    commands=commands,
                )
                browser_env = os.environ.copy()
                browser_env["HAYATE_HTMX_BROWSER_TESTS"] = "1"
                phase = "browser-smoke"
                _run(
                    ["uv", "run", "--no-sync", "pytest", "-m", "browser", "-q"],
                    cwd=project,
                    phase=phase,
                    commands=commands,
                    env=browser_env,
                )

            phase = "asset-check"
            missing = [
                relative
                for relative in _expected_assets(case)
                if not (project / relative).is_file()
            ]
            if missing:
                raise RuntimeError(f"{phase}: missing generated assets: {', '.join(missing)}")
            commands.append(
                {
                    "phase": phase,
                    "command": "verify generated asset manifest",
                    "seconds": 0,
                    "exit_code": 0,
                    "expected_failure": False,
                }
            )

            if case.workerd:
                workerd_env = os.environ.copy()
                workerd_env.update(
                    {
                        "CREATE_HAYATE_WHEEL": str(wheel),
                        "MATRIX_FEATURES": ",".join(case.requested_features),
                        "MATRIX_AUTH": case.auth,
                        "MATRIX_ENTRYPOINT": case.entrypoint,
                        "MATRIX_RENDERER": (case.renderer if case.frontend == "htmx" else "jinja"),
                        "MATRIX_PYTHON": python_version,
                    }
                )
                phase = "real-workerd"
                _run(
                    ["bash", "scripts/check_workers_template.sh", case.frontend],
                    cwd=ROOT,
                    phase=phase,
                    commands=commands,
                    env=workerd_env,
                )

        record["status"] = "passed"
        return True
    except Exception as error:
        record["status"] = "failed"
        record["failed_phase"] = phase
        record["error"] = str(error)
        print(f"::{case.id} failed at {phase}: {error}", file=sys.stderr)
        return False
    finally:
        evidence_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _cases_for(scope: str, selector: str) -> tuple[FrontendCase, ...]:
    if scope == "smoke":
        cases = {case.id: case for case in smoke_frontend_cases()}
        try:
            return (cases[selector],)
        except KeyError as error:
            raise ValueError(f"unknown smoke case: {selector}") from error
    shard = int(selector)
    if not 0 <= shard < FULL_SHARDS:
        raise ValueError(f"full shard must be between 0 and {FULL_SHARDS - 1}")
    return tuple(
        case for index, case in enumerate(SUPPORTED_FRONTEND_CASES) if index % FULL_SHARDS == shard
    )


def _matrix(scope: str) -> dict[str, list[dict[str, str]]]:
    if scope == "smoke":
        include = [
            {
                "id": case.id,
                "scope": scope,
                "selector": case.id,
                "python": TOOLCHAINS["python_asgi" if case.runtime == "api" else "python_workers"],
            }
            for case in smoke_frontend_cases()
        ]
    else:
        include = [
            {
                "id": f"full-{shard + 1:02d}-of-{FULL_SHARDS}",
                "scope": scope,
                "selector": str(shard),
                "python": TOOLCHAINS["python_workers"],
            }
            for shard in range(FULL_SHARDS)
        ]
    return {"include": include}


def _render_document() -> str:
    profile_rows = "\n".join(
        "| "
        + " | ".join(
            (
                name,
                ", ".join(profile.templates),
                ", ".join(profile.required_features) or "none",
                ", ".join(profile.optional_features) or "none",
            )
        )
        + " |"
        for name, profile in FRONTEND_PROFILES.items()
    )
    smoke_rows = "\n".join(
        f"| `{case.id}` | "
        f"{f'`{case.renderer}`' if case.renderer != 'none' else '—'} | "
        f"{'yes' if case.browser else 'no'} | {'yes' if case.workerd else 'no'} |"
        for case in smoke_frontend_cases()
    )
    renderer_rows = "\n".join(
        f"| `{case.renderer}` | `{case.template}` | "
        f"{'supported' if case.renderer != 'tdom' else 'experimental'} | "
        f"{'yes' if case.browser else 'no'} | {'yes' if case.workerd else 'no'} |"
        for case in RENDERER_CASES
    )
    return f"""# Frontend compatibility

This is the published compatibility contract for `create-hayate` frontend
profiles. It is rendered from
`src/create_hayate/frontend_compatibility.json`; CI fails if this document,
the CLI allow-list, or the executable matrix drifts from that source.

## Supported axes

| Frontend | Templates | Required features | Optional features |
|---|---|---|---|
{profile_rows}

- `api` supports `auth=none` and the class entrypoint.
- `workers` and the `mcp` shortcut support `auth=none|cloudflare-access` and
  `workers-entrypoint=class|global`.
- `mcp` is implicit in the `mcp` shortcut. `openapi` is implicit in React and
  Astro. Removing those duplicates leaves
  **{len(SUPPORTED_FRONTEND_CASES)} unique supported frontend compositions**.
- Frontends remain intentionally incompatible with `--preset production`
  until each profile has a dedicated reviewed production contract.

## htmx renderer contracts

Jinja2 remains the compatibility default and the existing 112-composition full
matrix is unchanged. The following additional boundary cases exercise each
explicit renderer without replacing or weakening that matrix.

| Renderer | Template | Status | Chromium | Real workerd |
|---|---|---|---|---|
{renderer_rows}

## Exact CI toolchains

| Tool | Version |
|---|---|
| Python (ASGI smoke) | {TOOLCHAINS["python_asgi"]} |
| Python (Workers/full matrix) | {TOOLCHAINS["python_workers"]} |
| Node.js | {TOOLCHAINS["node"]} |
| npm | {TOOLCHAINS["npm"]} |
| uv | {TOOLCHAINS["uv"]} |

Every run records the actual tool versions, wheel SHA-256, composition, phase,
command, exit code, and duration in the uploaded
`frontend-compatibility-evidence` JSON artifact. A run fails before generation
if any actual tool version differs from this contract. Browser cases also
record isolated, dynamically selected backend and frontend ports so an
unrelated local server cannot satisfy their readiness probes.

## Pull-request smoke cases

| Composition | Renderer | Chromium | Real workerd |
|---|---|---|---|
{smoke_rows}

Pull requests run these {len(SMOKE_IDS)} boundary cases. A weekly schedule and
manual `workflow_dispatch` split all {len(SUPPORTED_FRONTEND_CASES)} compositions
across {FULL_SHARDS} deterministic shards. Scheduled workflows run from the
latest default-branch commit; manual runs can select `smoke` or `full`.

## Per-composition phases

1. Build `create-hayate` as a wheel and scaffold with
   `uvx --from <wheel> create-hayate ...`.
2. Create a Python lock with `uv lock`, then install only with
   `uv sync --locked`.
3. Run generated pytest, Ruff check, and Ruff format check.
4. For explicit htmx renderers, run strict mypy on the renderer boundary and
   import the generated application.
5. For React/Astro, install `package-lock.json` with `npm ci`, export and
   drift-check OpenAPI, prove a stale artifact is rejected, regenerate it,
   typecheck, build, verify required assets, and run `npm audit`.
6. Run focused Chromium smoke tests with console/page errors treated as
   failures, plus representative real-workerd routing contracts.

The workflow and local entrypoint are:

```sh
uv run python scripts/check_frontend_matrix.py matrix --scope smoke
uv run python scripts/check_frontend_matrix.py run \\
  --scope smoke \\
  --selector react-api-none-class-openapi \\
  --wheel dist/create_hayate-<version>-py3-none-any.whl \\
  --evidence frontend-evidence
uv run python scripts/check_frontend_matrix.py matrix --scope full
```

The broader Hayate package-version contract remains in the ecosystem
[compatibility matrix](https://github.com/hayatepy/.github/blob/main/docs/COMPATIBILITY.md).
"""


def _summarize(
    evidence_dir: Path,
    *,
    scope: str,
    output: Path,
    markdown: Path | None,
) -> int:
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(evidence_dir.rglob("*.json"))
    ]
    expected = {
        case.id
        for case in (smoke_frontend_cases() if scope == "smoke" else SUPPORTED_FRONTEND_CASES)
    }
    actual = [record["case"]["id"] for record in records]
    duplicates = sorted({identifier for identifier in actual if actual.count(identifier) > 1})
    missing = sorted(expected.difference(actual))
    unexpected = sorted(set(actual).difference(expected))
    failed = sorted(record["case"]["id"] for record in records if record.get("status") != "passed")
    aggregate = {
        "schema": SCHEMA_VERSION,
        "scope": scope,
        "expected": len(expected),
        "received": len(records),
        "declared_toolchains": TOOLCHAINS,
        "duplicates": duplicates,
        "missing": missing,
        "unexpected": unexpected,
        "failed": failed,
        "cases": sorted(records, key=lambda record: record["case"]["id"]),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if markdown is not None:
        lines = [
            f"## Frontend compatibility · {scope}",
            "",
            f"- Expected: {len(expected)}",
            f"- Received: {len(records)}",
            f"- Passed: {len(records) - len(failed)}",
            f"- Failed: {len(failed)}",
        ]
        if missing:
            lines.append(f"- Missing: {', '.join(missing)}")
        if failed:
            lines.append(f"- Failed cases: {', '.join(failed)}")
        markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if duplicates or missing or unexpected or failed:
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    matrix = subparsers.add_parser("matrix")
    matrix.add_argument("--scope", choices=("smoke", "full"), required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--scope", choices=("smoke", "full"), required=True)
    run.add_argument("--selector", required=True)
    run.add_argument("--wheel", type=Path, required=True)
    run.add_argument("--evidence", type=Path, required=True)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--scope", choices=("smoke", "full"), required=True)
    summarize.add_argument("--evidence", type=Path, required=True)
    summarize.add_argument("--output", type=Path, required=True)
    summarize.add_argument("--markdown", type=Path)

    document = subparsers.add_parser("document")
    document.add_argument("--check", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "matrix":
        print(json.dumps(_matrix(args.scope), separators=(",", ":")))
        return 0
    if args.command == "run":
        wheel = args.wheel.resolve()
        if not wheel.is_file() or wheel.suffix != ".whl":
            raise SystemExit(f"--wheel must name an existing wheel: {wheel}")
        cases = _cases_for(args.scope, args.selector)

        def python_version(case: FrontendCase) -> str:
            if args.scope == "full" or case.runtime == "workers":
                return TOOLCHAINS["python_workers"]
            return TOOLCHAINS["python_asgi"]

        results = [
            _run_case(
                case,
                wheel=wheel,
                evidence_dir=args.evidence.resolve(),
                python_version=python_version(case),
            )
            for case in cases
        ]
        return 0 if all(results) else 1
    if args.command == "summarize":
        return _summarize(
            args.evidence,
            scope=args.scope,
            output=args.output,
            markdown=args.markdown,
        )
    document = _render_document()
    if args.check is None:
        print(document, end="")
        return 0
    actual = args.check.read_text(encoding="utf-8")
    if actual != document:
        print(f"{args.check} is stale; regenerate it from frontend compatibility data")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
