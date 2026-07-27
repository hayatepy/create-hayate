import importlib.util
import io
import itertools
from pathlib import Path
from types import SimpleNamespace

import pytest

from create_hayate import cli
from create_hayate.cli import FEATURES, FRONTENDS, TEMPLATES, main


def _generate(
    tmp_path,
    monkeypatch,
    name="demo-app",
    template="api",
    extra_args=(),
):
    monkeypatch.chdir(tmp_path)
    assert main([name, "--template", template, "--no-input", *extra_args]) == 0
    return tmp_path / name


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_generates_a_complete_project(tmp_path, monkeypatch, template):
    dest = _generate(tmp_path, monkeypatch, template=template)
    for expected in (
        "pyproject.toml",
        "README.md",
        ".gitignore",
        "src/app.py",
        "src/storage.py",
        "src/todo_api.py",
        "src/todo_domain.py",
        "src/generated_features.py",
        "tests/test_app.py",
    ):
        assert (dest / expected).is_file(), expected
    assert 'name = "demo-app"' in (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert (dest / "wrangler.toml").is_file() is (template != "api")


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_no_generator_placeholder_survives_generation(tmp_path, monkeypatch, template):
    dest = _generate(tmp_path, monkeypatch, template=template)
    placeholders = {
        "$project_name",
        "$feature_imports",
        "$feature_registrations",
        "$dependencies",
        "$wrangler_bindings",
    }
    for path in dest.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not placeholders.intersection(text.split()), path


@pytest.mark.parametrize("template", ["workers", "mcp"])
def test_workers_templates_wire_wrangler(tmp_path, monkeypatch, template):
    dest = _generate(tmp_path, monkeypatch, template=template)
    wrangler = (dest / "wrangler.toml").read_text(encoding="utf-8")
    assert 'name = "demo-app"' in wrangler
    assert 'compatibility_flags = ["python_workers"]' in wrangler
    assert 'main = "src/entry.py"' in wrangler
    assert "\nexclude = [" in wrangler
    for excluded in (
        "**/*.pyc",
        "**/__pycache__/**",
        "**/*.dist-info/**",
        "asgi.py",
        "hayate/adapters/asgi.py",
        "hayate/adapters/aws.py",
        "workers/wsgi.py",
    ):
        assert f'"{excluded}"' in wrangler
    assert "uts46" not in wrangler
    entry = (dest / "src/entry.py").read_text(encoding="utf-8")
    assert "Default = to_workers(app)" in entry
    assert "on_fetch" not in entry
    assert (dest / ".node-version").read_text(encoding="utf-8") == "24\n"
    assert (dest / ".nvmrc").read_text(encoding="utf-8") == "24\n"


@pytest.mark.parametrize("template", ["workers", "mcp"])
def test_global_workers_entrypoint_requires_an_explicit_option(tmp_path, monkeypatch, template):
    dest = _generate(
        tmp_path,
        monkeypatch,
        template=template,
        extra_args=("--workers-entrypoint", "global"),
    )
    entry = (dest / "src/entry.py").read_text(encoding="utf-8")
    wrangler = (dest / "wrangler.toml").read_text(encoding="utf-8")

    assert "on_fetch = to_workers_global(app)" in entry
    assert "Default =" not in entry
    assert '"disable_python_no_global_handlers"' in wrangler
    assert "HTTP-only" in (dest / "README.md").read_text(encoding="utf-8")


def test_rejects_global_workers_entrypoint_for_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main(
            [
                "demo-app",
                "--template",
                "api",
                "--no-input",
                "--workers-entrypoint",
                "global",
            ]
        )
    assert not (tmp_path / "demo-app").exists()


@pytest.mark.parametrize(
    ("template", "extra_args", "dependency"),
    [
        ("api", (), '"hayate>=0.12.1,<0.13"'),
        ("workers", (), '"hayate>=0.12.1,<0.13"'),
        ("mcp", (), '"hayate-mcp>=0.11,<0.12"'),
        ("api", ("--with", "openapi"), '"hayate-openapi>=0.5,<0.6"'),
        ("api", ("--with", "sql"), '"hayate-sql>=0.1,<0.2"'),
    ],
)
def test_composed_projects_pin_released_compatibility_lines(
    tmp_path,
    monkeypatch,
    template,
    extra_args,
    dependency,
):
    dest = _generate(tmp_path, monkeypatch, template=template, extra_args=extra_args)
    assert dependency in (dest / "pyproject.toml").read_text(encoding="utf-8")


def test_openapi_feature_overlays_typed_todo_contracts(tmp_path, monkeypatch):
    minimal = _generate(tmp_path, monkeypatch, name="minimal", template="api")
    typed = _generate(
        tmp_path,
        monkeypatch,
        name="typed",
        template="api",
        extra_args=("--with", "openapi"),
    )

    minimal_api = (minimal / "src/todo_api.py").read_text(encoding="utf-8")
    typed_api = (typed / "src/todo_api.py").read_text(encoding="utf-8")
    assert "def _validated_todo_id" in minimal_api
    assert "from hayate_openapi import Path, StdlibProvider, endpoint, validated" in typed_api
    assert "providers=_PROVIDERS" in typed_api
    assert 'Path(alias="id")' in typed_api
    assert "-> TodoResponse" in typed_api
    assert "def _validated_todo_id" not in typed_api


def _load_workers_launcher(dest):
    spec = importlib.util.spec_from_file_location(
        "generated_manage_workers",
        dest / "manage_workers.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workers_launcher_rejects_unsupported_node(tmp_path, monkeypatch, capsys):
    launcher = _load_workers_launcher(
        _generate(tmp_path, monkeypatch, template="workers"),
    )
    monkeypatch.setattr(launcher, "_node_version", lambda: "v26.0.0")

    assert launcher.main(["dev"]) == 2
    assert "requires Node.js 24" in capsys.readouterr().err


def test_workers_launcher_proxies_supported_node(tmp_path, monkeypatch):
    launcher = _load_workers_launcher(
        _generate(tmp_path, monkeypatch, template="workers"),
    )
    monkeypatch.setattr(launcher, "_node_version", lambda: "v24.18.0")
    monkeypatch.setattr(launcher.shutil, "which", lambda _name: "/bin/pywrangler")
    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda command, **_kwargs: (
            SimpleNamespace(returncode=7)
            if command[0] == "/bin/pywrangler"
            else pytest.fail(f"unexpected command: {command}")
        ),
    )

    assert launcher.main(["deploy", "--dry-run"]) == 7


def test_workers_launcher_uses_node_compatibility_shim(tmp_path, monkeypatch):
    launcher = _load_workers_launcher(
        _generate(tmp_path, monkeypatch, template="workers"),
    )
    monkeypatch.setenv("UV_PYTHON", "3.13.11")
    monkeypatch.setattr(launcher, "_node_version", lambda: "v24.18.0")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: f"/bin/{name}")
    observed = {}

    def run(command, **kwargs):
        observed["command"] = command
        observed["environment"] = kwargs["env"]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launcher.subprocess, "run", run)

    assert launcher.main(["dev"]) == 0
    environment = observed["environment"]
    assert observed["command"] == ["/bin/pywrangler", "dev"]
    assert "UV_PYTHON" not in environment
    assert environment["CREATE_HAYATE_REAL_NODE"] == "/bin/node"
    shim_dir = Path(environment["PATH"].split(launcher.os.pathsep)[0])
    assert shim_dir.name.startswith("create-hayate-node-")


