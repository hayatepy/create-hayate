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

from .frontend_compatibility import FRONTEND_PROFILES, supports_frontend_plan

TEMPLATES: dict[str, str] = {
    "api": "TODO API + pytest, served by uvicorn",
    "workers": "the same app on Cloudflare Python Workers",
    "mcp": "MCP 2025-11-25 on ASGI and Cloudflare Workers",
}
DEFAULT_TEMPLATE = "api"
FEATURES: dict[str, str] = {
    "admin": "fail-closed checked-SQL operations UI with persistent audit history",
    "openapi": "OpenAPI 3.1, Scalar docs, and typed-client export",
    "mcp": "MCP 2025-11-25 tools on the same application",
    "sql": "checked SQL contracts with SQLite and Cloudflare D1",
}
FRONTENDS: dict[str, str] = {
    "none": "backend-only project (compatibility default)",
    **{frontend: profile.description for frontend, profile in FRONTEND_PROFILES.items()},
}
DEFAULT_FRONTEND = "none"
RENDERERS: dict[str, str] = {
    "jinja": "Jinja2 templates (compatibility default)",
    "htpy": "typed Python components on ASGI and Workers",
    "jx": "Jinja-backed typed components on ASGI",
    "tdom": "experimental Python 3.14 t-string components on ASGI",
}
DEFAULT_RENDERER = "jinja"
AUTHS = ("none", "cloudflare-access")
PRESETS = ("production",)
_FEATURE_ORDER = ("sql", "admin", "mcp", "openapi")
_PRODUCTION_FEATURES = frozenset({"sql", "mcp", "openapi"})
_REGISTRATION_ORDER = (
    "observability",
    "access",
    "production",
    "admin",
    "mcp",
    "openapi",
    "htmx",
)
_DEPENDENCIES = {
    "admin": "jinja2==3.1.6",
    "openapi": "hayate-openapi>=0.7,<0.8",
    "mcp": "hayate-mcp>=0.11,<0.12",
    "sql": "hayate-sql>=0.1,<0.2",
}
_MCP_CPYTHON_RPDS = "rpds-py>=0.26; sys_platform != 'emscripten'"
_MCP_CPYTHON_MARKER = "sys_platform != 'emscripten'"
_MCP_UV_ENVIRONMENTS = """[tool.uv]
environments = [
  "sys_platform == 'emscripten'",
  "sys_platform != 'emscripten'",
]"""
_HTMX_COMMIT = "255de5bf3fc3f3f7665572940ffb5bfcef06d6b2"
_HTMX_RENDERER_COMMIT = "c133900998c487a44d40a103c52f2d469047deda"
_FRONTEND_DEPENDENCIES = {
    "none": (),
    "htmx": (f"hayate-htmx @ git+https://github.com/hayatepy/hayate-htmx.git@{_HTMX_COMMIT}",),
    "react": (),
    "astro": (),
}
_HTMX_ASGI_DEPENDENCIES = {
    renderer: (
        f"hayate-htmx[{renderer}] @ "
        f"git+https://github.com/hayatepy/hayate-htmx.git@{_HTMX_RENDERER_COMMIT}",
    )
    for renderer in ("htpy", "jx", "tdom")
}
_HTMX_WORKERS_DEPENDENCIES = {
    "htpy": (
        "jinja2==3.1.6",
        "htpy>=26.5,<27",
        "markupsafe==3.0.2; sys_platform == 'emscripten' and python_version < '3.14'",
    ),
}
_HTMX_VIEW_REFERENCES = {
    "jinja": {
        "auth": '"auth/page.html"',
        "page": '"app/page.html"',
        "list": '"app/_list.html"',
        "create_error": '"app/_create_error.html"',
        "edit": '"app/_edit.html"',
        "item": '"app/_item.html"',
    },
    "htpy": {
        "auth": "auth_page",
        "page": "app_page",
        "list": "todo_list",
        "create_error": "create_error",
        "edit": "edit_todo",
        "item": "todo_item",
    },
    "jx": {
        "auth": '"auth/page.jx"',
        "page": '"app/page.jx"',
        "list": '"app/list.jx"',
        "create_error": '"app/create_error.jx"',
        "edit": '"app/edit.jx"',
        "item": '"app/item.jx"',
    },
    "tdom": {
        "auth": "auth_page",
        "page": "app_page",
        "list": "todo_list",
        "create_error": "create_error",
        "edit": "edit_todo",
        "item": "todo_item",
    },
}
_MCP_OPENAPI_PATHS = """,
    "/mcp": {
      "get": {
        "operationId": "get_mcp",
        "responses": {
          "200": {
            "description": "Successful response"
          }
        }
      },
      "post": {
        "operationId": "post_mcp",
        "responses": {
          "200": {
            "description": "Successful response"
          }
        }
      },
      "delete": {
        "operationId": "delete_mcp",
        "responses": {
          "200": {
            "description": "Successful response"
          }
        }
      }
    }"""
