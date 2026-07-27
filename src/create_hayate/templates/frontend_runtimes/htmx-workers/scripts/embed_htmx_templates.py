"""Embed canonical Jinja files into the Python modules uploaded to Workers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
OUTPUT = ROOT / "src" / "htmx_worker_templates.py"


def main() -> int:
    files = sorted(path for path in TEMPLATES.rglob("*") if path.is_file())
    if not files:
        raise RuntimeError(f"no templates found under {TEMPLATES}")
    lines = [
        '"""Generated from templates/ by scripts/embed_htmx_templates.py."""',
        "",
        "TEMPLATES: dict[str, str] = {",
    ]
    for path in files:
        name = path.relative_to(TEMPLATES).as_posix()
        lines.append(f"    {name!r}: {path.read_text(encoding='utf-8')!r},")
    lines.extend(("}", ""))
    OUTPUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