def test_api_and_workers_share_one_base_application(tmp_path, monkeypatch):
    api = _generate(tmp_path, monkeypatch, name="proj-alpha", template="api")
    workers = _generate(tmp_path, monkeypatch, name="proj-beta", template="workers")
    read = lambda directory, path: (  # noqa: E731
        (directory / path).read_text(encoding="utf-8").replace(directory.name, "X")
    )
    assert read(api, "src/app.py") == read(workers, "src/app.py")
    assert read(api, "tests/test_app.py") == read(workers, "tests/test_app.py")


def test_mcp_template_is_a_workers_runtime_plus_the_mcp_component(tmp_path, monkeypatch):
    dest = _generate(tmp_path, monkeypatch, template="mcp")
    project = (dest / "pyproject.toml").read_text(encoding="utf-8")
    registrations = (dest / "src/generated_features.py").read_text(encoding="utf-8")

    assert '"hayate-mcp>=0.11,<0.12"' in project
    assert (dest / "src/feature_mcp.py").is_file()
    assert "register_mcp(app)" in registrations
    assert (dest / "manage_workers.py").is_file()


def test_every_supported_feature_combination_generates_from_components(tmp_path, monkeypatch):
    names = sorted(FEATURES)
    combinations = [
        combination
        for size in range(len(names) + 1)
        for combination in itertools.combinations(names, size)
    ]
    observed = 0
    for runtime in ("api", "workers"):
        auths = ("none",) if runtime == "api" else ("none", "cloudflare-access")
        entrypoints = ("class",) if runtime == "api" else ("class", "global")
        for auth, combination, entrypoint in itertools.product(
            auths,
            combinations,
            entrypoints,
        ):
            observed += 1
            name = f"case-{observed}"
            args = ["--with", ",".join(combination)] if combination else []
            if auth != "none":
                args.extend(["--auth", auth])
            if entrypoint == "global":
                args.extend(["--workers-entrypoint", "global"])
            dest = _generate(
                tmp_path,
                monkeypatch,
                name=name,
                template=runtime,
                extra_args=tuple(args),
            )
            assert (dest / "src/app.py").is_file()
            for feature in combination:
                if feature == "sql":
                    assert (dest / "src/queries.py").is_file()
                else:
                    assert (dest / f"src/feature_{feature}.py").is_file()
            if auth == "cloudflare-access":
                assert (dest / "src/feature_access.py").is_file()
            entry = (dest / "src/entry.py").read_text() if runtime == "workers" else ""
            assert ("on_fetch =" in entry) is (entrypoint == "global")
    assert observed == 40


