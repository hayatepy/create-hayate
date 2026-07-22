# create-hayate

Project scaffolding for [hayate](https://github.com/hayatepy/hayate) —
`uvx create-hayate my-app` and you have a running, tested project in minutes.

```sh
uvx create-hayate my-app --template workers
cd my-app
uv run pytest        # green out of the box
uv run pywrangler dev
```

## Templates

| Name | What you get | Serve with |
|---|---|---|
| `api` (default) | TODO API + tests that call the app core directly | `uv run uvicorn app:app --reload` |
| `workers` | The same app on Cloudflare Python Workers | `uv run pywrangler dev` / `deploy` |

`lambda`, `mcp`, and `auth` templates follow as those packages ship.

## Design

- **Zero-dependency CLI** (stdlib only: argparse + `string.Template`), templates
  bundled in the package — no network fetch, works offline, version-pinned.
- Templates mirror the upstream `examples/` style, and CI generates every
  template and runs its test suite, so they can't rot.
- One question at most (the template); `--no-input` for scripts and CI.

The internal design memo (Japanese, per project convention) lives in
[DESIGN.md](DESIGN.md).

## License

MIT
