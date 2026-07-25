"""Remove the obsolete Node flag still emitted by current Pywrangler."""

from __future__ import annotations

import os
import sys


def main() -> None:
    real_node = os.environ["CREATE_HAYATE_REAL_NODE"]
    arguments = [arg for arg in sys.argv[1:] if arg != "--experimental-wasm-stack-switching"]
    os.execv(real_node, [real_node, *arguments])


if __name__ == "__main__":
    main()
