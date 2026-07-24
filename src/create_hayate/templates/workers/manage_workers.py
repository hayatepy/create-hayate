"""Run Pywrangler with the Node release supported by Python Workers."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence

SUPPORTED_NODE_MAJOR = 24


def _node_version() -> str | None:
    try:
        result = subprocess.run(
            ["node", "--experimental-wasm-stack-switching", "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    version = _node_version()
    try:
        major = int(version.removeprefix("v").split(".", 1)[0]) if version else None
    except ValueError:
        major = None
    if major != SUPPORTED_NODE_MAJOR:
        print(
            "Cloudflare Python Workers currently requires Node.js 24. "
            "Activate the version in .node-version or .nvmrc, then retry.",
            file=sys.stderr,
        )
        return 2

    pywrangler = shutil.which("pywrangler")
    if pywrangler is None:
        print(
            "Pywrangler is not installed. Run this command through `uv run`.",
            file=sys.stderr,
        )
        return 2
    return subprocess.run([pywrangler, *args], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
