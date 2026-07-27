"""Zero-dependency scaffold CLI built from composable bundled components."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from string import Template

TEMPLATES: dict[str, str] = {
    "api": "TODO API + pytest, served by uvicorn",
    "workers": "the same app on Cloudflare Python Workers",
    "mcp": "MCP 2025-11-25 on ASGI and Cloudflare Workers",
}
DEFAULT_TEMPLATE = "api"
FEATURES: dict[str, str] = {
    "openapi": "OpenAPI 3.1, Scalar docs, and typed-client export",
    "mcp": "MCP 2025-11-25 tools on the same application",
    "sql": "checked SQL contracts with SQLite and Cloudflare D1",
}
AUTHS = ("none", "cloudflare-access")
PRESETS = ("production",)
_FEATURE_ORDER = ("sql", "mcp", "openapi")
_REGISTRATION_ORDER = ("access", "production", "mcp", "openapi")
_DEPENDENCIES = {
    "openapi": "hayate-openapi>=0.4.1,<0.5",
    "mcp": "hayate-mcp>=0.11,<0.12",
    "sql": "hayate-sql>=0.1,<0.2",
}

# One name serves as directory, distribution, and Workers service name,
# so enforce the strictest of the three.
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_RESERVED_PROJECT_NAMES = {
    "hayate",
    "hayate-mcp",
    "hayate-openapi",
    "hayate-sql",
    "mcp",
    "pytest",
    "pytest-asyncio",
    "ruff",
    "uvicorn",
    "workers-py",
    "workers-runtime-sdk",
}

# Build backends drop dotfiles from wheels, so bundle them without the dot.
_RENAMES = {
    "dev-vars": ".dev.vars",
    "gitignore": ".gitignore",
    "node-version": ".node-version",
    "nvmrc": ".nvmrc",
}
_SKIP_DIRS = {"__pycache__"}


@dataclass(frozen=True)
class ScaffoldPlan:
    template: str
    runtime: str
    features: tuple[str, ...]
    auth: str
    production: bool
    workers_entrypoint: str


def _render_tree(src: Traversable, dest: Path, variables: dict[str, str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in _SKIP_DIRS:
            continue
        target = dest / _RENAMES.get(entry.name, entry.name)
        if entry.is_dir():
            _render_tree(entry, target, variables)
        else:
            text = entry.read_text(encoding="utf-8")
            target.write_text(Template(text).substitute(variables), encoding="utf-8", newline="\n")


def _choose_template() -> str:
    names = list(TEMPLATES)
    print("Which template?")
    for i, name in enumerate(names, start=1):
        print(f"  {i}) {name:<8}- {TEMPLATES[name]}")
    while True:
        try:
            raw = input(f"Choose 1-{len(names)} [1]: ").strip()
        except EOFError:
            return DEFAULT_TEMPLATE
        if not raw:
            return names[0]
        if raw in TEMPLATES:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(names):
            return names[int(raw) - 1]
        print(f"Please answer 1-{len(names)} or a template name.")


def _parse_features(raw: str | None, parser: argparse.ArgumentParser) -> set[str]:
    if raw is None:
        return set()
    requested = {feature.strip() for feature in raw.split(",") if feature.strip()}
    if not requested:
        parser.error("--with requires a comma-separated feature list")
    unknown = requested.difference(FEATURES)
    if unknown:
        supported = ", ".join(FEATURES)
        parser.error(
            f"unsupported feature(s): {', '.join(sorted(unknown))}; choose from {supported}"
        )
    return requested


def _build_plan(
    args: argparse.Namespace,
    template: str,
    parser: argparse.ArgumentParser,
) -> ScaffoldPlan:
    features = _parse_features(args.features, parser)
    runtime = "api" if template == "api" else "workers"
    if template == "mcp":
        features.add("mcp")

    production = args.preset == "production"
    auth = args.auth
    if production:
        if template != "workers":
            parser.error("--preset production requires --template workers")
        features.update(FEATURES)
        if auth not in (None, "cloudflare-access"):
            parser.error("--preset production requires --auth cloudflare-access")
        auth = "cloudflare-access"
    elif auth is None:
        auth = "none"

    if auth == "cloudflare-access" and runtime != "workers":
        parser.error(
            "--auth cloudflare-access requires --template workers; "
            "use --auth none for an ASGI-only project"
        )
    if runtime == "api" and args.workers_entrypoint != "class":
        parser.error("--workers-entrypoint applies only to workers and mcp templates")

    ordered = tuple(feature for feature in _FEATURE_ORDER if feature in features)
    return ScaffoldPlan(
        template=template,
        runtime=runtime,
        features=ordered,
        auth=auth,
        production=production,
        workers_entrypoint=args.workers_entrypoint,
    )


def _toml_array(values: list[str]) -> str:
    return "[\n" + "".join(f'  "{value}",\n' for value in values) + "]"


def _feature_registration(plan: ScaffoldPlan) -> tuple[str, str]:
    enabled = set(plan.features).intersection(_REGISTRATION_ORDER)
    if plan.auth == "cloudflare-access":
        enabled.add("access")
    if plan.production:
        enabled.add("production")
    ordered = [name for name in _REGISTRATION_ORDER if name in enabled]
    imports = "\n".join(
        f"from feature_{name} import register as register_{name}" for name in sorted(enabled)
    )
    if imports:
        imports = f"\n\n{imports}"
    calls = "\n".join(f"    register_{name}(app)" for name in ordered)
    return imports, calls or "    del app"


def _readme_sections(plan: ScaffoldPlan) -> dict[str, str]:
    sql = "sql" in plan.features
    mcp = "mcp" in plan.features
    openapi = "openapi" in plan.features
    feature_names = [*plan.features]
    if plan.auth != "none":
        feature_names.append(f"auth:{plan.auth}")
    if plan.production:
        feature_names.append("production-controls")

    quickstart = ["uv sync", "uv run pytest"]
    if sql and plan.runtime == "workers":
        quickstart.append("uv run python manage_workers.py d1 migrations apply DB --local")
    quickstart.append(
        "uv run uvicorn app:app --app-dir src --reload"
        if plan.runtime == "api"
        else "uv run python manage_workers.py dev"
    )

    sql_section = ""
    if sql:
        sql_section = """
