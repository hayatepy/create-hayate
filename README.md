# create-hayate

API, Cloudflare Workers, and MCP 2025-11-25 project scaffolding for
[hayate](https://github.com/hayatepy/hayate) — `uvx create-hayate my-app`
and you have a running, tested project in minutes.

```sh
uvx create-hayate my-app --template workers
cd my-app
uv run pytest        # green out of the box
uv run python manage_workers.py dev
```

## Templates

| Name | What you get | Serve with |
|---|---|---|
| `api` (default) | TODO API + tests that call the app core directly | `uv run uvicorn app:app --reload` |
| `workers` | The same app on Cloudflare Python Workers | `uv run python manage_workers.py dev` / `deploy` |
| `mcp` | MCP 2025-11-25 server shared by ASGI and Workers | Uvicorn or `manage_workers.py` |

The `mcp` template uses the Workers-native, schema-validated
[`hayate-mcp`](https://github.com/hayatepy/hayate-mcp) runtime on both
platforms. It does not require `hayate-auth`: connect an existing identity
provider through request context, or add the authorization server package
when the application owns authentication.

## Design

- **Zero-dependency CLI** (stdlib only: argparse + `string.Template`), templates
  bundled in the package — no network fetch, works offline, version-pinned.
- Templates mirror the upstream `examples/` style, and CI generates every
  template and runs its test suite, so they can't rot.
- The Workers template pins Python 3.13 and Node.js 24 to the versions used by
  workerd/Pywrangler, and its launcher fails fast on an unsupported Node
  runtime instead of producing an incomplete dependency bundle.
- One question at most (the template); `--no-input` for scripts and CI.

The internal design memo (Japanese, per project convention) lives in
[DESIGN.md](DESIGN.md); release history is in [CHANGELOG.md](CHANGELOG.md).

> **Status: alpha (0.2.x).** Generated API, Workers, and MCP projects are exercised
> in CI against their real dependency resolution and test suites.

## License

MIT