_MCP_SCHEMA_PATH = """
    "/mcp": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["get_mcp"];
        put?: never;
        post: operations["post_mcp"];
        delete: operations["delete_mcp"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };"""
_MCP_SCHEMA_OPERATIONS = """
    get_mcp: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    post_mcp: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    delete_mcp: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };"""
_FRONTEND_TEMPLATES = {
    "none": frozenset(TEMPLATES),
    **{frontend: frozenset(profile.templates) for frontend, profile in FRONTEND_PROFILES.items()},
}

# One name serves as directory, distribution, and Workers service name,
# so enforce the strictest of the three.
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_RESERVED_PROJECT_NAMES = {
    "hayate",
    "hayate-mcp",
    "hayate-openapi",
    "hayate-sql",
    "htpy",
    "jinja2",
    "jx",
    "mcp",
    "mypy",
    "playwright",
    "pytest",
    "pytest-asyncio",
    "ruff",
    "tdom",
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
    "pyproject.toml.template": "pyproject.toml",
}
_SKIP_DIRS = {"__pycache__"}
_VERBATIM_SUFFIXES = (".min.js",)


@dataclass(frozen=True)
class ScaffoldPlan:
    template: str
    runtime: str
    frontend: str
    renderer: str
    features: tuple[str, ...]
    auth: str
    production: bool
    workers_entrypoint: str