## SQL contracts

Queries in `sql/queries/` compile against `migrations/` and generate
`src/queries.py`.

```sh
uv run python scripts/check_sql_contracts.py
uv run python scripts/check_sql_contracts.py --write
```

ASGI uses a local SQLite database. Cloudflare Workers uses the `DB` D1 binding
without changing `src/app.py`.
"""
    mcp_section = ""
    if mcp:
        mcp_section = """
## MCP

The MCP 2025-11-25 endpoint is `/mcp`. Its `list_todos` tool reads the same
identity context and SQL-backed storage as the HTTP API.
"""
    openapi_section = ""
    if openapi:
        openapi_section = """
## API schema and typed client

OpenAPI 3.1 JSON is served at `/openapi.json`; Scalar is served at `/docs`.
Export the schema and pinned TypeScript types with:

```sh
sh scripts/export_api.sh
```
"""
    auth_section = ""
    if plan.auth == "cloudflare-access":
        auth_section = """
## Identity

Protected routes require Cloudflare Access identity. Local development accepts
`Cf-Access-Authenticated-User-Email`; production additionally verifies the
Access JWT signature, issuer, audience, expiry, type, subject, and email.
Local trust is isolated to the ignored `.dev.vars`; every deploy configuration
defaults to fail-closed production verification.
"""
    production_section = ""
    if plan.production:
        production_section = """
## Production handoff

