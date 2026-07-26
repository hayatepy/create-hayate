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
    "mcp": "MCP 2025-11-25 on ASGI and Cloudflare Workers",
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
    parser.add_argument(
        "--workers-entrypoint",
        choices=("class", "global"),
        default="class",
        help=(
            "Workers handler shape: the feature-complete WorkerEntrypoint class "
            "(default), or the explicit HTTP-only global compatibility path"
        ),
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

    if template == "api" and args.workers_entrypoint != "class":
        parser.error("--workers-entrypoint applies only to workers and mcp templates")

    global_entrypoint = args.workers_entrypoint == "global"
    variables = {
        "project_name": args.name,
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
    }
    src = files("create_hayate").joinpath("templates", template)
    try:
        _render_tree(src, dest, variables)
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