def _render_tree(
    src: Traversable,
    dest: Path,
    variables: dict[str, str],
    *,
    allow_overwrite: bool = True,
    render_templates: bool = True,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in _SKIP_DIRS:
            continue
        target = dest / _RENAMES.get(entry.name, entry.name)
        if entry.is_dir():
            _render_tree(
                entry,
                target,
                variables,
                allow_overwrite=allow_overwrite,
                render_templates=render_templates,
            )
        else:
            if target.exists() and not allow_overwrite:
                raise FileExistsError(
                    f"frontend overlay would overwrite generated backend file: {target}"
                )
            if entry.name.endswith(_VERBATIM_SUFFIXES):
                target.write_bytes(entry.read_bytes())
                continue
            text = entry.read_text(encoding="utf-8")
            rendered = Template(text).substitute(variables) if render_templates else text
            target.write_text(rendered, encoding="utf-8", newline="\n")


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
    frontend = args.frontend
    renderer = args.renderer or DEFAULT_RENDERER
    if args.renderer is not None and frontend != "htmx":
        parser.error("--renderer requires --frontend htmx")
    if frontend == "htmx":
        if renderer in {"jx", "tdom"} and runtime != "api":
            parser.error(
                f"--renderer {renderer} is ASGI-only; use --template api or "
                "--renderer jinja/htpy for Cloudflare Workers"
            )
    else:
        renderer = "none"
    if template == "mcp":
        features.add("mcp")
    if frontend in {"react", "astro"}:
        features.add("openapi")
    if "admin" in features:
        features.add("sql")

    production = args.preset == "production"
    auth = args.auth
    if production:
        if template != "workers":
            parser.error("--preset production requires --template workers")
        features.update(_PRODUCTION_FEATURES)
        if auth not in (None, "cloudflare-access"):
            parser.error("--preset production requires --auth cloudflare-access")
        auth = "cloudflare-access"
    elif "admin" in features and auth is None:
        auth = "cloudflare-access"
    elif auth is None:
        auth = "none"

    if "admin" in features:
        if runtime != "workers":
            parser.error(
                "--with admin requires --template workers or mcp so the reviewed "
                "Cloudflare Access and D1 production path is available"
            )
        if auth != "cloudflare-access":
            parser.error("--with admin requires --auth cloudflare-access")
        if frontend != "none":
            parser.error(
                "--with admin currently requires --frontend none; the operations UI "
                "owns its own HTML boundary"
            )
    if auth == "cloudflare-access" and runtime != "workers":
        parser.error(
            "--auth cloudflare-access requires --template workers; "
            "use --auth none for an ASGI-only project"
        )
    if runtime == "api" and args.workers_entrypoint != "class":
        parser.error("--workers-entrypoint applies only to workers and mcp templates")
    if template not in _FRONTEND_TEMPLATES[frontend]:
        supported = ", ".join(sorted(_FRONTEND_TEMPLATES[frontend]))
        parser.error(
            f"--frontend {frontend} does not support --template {template}; choose from {supported}"
        )
    if production and frontend != "none":
        parser.error(
            f"--frontend {frontend} cannot yet be combined with --preset production; "
            "use --frontend none until that profile's production contract is available"
        )

    ordered = tuple(feature for feature in _FEATURE_ORDER if feature in features)
    if not supports_frontend_plan(
        frontend=frontend,
        template=template,
        features=ordered,
        auth=auth,
        entrypoint=args.workers_entrypoint,
        production=production,
    ):
        feature_label = ",".join(ordered) if ordered else "none"
        parser.error(
            "unsupported or untested frontend composition: "
            f"template={template}, frontend={frontend}, features={feature_label}, "
            f"auth={auth}, workers-entrypoint={args.workers_entrypoint}"
        )
    return ScaffoldPlan(
        template=template,
        runtime=runtime,
        frontend=frontend,
        renderer=renderer,
        features=ordered,
        auth=auth,
        production=production,
        workers_entrypoint=args.workers_entrypoint,
    )


def _toml_array(values: list[str]) -> str:
    return "[\n" + "".join(f'  "{value}",\n' for value in values) + "]"


def _feature_registration(plan: ScaffoldPlan) -> tuple[str, str]:
    enabled = {"observability"}
    enabled.update(set(plan.features).intersection(_REGISTRATION_ORDER))
    if plan.auth == "cloudflare-access":
        enabled.add("access")
    if plan.production:
        enabled.add("production")
    if plan.frontend == "htmx":
        enabled.add("htmx")
    ordered = [name for name in _REGISTRATION_ORDER if name in enabled]
    imports = "\n".join(
        f"from feature_{name} import register as register_{name}" for name in sorted(enabled)
    )
    if imports:
        imports = f"\n\n{imports}"
    calls = "\n".join(f"    register_{name}(app)" for name in ordered)
    return imports, calls or "    del app"


def _readme_sections(plan: ScaffoldPlan) -> dict[str, str]:
    admin = "admin" in plan.features
    sql = "sql" in plan.features
    mcp = "mcp" in plan.features
    openapi = "openapi" in plan.features
    feature_names = [*plan.features]
    if plan.auth != "none":
        feature_names.append(f"auth:{plan.auth}")
    if plan.production:
        feature_names.append("production-controls")
    if plan.frontend != "none":
        feature_names.append(f"frontend:{plan.frontend}")
    if plan.frontend == "htmx" and plan.renderer != DEFAULT_RENDERER:
        feature_names.append(f"renderer:{plan.renderer}")

    quickstart = ["uv sync", "uv run pytest"]
    if sql and plan.runtime == "workers":
        quickstart.append("uv run python manage_workers.py d1 migrations apply DB --local")
    if plan.frontend in {"react", "astro"}:
        quickstart.extend(
            [
                "npm --prefix frontend ci",
                "npm --prefix frontend run build",
            ]
        )
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
identity context and SQL-backed storage as the HTTP API. The generated uv
configuration keeps Emscripten's reviewed `rpds-py` wheel separate from the
native CPython resolution so the same universal lock installs on Workers and
Python 3.14.
"""
    openapi_section = ""
    if openapi and plan.frontend in {"react", "astro"}:
        openapi_section = """
## API schema

OpenAPI 3.1 JSON is served at `/openapi.json`; Scalar is served at `/docs`.
The frontend profile below owns the checked-in browser contract and generated
TypeScript types.
"""
    elif openapi:
        openapi_section = """
## API schema and typed client

OpenAPI 3.1 JSON is served at `/openapi.json`; Scalar is served at `/docs`.
TODO path parameters and responses use explicit typed runtime contracts; JSON
body length constraints remain enforced from the same raw schema they expose.
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
    admin_section = ""
    admin_production_checklist = ""
    if admin:
        admin_section = """
## Operations admin

Open `/admin` with a Cloudflare Access identity whose email is listed in
`ADMIN_EMAILS`. The generated starter exposes only the current identity's
TODO records, uses bounded checked-SQL search/sort/page queries, and stores
redacted attempt/success/failure events in `admin_audit_events`. Static saved
views, forward-only keyset cursors, and separately authorized bounded CSV
exports are enabled without exposing a generic query surface.

Local ASGI and `wrangler dev` authorize `developer@example.com`. Before
deployment, replace `ADMIN_EMAILS`, `ADMIN_ALLOWED_ORIGINS` in
`src/feature_admin.py`, and the example production origin together. There is
no anonymous mode, default superuser, reflected table access, or generic SQL
surface.

`src/hayate_admin` and `src/hayate_htmx` are unmodified, license-preserving
snapshots of the commits recorded in `admin/profile.toml`. They keep the
generated Workers project reproducible without a generation-time network
fetch. Replace them with released dependencies only after updating and
re-running the generated SQLite, browser, and workerd/D1 gates.

Run the optional browser gate after installing Chromium:

```sh
uv run playwright install chromium
HAYATE_ADMIN_BROWSER_TESTS=1 uv run pytest -m browser -q
```
"""
        admin_production_checklist = """
- Replace `ADMIN_EMAILS` with a reviewed, case-insensitive operator allowlist.
- Replace `ADMIN_ALLOWED_ORIGINS` in `src/feature_admin.py` with the exact
  HTTPS origin that serves `/admin`; keep it synchronized with the production
  URL and exercise a rejected foreign origin.
- Retain the append-only redacted `admin_audit_events` records according to
  your incident-response and privacy policy.
"""
    production_section = ""
    if plan.production:
        production_section = """
## Production handoff

Complete every item in [PRODUCTION.md](PRODUCTION.md) before deployment.
The generated configuration fails closed when production identity, CORS, D1,
or rate-limit bindings are missing.
"""
    frontend_section = ""
    if plan.frontend == "htmx" and plan.renderer == DEFAULT_RENDERER:
        frontend_section = """
## htmx full-stack UI

Open `/app` for the server-rendered task UI. JSON contracts live under
`/api`, the current identity is visible at `/auth`, and every browser request
stays on the application origin.

The profile pins the reviewed `hayate-htmx` 0.1 release-gate commit,
`255de5bf3fc3f3f7665572940ffb5bfcef06d6b2`, and uses autoescaping Jinja
templates, strict same-origin mutation checks, CSP, page/fragment `Vary`
headers, and the self-hosted htmx 2.0.10 asset. ASGI resolves that immutable
Git commit directly. Until the package is published, Workers includes the
same small source snapshot because Pywrangler cannot install VCS records from
its portable lock. The commit and asset SHA-256 are recorded in
`frontend/profile.toml` and asserted by generated tests.

Run the optional Chromium smoke test once the browser is installed:

```sh
uv run playwright install chromium
HAYATE_HTMX_BROWSER_TESTS=1 uv run pytest -m browser -q
```

ASGI serves `public/assets` through Hayate. The Workers configuration publishes
`public` through Cloudflare Static Assets and sends `/app`, `/api`, and `/auth`
to Python first. Both paths use the same same-origin URLs and application code.
"""
    elif plan.frontend == "htmx":
        renderer_status = (
            "This renderer is experimental and requires Python 3.14 or newer."
            if plan.renderer == "tdom"
            else "This renderer is supported for the generated runtime."
        )
        runtime_note = (
            "The Workers configuration publishes `public` through Cloudflare "
            "Static Assets and sends `/app`, `/api`, and `/auth` to Python first."
            if plan.runtime == "workers"
            else "ASGI serves `public/assets` through Hayate."
        )
        frontend_section = f"""
## htmx full-stack UI

Open `/app` for the server-rendered task UI. JSON contracts live under
`/api`, the current identity is visible at `/auth`, and every browser request
stays on the application origin.

This project uses the `{plan.renderer}` renderer from the reviewed
`hayate-htmx` 0.2.0 candidate commit
`{_HTMX_RENDERER_COMMIT}`. Page, fragment, edit, validation, and identity
views are native `{plan.renderer}` components while htmx selection, `Vary`,
status, headers, CSRF, CSP, CRUD, and SSE remain shared application contracts.
{renderer_status}

Run the optional Chromium smoke test once the browser is installed:

```sh
uv run playwright install chromium
HAYATE_HTMX_BROWSER_TESTS=1 uv run pytest -m browser -q
```

{runtime_note} The renderer, package range, Python floor, and runtime claim are
recorded in `frontend/renderer.toml` and asserted by generated tests.
"""
    elif plan.frontend == "react":
        frontend_section = """
## React SPA

The TypeScript application lives in `frontend/`; Hayate remains the only
backend and owns every `/api` route. The browser client is generated from
`frontend/openapi.json`, sends same-origin cookies with every request, and does
not store credentials in local storage.

Start both development servers in separate terminals:

```sh
uv run uvicorn app:app --app-dir src --reload
cd frontend && npm ci && npm run dev
```

Vite proxies `/api` to Hayate during development. Before committing an API
change, refresh the checked-in contract and client types:

```sh
cd frontend
npm run api:generate
npm run api:check
```

`npm run api:check` exports OpenAPI from the current Hayate routes and fails if
either the document or generated TypeScript types drift. `npm run typecheck`,
`npm run build`, and `npm run test:e2e` exercise the browser application.

For ASGI production, publish `frontend/dist` from a static host on the same
origin, proxy `/api/*`, `/openapi.json`, and `/docs` to Hayate, and rewrite
non-file navigation requests such as `/about` to `index.html`. Do not rewrite
API requests. The Workers template configures this split directly with
Cloudflare Static Assets and SPA fallback.
"""
    elif plan.frontend == "astro":
        frontend_section = """
## Astro content site

The static Astro site lives in `frontend/`; Hayate remains the only backend
and owns every `/api` route. Astro builds only local public content. The
identity-scoped workspace is a Preact island that hydrates when visible and
then requests Hayate from the browser with same-origin cookies.

Start both development servers in separate terminals:

```sh
uv run uvicorn app:app --app-dir src --reload
cd frontend && npm ci && npm run dev
```

Before committing an API change, refresh and verify the shared browser
contract:

```sh
cd frontend
npm run api:generate
npm run api:check
```

`npm run typecheck`, `npm run build`, and `npm run test:e2e` verify the static
site and its runtime island. Publish `frontend/dist` on the same origin and
route `/api/*`, `/openapi.json`, and `/docs` to Hayate first. The Workers
template configures API-first routing, trailing-slash static HTML, a generated
404 page, caching, and security headers directly.

Astro SSR is intentionally absent. If the project later needs a BFF, add the
official adapter for the target host and opt specific pages into on-demand
rendering; do not recreate Hayate business logic as Astro endpoints or actions.
"""
    return {
        "feature_summary": ", ".join(feature_names) if feature_names else "base API",
        "quickstart_commands": "\n".join(quickstart),
        "sql_readme": sql_section.strip(),
        "mcp_readme": mcp_section.strip(),
        "openapi_readme": openapi_section.strip(),
        "auth_readme": auth_section.strip(),
        "admin_readme": admin_section.strip(),
        "admin_production_checklist": admin_production_checklist.strip(),
        "production_readme": production_section.strip(),
        "frontend_readme": frontend_section.strip(),
    }


def _variables(name: str, plan: ScaffoldPlan) -> dict[str, str]:
    global_entrypoint = plan.workers_entrypoint == "global"
    dependencies = ["hayate>=0.15.1,<0.16"]
    dependencies.extend(_DEPENDENCIES[feature] for feature in plan.features)
    if "mcp" in plan.features:
        # hayate-mcp pins the Pyodide ABI-compatible rpds build only on
        # Emscripten. Tell uv to retain that platform fork instead of selecting
        # the older version for CPython to minimize a universal lock.
        dependencies.append(_MCP_CPYTHON_RPDS)
    if plan.frontend == "htmx" and plan.renderer == DEFAULT_RENDERER and plan.runtime == "workers":
        dependencies.append("jinja2==3.1.6")
    elif plan.frontend == "htmx" and plan.runtime == "workers":
        dependencies.extend(_HTMX_WORKERS_DEPENDENCIES[plan.renderer])
    elif plan.frontend == "htmx" and plan.renderer != DEFAULT_RENDERER:
        dependencies.extend(_HTMX_ASGI_DEPENDENCIES[plan.renderer])
    else:
        dependencies.extend(_FRONTEND_DEPENDENCIES[plan.frontend])
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
    if plan.frontend == "htmx" or "admin" in plan.features:
        dev_dependencies.append("playwright>=1.54,<2")
        if plan.frontend == "htmx" and plan.renderer != DEFAULT_RENDERER:
            dev_dependencies.append("mypy>=1.18")
    if "mcp" in plan.features:
        # Universal MCP locks include the Emscripten runtime, but local test,
        # lint, server, and Workers tooling only execute on the host CPython.
        # Excluding them from Emscripten also prevents native-only tools such
        # as Playwright from making that runtime resolution unsatisfiable.
        dev_dependencies = [
            f"{requirement}; {_MCP_CPYTHON_MARKER}" for requirement in dev_dependencies
        ]

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
    admin_production_vars = (
        'ADMIN_EMAILS = "operator@example.com"' if "admin" in plan.features else ""
    )
    if plan.auth == "cloudflare-access":
        deploy_vars.extend(
            [
                'ENVIRONMENT = "production"',
                'ACCESS_TEAM_DOMAIN = "https://your-team.cloudflareaccess.com"',
                'ACCESS_AUD = "replace-with-your-access-application-audience"',
            ]
        )
    if "admin" in plan.features:
        deploy_vars.append('ADMIN_EMAILS = "developer@example.com"')
    if plan.production:
        deploy_vars.append('CORS_ORIGINS = "https://app.example.com"')
        production_env = f"""
[env.production.vars]
ENVIRONMENT = "production"
CORS_ORIGINS = "https://app.example.com"
ACCESS_TEAM_DOMAIN = "https://your-team.cloudflareaccess.com"
ACCESS_AUD = "replace-with-your-access-application-audience"
{admin_production_vars}

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
        "frontend": plan.frontend,
        "api_prefix": "/api" if plan.frontend in {"htmx", "react", "astro"} else "",
        "mcp_openapi_paths": _MCP_OPENAPI_PATHS if "mcp" in plan.features else "",
        "mcp_schema_path": _MCP_SCHEMA_PATH if "mcp" in plan.features else "",
        "mcp_schema_operations": (_MCP_SCHEMA_OPERATIONS if "mcp" in plan.features else ""),
        "requires_python": (
            ">=3.14,<3.15"
            if plan.renderer == "tdom"
            else (">=3.13,<3.14" if plan.runtime == "workers" else ">=3.12")
        ),
        "dependencies": _toml_array(dependencies),
        "dev_dependencies": _toml_array(dev_dependencies),
        "uv_environments": _MCP_UV_ENVIRONMENTS if "mcp" in plan.features else "",
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
        "workers_preflight": (
            """
    embedded = subprocess.run(
        [sys.executable, "scripts/embed_htmx_templates.py"],
        check=False,
    )
    if embedded.returncode != 0:
        return embedded.returncode
""".rstrip()
            if (
                plan.runtime == "workers"
                and plan.frontend == "htmx"
                and plan.renderer == DEFAULT_RENDERER
            )
            else ""
        ),
        "htmx_import_block": (
            (
                "\nfrom hayate_htmx import HtmxTemplates, JinjaRenderer, "
                "append_htmx_vary, with_htmx\n"
                "from htmx_worker_renderer import EmbeddedJinjaRenderer"
                if plan.runtime == "workers"
                else (
                    "from hayate_htmx import HtmxTemplates, JinjaRenderer, "
                    "append_htmx_vary, with_htmx\n"
                )
            )
            if plan.renderer == "jinja"
            else (
                ("\n" if plan.runtime == "workers" else "")
                + "from hayate_htmx import HtmxTemplates, append_htmx_vary, with_htmx\n"
                f"from hayate_htmx.{plan.renderer} import "
                f"{plan.renderer.title()}Renderer\n"
                + (
                    ("\n" if plan.runtime != "workers" else "") + "from htmx_views import (\n"
                    "    app_page,\n"
                    "    auth_page,\n"
                    "    create_error,\n"
                    "    edit_todo,\n"
                    "    todo_item,\n"
                    "    todo_list,\n"
                    ")"
                    if plan.renderer in {"htpy", "tdom"}
                    else ""
                )
            )
        ),
        "htmx_renderer_setup": (
            (
                """
    template_root = _ROOT / "templates"
    renderer = JinjaRenderer(template_root) if template_root.is_dir() else EmbeddedJinjaRenderer()
""".strip("\n")
                if plan.runtime == "workers"
                else '    renderer = JinjaRenderer(_ROOT / "templates")'
            )
            if plan.renderer == "jinja"
            else (
                '    renderer = JxRenderer(_ROOT / "components")'
                if plan.renderer == "jx"
                else f"    renderer = {plan.renderer.title()}Renderer()"
            )
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
        "frontend_assets": (
            """
[assets]
directory = "./public"
binding = "ASSETS"
run_worker_first = ["/", "/app", "/app/*", "/api/*", "/auth", "/auth/*"]
""".strip()
            if plan.runtime == "workers" and plan.frontend == "htmx"
            else (
                """
[assets]
directory = "./frontend/dist"
binding = "ASSETS"
not_found_handling = "single-page-application"
run_worker_first = ["/api/*", "/openapi.json", "/docs", "/mcp", "/mcp/*"]
""".strip()
                if plan.runtime == "workers" and plan.frontend == "react"
                else (
                    """
[assets]
directory = "./frontend/dist"
binding = "ASSETS"
not_found_handling = "404-page"
html_handling = "auto-trailing-slash"
run_worker_first = ["/api/*", "/openapi.json", "/docs", "/mcp", "/mcp/*"]
""".strip()
                    if plan.runtime == "workers" and plan.frontend == "astro"
                    else ""
                )
            )
        ),
        "pytest_markers": (
            """
markers = [
  "browser: end-to-end smoke tests that require an installed Chromium browser",
]
""".strip()
            if plan.frontend == "htmx" or "admin" in plan.features
            else ""
        ),
        "ruff_extend_exclude": (
            'extend-exclude = ["src/hayate_admin", "src/hayate_htmx"]'
            if "admin" in plan.features
            else ""
        ),
        "auth_headers": (
            '{"Cf-Access-Authenticated-User-Email": "developer@example.com"}'
            if plan.auth == "cloudflare-access"
            else "{}"
        ),
        "admin_local_env_line": (
            ',\n    ADMIN_EMAILS="developer@example.com"' if "admin" in plan.features else ""
        ),
        "admin_dev_var_line": (
            "ADMIN_EMAILS=developer@example.com" if "admin" in plan.features else ""
        ),
        "ruff_target_version": "py312",
        "ruff_renderer_config": (
            '\n\n[tool.ruff.per-file-target-version]\n"src/htmx_views.py" = "py314"'
            if plan.renderer == "tdom"
            else ""
        ),
        "page_doctype_check": (
            '(await page.text()).lower().startswith("<!doctype html>")'
            if plan.renderer == "tdom"
            else '(await page.text()).startswith("<!doctype html>")'
        ),
        "restored_doctype_check": (
            '(await restored.text()).lower().startswith("<!doctype html>")'
            if plan.renderer == "tdom"
            else '(await restored.text()).startswith("<!doctype html>")'
        ),
        "htmx_server_package": (
            f"hayate-htmx 0.2.0 vendored @ {_HTMX_RENDERER_COMMIT}"
            if plan.frontend == "htmx"
            and plan.renderer != DEFAULT_RENDERER
            and plan.runtime == "workers"
            else _HTMX_ASGI_DEPENDENCIES[plan.renderer][0]
            if plan.frontend == "htmx" and plan.renderer != DEFAULT_RENDERER
            else ""
        ),
    }
    variables.update(
        {
            f"htmx_{name}_view": reference
            for name, reference in _HTMX_VIEW_REFERENCES.get(plan.renderer, {}).items()
        }
    )
    variables.update(_readme_sections(plan))
    return variables


def _render_plan(dest: Path, variables: dict[str, str], plan: ScaffoldPlan) -> None:
    templates = files("create_hayate").joinpath("templates")
    _render_tree(templates.joinpath("base"), dest, variables)
    if plan.runtime == "workers":
        _render_tree(templates.joinpath("workers"), dest, variables)
    for feature in plan.features:
        _render_tree(templates.joinpath("features", feature), dest, variables)
    if "admin" in plan.features:
        _render_tree(
            templates.joinpath("vendor", "admin"),
            dest,
            variables,
            allow_overwrite=False,
            render_templates=False,
        )
    if plan.auth == "cloudflare-access":
        _render_tree(templates.joinpath("auth", "cloudflare-access"), dest, variables)
    if plan.production:
        _render_tree(templates.joinpath("production"), dest, variables)
    if plan.frontend != "none":
        _render_tree(
            templates.joinpath("frontends", plan.frontend),
            dest,
            variables,
            allow_overwrite=False,
        )
    if plan.frontend == "htmx" and plan.renderer != DEFAULT_RENDERER:
        _render_tree(
            templates.joinpath("renderers", "shared"),
            dest,
            variables,
            allow_overwrite=False,
        )
        _render_tree(
            templates.joinpath("renderers", plan.renderer),
            dest,
            variables,
            allow_overwrite=False,
        )
    if plan.frontend in {"react", "astro"}:
        _render_tree(
            templates.joinpath("frontend_contracts", "openapi"),
            dest,
            variables,
            allow_overwrite=False,
        )
    if plan.frontend == "htmx" and plan.runtime == "workers":
        _render_tree(
            templates.joinpath("frontend_runtimes", "htmx-workers"),
            dest,
            variables,
            allow_overwrite=False,
        )
        if plan.renderer == "htpy":
            _render_tree(
                templates.joinpath("frontend_runtimes", "htmx-workers-htpy"),
                dest,
                variables,
                allow_overwrite=True,
            )


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
        help="comma-separated optional features: admin,openapi,mcp,sql",
    )
    parser.add_argument(
        "--frontend",
        choices=tuple(FRONTENDS),
        default=DEFAULT_FRONTEND,
        help="frontend profile: none (default), htmx, react, or astro",
    )
    parser.add_argument(
        "--renderer",
        choices=tuple(RENDERERS),
        default=None,
        help="htmx renderer: jinja (default), htpy, jx, or experimental tdom",
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
    frontend_summary = "" if plan.frontend == "none" else f"; frontend={plan.frontend}"
    renderer_summary = f"; renderer={plan.renderer}" if plan.frontend == "htmx" else ""
    print(
        f"\nCreated {args.name}/ from the {template} template "
        f"({feature_summary}; auth={plan.auth}{frontend_summary}{renderer_summary}). Next:\n"
    )
    print(f"  cd {args.name}")
    print("  uv run pytest")
    if plan.frontend in {"react", "astro"}:
        print("  npm --prefix frontend ci")
        if plan.runtime == "workers":
            print("  npm --prefix frontend run build")
    print(f"  {serve}")
    if plan.frontend in {"react", "astro"} and plan.runtime == "api":
        print("  # In another terminal:")
        print("  npm --prefix frontend run dev")
    return 0