Complete every item in [PRODUCTION.md](PRODUCTION.md) before deployment.
The generated configuration fails closed when production identity, CORS, D1,
or rate-limit bindings are missing.
"""
    return {
        "feature_summary": ", ".join(feature_names) if feature_names else "base API",
        "quickstart_commands": "\n".join(quickstart),
        "sql_readme": sql_section.strip(),
        "mcp_readme": mcp_section.strip(),
        "openapi_readme": openapi_section.strip(),
        "auth_readme": auth_section.strip(),
        "production_readme": production_section.strip(),
    }


def _variables(name: str, plan: ScaffoldPlan) -> dict[str, str]:
    global_entrypoint = plan.workers_entrypoint == "global"
    dependencies = ["hayate>=0.12.1,<0.13"]
    dependencies.extend(_DEPENDENCIES[feature] for feature in plan.features)
    dev_dependencies = [
        "pytest>=8.3",
        "pytest-asyncio>=0.25",
        "ruff>=0.16",
        "uvicorn>=0.30",
    ]
    if plan.runtime == "workers":
        dev_dependencies.extend(
            [
                "workers-py>=1.15,<2",
                "workers-runtime-sdk>=1.6,<2",
            ]
        )

    feature_imports, feature_registrations = _feature_registration(plan)
    bindings: list[str] = []
    if "sql" in plan.features:
        bindings.append(
            f"""
[[d1_databases]]
binding = "DB"
database_name = "{name}"
database_id = "00000000-0000-0000-0000-000000000000"
migrations_dir = "migrations"
""".strip()
        )
    if plan.production:
        bindings.append(
            """
[[ratelimits]]
name = "API_RATE_LIMITER"
namespace_id = "1001"
simple = { limit = 60, period = 60 }
""".strip()
        )

    deploy_vars: list[str] = []
    production_env = ""
    if plan.auth == "cloudflare-access":
        deploy_vars.extend(
            [
                'ENVIRONMENT = "production"',
                'ACCESS_TEAM_DOMAIN = "https://your-team.cloudflareaccess.com"',
                'ACCESS_AUD = "replace-with-your-access-application-audience"',
            ]
        )
    if plan.production:
        deploy_vars.append('CORS_ORIGINS = "https://app.example.com"')
        production_env = f"""
[env.production.vars]
ENVIRONMENT = "production"
CORS_ORIGINS = "https://app.example.com"
ACCESS_TEAM_DOMAIN = "https://your-team.cloudflareaccess.com"
ACCESS_AUD = "replace-with-your-access-application-audience"

[[env.production.d1_databases]]
binding = "DB"
database_name = "{name}-production"
database_id = "00000000-0000-0000-0000-000000000000"
migrations_dir = "migrations"