def test_production_preset_composes_the_complete_golden_path(tmp_path, monkeypatch):
    dest = _generate(
        tmp_path,
        monkeypatch,
        template="workers",
        extra_args=("--preset", "production"),
    )
    project = (dest / "pyproject.toml").read_text(encoding="utf-8")
    wrangler = (dest / "wrangler.toml").read_text(encoding="utf-8")
    registrations = (dest / "src/generated_features.py").read_text(encoding="utf-8")

    for dependency in ("hayate-openapi", "hayate-mcp", "hayate-sql"):
        assert dependency in project
    for component in ("access", "production", "mcp", "openapi"):
        assert f"register_{component}(app)" in registrations
    assert "[[d1_databases]]" in wrangler
    assert "[[ratelimits]]" in wrangler
    assert "[env.production.vars]" in wrangler
    assert "[[env.production.d1_databases]]" in wrangler
    assert 'ENVIRONMENT = "production"' in wrangler
    assert (dest / ".dev.vars").read_text(encoding="utf-8").startswith("ENVIRONMENT=local")
    assert ".dev.vars" in (dest / ".gitignore").read_text(encoding="utf-8")
    assert (dest / "PRODUCTION.md").is_file()
    assert (dest / "migrations/0001_create_todos.sql").is_file()
    assert (dest / "scripts/export_api.sh").is_file()


def test_production_preset_supports_the_explicit_global_http_entrypoint(
    tmp_path,
    monkeypatch,
):
    dest = _generate(
        tmp_path,
        monkeypatch,
        template="workers",
        extra_args=("--preset", "production", "--workers-entrypoint", "global"),
    )
    assert "on_fetch = to_workers_global(app)" in (dest / "src/entry.py").read_text()


@pytest.mark.parametrize(
    "args",
    [
        ("--template", "api", "--auth", "cloudflare-access"),
        ("--template", "api", "--preset", "production"),
        ("--template", "mcp", "--preset", "production"),
        ("--template", "workers", "--preset", "production", "--auth", "none"),
        ("--template", "workers", "--with", "unknown"),
        ("--template", "workers", "--with", ","),
        ("--template", "api", "--frontend", "vue"),
    ],
)
def test_unsupported_combinations_fail_before_writing(tmp_path, monkeypatch, capsys, args):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main(["demo-app", "--no-input", *args])
    assert not (tmp_path / "demo-app").exists()
    assert "error:" in capsys.readouterr().err


def test_rejects_existing_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demo-app").mkdir()
    with pytest.raises(SystemExit):
        main(["demo-app", "--template", "api", "--no-input"])


