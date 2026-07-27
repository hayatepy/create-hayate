"""Run Pywrangler with the Node release supported by Python Workers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

SUPPORTED_NODE_MAJOR = 24


def _node_version() -> str | None:
    try:
        result = subprocess.run(
            ["node", "--version"],
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
$workers_preflight
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

    real_node = shutil.which("node")
    if real_node is None:
        return 2
    with tempfile.TemporaryDirectory(prefix="create-hayate-node-") as raw_shim_dir:
        shim_dir = Path(raw_shim_dir)
        environment = os.environ.copy()
        environment["CREATE_HAYATE_REAL_NODE"] = real_node
        environment["CREATE_HAYATE_NODE_SHIM_PYTHON"] = sys.executable
        environment["CREATE_HAYATE_NODE_SHIM_SCRIPT"] = str(
            Path(__file__).with_name("node_compat.py")
        )
        environment["PATH"] = f"{shim_dir}{os.pathsep}{environment.get('PATH', '')}"

        if os.name == "nt":
            (shim_dir / "node.cmd").write_text(
                '@"%CREATE_HAYATE_NODE_SHIM_PYTHON%" "%CREATE_HAYATE_NODE_SHIM_SCRIPT%" %*\r\n',
                encoding="utf-8",
            )
        else:
            wrapper = shim_dir / "node"
            wrapper.write_text(
                '#!/bin/sh\nexec "$$CREATE_HAYATE_NODE_SHIM_PYTHON" '
                '"$$CREATE_HAYATE_NODE_SHIM_SCRIPT" "$$@"\n',
                encoding="utf-8",
            )
            wrapper.chmod(0o755)

        return subprocess.run([pywrangler, *args], check=False, env=environment).returncode


if __name__ == "__main__":
    raise SystemExit(main())
