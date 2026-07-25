import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from create_hayate import cli
from create_hayate.cli import TEMPLATES, main


def _generate(tmp_path, monkeypatch, name="demo-app", template="api"):
    monkeypatch.chdir(tmp_path)
    assert main([name, "--template", template, "--no-input"]) == 0
    return tmp_path / name


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_generates_a_complete_project(tmp_path, monkeypatch, template):
    dest = _generate(tmp_path, monkeypatch, template=template)
    for expected in ("pyproject.toml", "README.md", ".gitignore", "app.py", "tests/test_app.py"):
        assert (dest / expected).is_file(), expected
    assert 'name = "demo-app"' in (dest / "pyproject.toml").read_text(encoding="utf-8")


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_no_placeholder_survives_generation(tmp_path, monkeypatch, template):
    dest = _generate(tmp_path, monkeypatch, template=template)
    for path in dest.rglob("*"):
        if path.is_file():
            assert "$project_name" not in path.read_text(encoding="utf-8"), path


@pytest.mark.parametrize("template", ["workers", "mcp"])
def test_workers_templates_wire_wrangler(tmp_path, monkeypatch, template):
    dest = _generate(tmp_path, monkeypatch, template=template)
    assert 'name = "demo-app"' in (dest / "wrangler.toml").read_text(encoding="utf-8")
    assert (dest / "entry.py").is_file()
    assert (dest / "manage_workers.py").is_file()
    assert (dest / ".node-version").read_text(encoding="utf-8") == "24\n"
    assert (dest / ".nvmrc").read_text(encoding="utf-8") == "24\n"


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
    monkeypatch.setattr(launcher, "_node_version", lambda: "v24.18.0")
    monkeypatch.setattr(
        launcher.shutil,
        "which",
        lambda name: f"/bin/{name}",
    )
    observed = {}

    def run(command, **kwargs):
        observed["command"] = command
        observed["environment"] = kwargs["env"]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launcher.subprocess, "run", run)

    assert launcher.main(["dev"]) == 0
    environment = observed["environment"]
    assert observed["command"] == ["/bin/pywrangler", "dev"]
    assert environment["CREATE_HAYATE_REAL_NODE"] == "/bin/node"
    shim_dir = Path(environment["PATH"].split(launcher.os.pathsep)[0])
    assert shim_dir.name.startswith("create-hayate-node-")


def test_api_and_workers_share_the_same_app(tmp_path, monkeypatch):
    api = _generate(tmp_path, monkeypatch, name="proj-alpha", template="api")
    workers = _generate(tmp_path, monkeypatch, name="proj-beta", template="workers")
    read = lambda d, p: (d / p).read_text(encoding="utf-8").replace(d.name, "X")  # noqa: E731
    assert read(api, "app.py") == read(workers, "app.py")
    assert read(api, "tests/test_app.py") == read(workers, "tests/test_app.py")


def test_workers_profiles_share_the_same_launcher(tmp_path, monkeypatch):
    workers = _generate(tmp_path, monkeypatch, name="proj-workers", template="workers")
    mcp = _generate(tmp_path, monkeypatch, name="proj-mcp", template="mcp")

    assert (workers / "manage_workers.py").read_text() == (mcp / "manage_workers.py").read_text()
    assert (workers / "node_compat.py").read_text() == (mcp / "node_compat.py").read_text()


def test_mcp_template_uses_published_workers_runtime(tmp_path, monkeypatch):
    dest = _generate(tmp_path, monkeypatch, template="mcp")
    project = (dest / "pyproject.toml").read_text(encoding="utf-8")
    app = (dest / "app.py").read_text(encoding="utf-8")

    assert '"hayate-mcp>=0.10,<0.11"' in project
    assert "WorkerMcpMount" in app
    assert "get_request_context" in app
    assert '"taskSupport": "forbidden"' in app


def test_rejects_existing_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demo-app").mkdir()
    with pytest.raises(SystemExit):
        main(["demo-app", "--template", "api", "--no-input"])


@pytest.mark.parametrize("name", ["My-App", "app_x", "1app", "-app", "app!", ""])
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