[[env.production.ratelimits]]
name = "API_RATE_LIMITER"
namespace_id = "1002"
simple = {{ limit = 60, period = 60 }}
""".strip()

    variables = {
        "project_name": name,
        "requires_python": ">=3.13,<3.14" if plan.runtime == "workers" else ">=3.12",
        "dependencies": _toml_array(dependencies),
        "dev_dependencies": _toml_array(dev_dependencies),
        "pythonpath": '["src"]',
        "feature_imports": feature_imports,
        "feature_registrations": feature_registrations,
        "workers_adapter": "to_workers_global" if global_entrypoint else "to_workers",
        "workers_export": (
            "on_fetch = to_workers_global(app)"
            if global_entrypoint
            else "Default = to_workers(app)"
        ),
        "workers_compatibility_flags": (
            '"python_workers", "disable_python_no_global_handlers"'
            if global_entrypoint
            else '"python_workers"'
        ),
        "workers_entrypoint_summary": (
            "This project explicitly uses Hayate's lower-overhead global handler. "
            "It is HTTP-only: named RPC methods and class handlers such as "
            "`scheduled` require the default `WorkerEntrypoint` mode."
            if global_entrypoint
            else "This project uses the default `WorkerEntrypoint` class, preserving "
            "named RPC methods and class handlers such as `scheduled`."
        ),
        "runtime_readme": (
            (
                "This project targets Cloudflare Python Workers and also runs unchanged "
                "through ASGI. "
                + (
                    "It explicitly uses the lower-overhead global handler and is HTTP-only."
                    if global_entrypoint
                    else "It uses the feature-complete `WorkerEntrypoint` class."
                )
            )
            if plan.runtime == "workers"
            else "This project targets ASGI and keeps its application core adapter-neutral."
        ),
        "wrangler_bindings": "\n\n".join(bindings),
        "wrangler_vars": "[vars]\n" + "\n".join(deploy_vars) if deploy_vars else "",
        "production_env": production_env,
        "auth_headers": (
            '{"Cf-Access-Authenticated-User-Email": "developer@example.com"}'
            if plan.auth == "cloudflare-access"
            else "{}"
        ),
    }
    variables.update(_readme_sections(plan))
    return variables


def _render_plan(dest: Path, variables: dict[str, str], plan: ScaffoldPlan) -> None:
    templates = files("create_hayate").joinpath("templates")
    _render_tree(templates.joinpath("base"), dest, variables)
    if plan.runtime == "workers":
        _render_tree(templates.joinpath("workers"), dest, variables)
    for feature in plan.features:
        _render_tree(templates.joinpath("features", feature), dest, variables)
    if plan.auth == "cloudflare-access":
        _render_tree(templates.joinpath("auth", "cloudflare-access"), dest, variables)
    if plan.production:
        _render_tree(templates.joinpath("production"), dest, variables)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="create-hayate",
        description="Scaffold a tested Hayate project from composable features.",
    )
    parser.add_argument("name", help="project name; a directory of this name is created")
    parser.add_argument(
        "--template",
        choices=tuple(TEMPLATES),
        help="project template (prompted interactively when omitted)",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help=f"never prompt; --template or the default ({DEFAULT_TEMPLATE}) is used",
    )
    parser.add_argument(
        "--workers-entrypoint",
        choices=("class", "global"),
        default="class",
        help=(
            "Workers handler shape: the feature-complete WorkerEntrypoint class "
            "(default), or the explicit HTTP-only global compatibility path"
        ),
    )
    parser.add_argument(
        "--with",
        dest="features",
        metavar="FEATURES",
        help="comma-separated optional features: openapi,mcp,sql",
    )
    parser.add_argument(
        "--auth",
        choices=AUTHS,
        default=None,
        help="identity strategy (default: none; production preset: cloudflare-access)",
    )
    parser.add_argument(
        "--preset",
        choices=PRESETS,
        help="curated feature composition; production requires the workers template",
    )
    args = parser.parse_args(argv)

    if not _NAME_RE.match(args.name):
        parser.error(
            f"invalid project name {args.name!r}: use lowercase letters, digits, and"
            " hyphens, starting with a letter (the name doubles as the Workers"
            " service name)"
        )
    if args.name in _RESERVED_PROJECT_NAMES:
        parser.error(
            f"invalid project name {args.name!r}: it shadows a generated project dependency; "
            "choose an application-specific name"
        )
    dest = Path.cwd() / args.name
    if dest.exists():
        parser.error(f"{dest} already exists")

    template = args.template
    if template is None:
        interactive = not args.no_input and sys.stdin is not None and sys.stdin.isatty()
        template = _choose_template() if interactive else DEFAULT_TEMPLATE

    plan = _build_plan(args, template, parser)
    variables = _variables(args.name, plan)
    try:
        _render_plan(dest, variables, plan)
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    serve = (
        "uv run uvicorn app:app --app-dir src --reload"
        if plan.runtime == "api"
        else "uv run python manage_workers.py dev"
    )
    feature_summary = ", ".join(plan.features) or "base"
    print(
        f"\nCreated {args.name}/ from the {template} template "
        f"({feature_summary}; auth={plan.auth}). Next:\n"
    )
    print(f"  cd {args.name}")
    print("  uv run pytest")
    print(f"  {serve}")
    return 0