@pytest.mark.parametrize(
    "name",
    ["My-App", "app_x", "1app", "-app", "app!", "", "mcp", "hayate-sql"],
)
def test_rejects_invalid_names(tmp_path, monkeypatch, name):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main([name, "--template", "api", "--no-input"])


def test_non_tty_defaults_to_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO())
    assert main(["demo-app"]) == 0
    assert not (tmp_path / "demo-app" / "wrangler.toml").exists()


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("", "api"),
        ("1", "api"),
        ("2", "workers"),
        ("3", "mcp"),
        ("workers", "workers"),
        ("mcp", "mcp"),
    ],
)
def test_choose_template_answers(monkeypatch, capsys, answer, expected):
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)
    assert cli._choose_template() == expected


def test_choose_template_reprompts_until_valid(monkeypatch, capsys):
    answers = iter(["nope", "9", "3"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cli._choose_template() == "mcp"


def _file_tree(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_implicit_frontend_none_preserves_the_explicit_none_output(tmp_path, monkeypatch):
    implicit_root = tmp_path / "implicit"
    explicit_root = tmp_path / "explicit"
    implicit_root.mkdir()
    explicit_root.mkdir()

    implicit = _generate(implicit_root, monkeypatch)
    explicit = _generate(
        explicit_root,
        monkeypatch,
        extra_args=("--frontend", "none"),
    )

    assert _file_tree(implicit) == _file_tree(explicit)
    assert not (implicit / "frontend").exists()


def test_frontend_source_trees_cannot_duplicate_backend_paths():
    templates = Path(cli.__file__).parent / "templates"
    backend_roots = [
        templates / "base",
        templates / "workers",
        templates / "production",
        *(templates / "features").iterdir(),
        *(templates / "auth").iterdir(),
    ]
    backend_paths = {
        path.relative_to(root)
        for root in backend_roots
        for path in root.rglob("*")
        if path.is_file()
    }

    frontends = templates / "frontends"
    for frontend in set(FRONTENDS) - {"none"}:
        paths = {
            path.relative_to(frontends / frontend)
            for path in (frontends / frontend).rglob("*")
            if path.is_file()
        }
        assert paths
        assert paths.isdisjoint(backend_paths)


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_htmx_profile_generates_a_runnable_same_origin_application(
    tmp_path,
    monkeypatch,
    template,
):
    dest = _generate(
        tmp_path,
        monkeypatch,
        template=template,
        extra_args=("--frontend", "htmx"),
    )

    for expected in (
        "frontend/profile.toml",
        "src/feature_htmx.py",
        "templates/app/page.html",
        "templates/auth/page.html",
        "public/assets/app.css",
        "public/assets/app.js",
        "public/assets/vendor/htmx-2.0.10.min.js",
        "public/_headers",
        "tests/test_htmx.py",
        "tests/browser/test_htmx_browser.py",
    ):
        assert (dest / expected).is_file(), expected

    project = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert '"playwright>=1.54,<2"' in project
    registrations = (dest / "src/generated_features.py").read_text(encoding="utf-8")
    assert "register_htmx(app)" in registrations
    application = (dest / "src/app.py").read_text(encoding="utf-8")
    todo_api = (dest / "src/todo_api.py").read_text(encoding="utf-8")
    assert '@app.get("/api/health")' in application
    assert '@app.get("/api/todos")' in todo_api
    profile = (dest / "frontend/profile.toml").read_text(encoding="utf-8")
    assert "71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de" in profile

    wrangler = dest / "wrangler.toml"
    if template == "api":
        assert not wrangler.exists()
        assert not (dest / "src/hayate_htmx").exists()
        assert '"hayate-htmx>=0.1,<0.2"' in project
        assert "hayate-htmx @ git+" not in project
    else:
        assert '"jinja2==3.1.6"' in project
        assert "hayate-htmx @ git+" not in project
        assert (dest / "src/hayate_htmx/__init__.py").is_file()
        assert (dest / "src/htmx_worker_renderer.py").is_file()
        assert (dest / "scripts/embed_htmx_templates.py").is_file()
        launcher = (dest / "manage_workers.py").read_text(encoding="utf-8")
        assert 'scripts/embed_htmx_templates.py"' in launcher
        config = wrangler.read_text(encoding="utf-8")
        assert '[assets]\ndirectory = "./public"\nbinding = "ASSETS"' in config
        assert '"/app/*"' in config


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_react_profile_generates_a_typed_same_origin_spa(
    tmp_path,
    monkeypatch,
    template,
):
    dest = _generate(
        tmp_path,
        monkeypatch,
        template=template,
        extra_args=("--frontend", "react"),
    )

    for expected in (
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/openapi.json",
        "frontend/src/api/schema.d.ts",
        "frontend/src/api/client.ts",
        "frontend/src/App.tsx",
        "frontend/public/_headers",
        "frontend/scripts/sync-openapi.mjs",
        "frontend/tests/smoke.spec.ts",
        "frontend/.node-version",
        "frontend/.gitignore",
        "scripts/export_api.sh",
        "src/feature_openapi.py",
    ):
        assert (dest / expected).is_file(), expected

    project = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert '"hayate-openapi>=0.5,<0.6"' in project
    assert "register_openapi(app)" in (dest / "src/generated_features.py").read_text(
        encoding="utf-8"
    )
    application = (dest / "src/app.py").read_text(encoding="utf-8")
    todo_api = (dest / "src/todo_api.py").read_text(encoding="utf-8")
    assert '@app.get("/api/health")' in application
    assert '@app.get("/api/todos")' in todo_api

    package = (dest / "frontend/package.json").read_text(encoding="utf-8")
    lock = (dest / "frontend/package-lock.json").read_text(encoding="utf-8")
    assert '"name": "demo-app-web"' in package
    assert '"name": "demo-app-web"' in lock
    for dependency in (
        '"react": "19.2.8"',
        '"react-router": "8.3.0"',
        '"openapi-typescript": "7.13.0"',
        '"openapi-fetch": "0.17.0"',
    ):
        assert dependency in package
    assert '"api:check": "node scripts/sync-openapi.mjs --check"' in package

    client = (dest / "frontend/src/api/client.ts").read_text(encoding="utf-8")
    assert 'from "./schema"' in client
    assert 'credentials: "include"' in client
    assert "interface Todo" not in client
    schema = (dest / "frontend/src/api/schema.d.ts").read_text(encoding="utf-8")
    assert '"/api/todos"' in schema
    assert "export type $defs" in schema
    document = (dest / "frontend/openapi.json").read_text(encoding="utf-8")
    assert '"title": "demo-app"' in document
    assert '"/api/todos"' in document
    playwright = (dest / "frontend/playwright.config.ts").read_text(encoding="utf-8")
    vite = (dest / "frontend/vite.config.ts").read_text(encoding="utf-8")
    assert "HAYATE_E2E_BACKEND_PORT" in playwright
    assert "HAYATE_E2E_FRONTEND_PORT" in playwright
    assert "reuseExistingServer: !process.env.CI && !isolated" in playwright
    assert "process.env.HAYATE_DEV_ORIGIN" in vite

    wrangler = dest / "wrangler.toml"
    if template == "api":
        assert not wrangler.exists()
    else:
        config = wrangler.read_text(encoding="utf-8")
        assert 'directory = "./frontend/dist"' in config
        assert 'not_found_handling = "single-page-application"' in config
        assert 'run_worker_first = ["/api/*"' in config


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_astro_profile_generates_a_static_site_with_a_runtime_island(
    tmp_path,
    monkeypatch,
    template,
):
    dest = _generate(
        tmp_path,
        monkeypatch,
        template=template,
        extra_args=("--frontend", "astro"),
    )

    for expected in (
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/openapi.json",
        "frontend/src/api/schema.d.ts",
        "frontend/src/api/client.ts",
        "frontend/src/components/WorkspaceIsland.tsx",
        "frontend/src/data/public.ts",
        "frontend/src/pages/index.astro",
        "frontend/src/pages/principles.astro",
        "frontend/src/pages/404.astro",
        "frontend/scripts/check-static-output.mjs",
        "frontend/scripts/sync-openapi.mjs",
        "frontend/tests/smoke.spec.ts",
        "frontend/public/_headers",
        "frontend/.node-version",
        "frontend/.gitignore",
        "src/feature_openapi.py",
    ):
        assert (dest / expected).is_file(), expected

    project = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert '"hayate-openapi>=0.5,<0.6"' in project
    assert "register_openapi(app)" in (dest / "src/generated_features.py").read_text(
        encoding="utf-8"
    )
    application = (dest / "src/app.py").read_text(encoding="utf-8")
    todo_api = (dest / "src/todo_api.py").read_text(encoding="utf-8")
    assert '@app.get("/api/health")' in application
    assert '@app.get("/api/todos")' in todo_api

    package = (dest / "frontend/package.json").read_text(encoding="utf-8")
    for dependency in (
        '"astro": "7.1.3"',
        '"@astrojs/preact": "6.0.1"',
        '"preact": "10.29.7"',
        '"openapi-typescript": "7.13.0"',
        '"openapi-fetch": "0.17.0"',
    ):
        assert dependency in package
    assert '"output: \\"static\\""' not in package
    assert 'output: "static"' in (dest / "frontend/astro.config.mjs").read_text(encoding="utf-8")

    island = (dest / "frontend/src/components/WorkspaceIsland.tsx").read_text(encoding="utf-8")
    page = (dest / "frontend/src/pages/index.astro").read_text(encoding="utf-8")
    client = (dest / "frontend/src/api/client.ts").read_text(encoding="utf-8")
    assert "useEffect" in island
    assert "listTodos()" in island
    assert "<WorkspaceIsland client:visible />" in page
    assert 'from "./schema"' in client
    assert 'credentials: "include"' in client
    assert not (dest / "frontend/src/pages/api").exists()
    assert not any((dest / "frontend/src").rglob("_actions.*"))
    assert "interface Todo" not in island

    document = (dest / "frontend/openapi.json").read_text(encoding="utf-8")
    schema = (dest / "frontend/src/api/schema.d.ts").read_text(encoding="utf-8")
    assert '"title": "demo-app"' in document
    assert '"/api/todos"' in document
    assert '"/api/todos"' in schema
    playwright = (dest / "frontend/playwright.config.ts").read_text(encoding="utf-8")
    assert "HAYATE_E2E_BACKEND_PORT" in playwright
    assert "HAYATE_E2E_FRONTEND_PORT" in playwright
    assert "reuseExistingServer: !process.env.CI && !isolated" in playwright

    wrangler = dest / "wrangler.toml"
    if template == "api":
        assert not wrangler.exists()
    else:
        config = wrangler.read_text(encoding="utf-8")
        assert 'directory = "./frontend/dist"' in config
        assert 'not_found_handling = "404-page"' in config
        assert 'html_handling = "auto-trailing-slash"' in config
        assert 'run_worker_first = ["/api/*"' in config


@pytest.mark.parametrize("frontend", ["react", "astro"])
def test_typed_frontend_contract_includes_optional_mcp_routes(
    tmp_path,
    monkeypatch,
    frontend,
):
    dest = _generate(
        tmp_path,
        monkeypatch,
        extra_args=("--frontend", frontend, "--with", "mcp"),
    )

    document = (dest / "frontend/openapi.json").read_text(encoding="utf-8")
    schema = (dest / "frontend/src/api/schema.d.ts").read_text(encoding="utf-8")
    assert '"/mcp"' in document
    assert '"/mcp"' in schema
    assert "get_mcp" in schema
    assert "post_mcp" in schema
    assert "delete_mcp" in schema


def test_frontend_overlay_collision_fails_without_overwriting(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    (source / "src").mkdir(parents=True)
    (destination / "src").mkdir(parents=True)
    (source / "src/app.py").write_text("frontend", encoding="utf-8")
    existing = destination / "src/app.py"
    existing.write_text("backend", encoding="utf-8")

    with pytest.raises(FileExistsError, match="frontend overlay would overwrite"):
        cli._render_tree(source, destination, {}, allow_overwrite=False)

    assert existing.read_text(encoding="utf-8") == "backend"


@pytest.mark.parametrize("frontend", sorted(set(FRONTENDS) - {"none"}))
def test_frontend_production_contract_fails_before_writing(
    tmp_path,
    monkeypatch,
    capsys,
    frontend,
):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        main(
            [
                "demo-app",
                "--template",
                "workers",
                "--preset",
                "production",
                "--frontend",
                frontend,
                "--no-input",
            ]
        )

    assert not (tmp_path / "demo-app").exists()
    assert "cannot yet be combined with --preset production" in capsys.readouterr().err
