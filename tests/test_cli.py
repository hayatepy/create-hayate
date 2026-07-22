import io

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


def test_workers_template_wires_wrangler(tmp_path, monkeypatch):
    dest = _generate(tmp_path, monkeypatch, template="workers")
    assert 'name = "demo-app"' in (dest / "wrangler.toml").read_text(encoding="utf-8")
    assert (dest / "entry.py").is_file()


def test_api_and_workers_share_the_same_app(tmp_path, monkeypatch):
    api = _generate(tmp_path, monkeypatch, name="proj-alpha", template="api")
    workers = _generate(tmp_path, monkeypatch, name="proj-beta", template="workers")
    read = lambda d, p: (d / p).read_text(encoding="utf-8").replace(d.name, "X")  # noqa: E731
    assert read(api, "app.py") == read(workers, "app.py")
    assert read(api, "tests/test_app.py") == read(workers, "tests/test_app.py")


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
    [("", "api"), ("1", "api"), ("2", "workers"), ("workers", "workers")],
)
def test_choose_template_answers(monkeypatch, capsys, answer, expected):
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)
    assert cli._choose_template() == expected


def test_choose_template_reprompts_until_valid(monkeypatch, capsys):
    answers = iter(["nope", "9", "2"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cli._choose_template() == "workers"
