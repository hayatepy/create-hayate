from importlib.metadata import version

from create_hayate import __version__


def test_public_version_matches_installed_distribution() -> None:
    assert __version__ == version("create-hayate")
