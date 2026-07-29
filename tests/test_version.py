import re
import tomllib
from importlib.metadata import version
from pathlib import Path

from create_hayate import __version__

ROOT = Path(__file__).resolve().parents[1]


def _project() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as source:
        return tomllib.load(source)["project"]


def test_public_version_matches_installed_distribution() -> None:
    project_version = _project()["version"]
    assert __version__ == project_version == version("create-hayate")


def test_readme_release_line_matches_project_version() -> None:
    project_version = _project()["version"]
    expected_line = ".".join(project_version.split(".")[:2])
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"Status: alpha \((\d+\.\d+)\.x\)", readme)
    assert match is not None
    assert match.group(1) == expected_line


def test_zero_dependency_cli_claim_matches_project_metadata() -> None:
    dependencies = _project()["dependencies"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ("**Zero-dependency CLI.**" in readme) is (not dependencies)
