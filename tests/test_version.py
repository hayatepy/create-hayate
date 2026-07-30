import re
import tomllib
from importlib.metadata import version
from pathlib import Path

from create_hayate import __version__

ROOT = Path(__file__).resolve().parents[1]
_PUBLIC_HOME = "https://hayatepy.dev/"
_PUBLIC_FIRST_APP = "https://hayatepy.dev/get-started/first-app/"
_PUBLIC_COMPATIBILITY = "https://hayatepy.dev/evidence/compatibility/"
_SUPERSEDED_DOCS_PREFIX = "https://github.com/hayatepy/.github/blob/main/docs/"


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


def test_public_discovery_metadata_uses_the_canonical_site() -> None:
    project = _project()
    assert project["urls"]["Homepage"] == _PUBLIC_FIRST_APP

    for public_entry_point in (
        ROOT / "README.md",
        ROOT / "src/create_hayate/templates/base/README.md",
    ):
        content = public_entry_point.read_text(encoding="utf-8")
        assert f"[Start here]({_PUBLIC_HOME})" in content
        assert f"[Tested compatibility]({_PUBLIC_COMPATIBILITY})" in content
        assert _SUPERSEDED_DOCS_PREFIX not in content


def test_frontend_evidence_routes_to_canonical_compatibility() -> None:
    for relative_path in (
        "docs/FRONTEND_COMPATIBILITY.md",
        "scripts/check_frontend_matrix.py",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert _PUBLIC_COMPATIBILITY in content
        assert _SUPERSEDED_DOCS_PREFIX not in content
