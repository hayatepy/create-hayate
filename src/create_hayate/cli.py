"""The whole CLI. Zero dependencies by design: argparse + shutil + string.Template.

Template trees live in ``templates/<name>/`` inside this package and are copied
file by file through ``string.Template`` (``$project_name`` is the only
variable). Keeping the machinery this small is a feature — see DESIGN.md.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from string import Template

TEMPLATES: dict[str, str] = {
    "api": "TODO API + pytest, served by uvicorn",
    "workers": "the same app on Cloudflare Python Workers",
}
DEFAULT_TEMPLATE = "api"

# One name serves as directory, distribution, and Workers service name,
# so enforce the strictest of the three.
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")

# Bundled name -> generated name. Build backends drop dotfiles from wheels,
# so dotfiles are bundled without the leading dot.
_RENAMES = {
    "gitignore": ".gitignore",
    "node-version": ".node-version",
    "nvmrc": ".nvmrc",
}

_SKIP_DIRS = {"__pycache__"}


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="create-hayate",
        description="Scaffold a hayate project that is tested from minute one.",
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
    args = parser.parse_args(argv)

    if not _NAME_RE.match(args.name):
        parser.error(
            f"invalid project name {args.name!r}: use lowercase letters, digits, and"
            " hyphens, starting with a letter (the name doubles as the Workers"
            " service name)"
        )
    dest = Path.cwd() / args.name
    if dest.exists():
        parser.error(f"{dest} already exists")

    template = args.template
    if template is None:
        interactive = not args.no_input and sys.stdin is not None and sys.stdin.isatty()
        template = _choose_template() if interactive else DEFAULT_TEMPLATE

    src = files("create_hayate").joinpath("templates", template)
    try:
        _render_tree(src, dest, {"project_name": args.name})
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    serve = (
        "uv run uvicorn app:app --reload"
        if template == "api"
        else "uv run python manage_workers.py dev"
    )
    print(f"\nCreated {args.name}/ from the {template} template. Next:\n")
    print(f"  cd {args.name}")
    print("  uv run pytest")
    print(f"  {serve}")
    return 0
