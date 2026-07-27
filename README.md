# create-hayate

> **Hayate ecosystem:** [Start here](https://github.com/hayatepy/.github/blob/main/docs/START.md)
> · [Production golden app](https://github.com/hayatepy/golden-app)
> · [Tested compatibility](https://github.com/hayatepy/.github/blob/main/docs/COMPATIBILITY.md)

Composable, production-oriented project scaffolding for
[hayate](https://github.com/hayatepy/hayate).

The golden path creates one application core with API routes, OpenAPI/Scalar,
MCP 2025-11-25, checked SQL, Cloudflare Access identity, SQLite on ASGI, and
D1 on Cloudflare Workers:

```sh
uvx create-hayate my-app --template workers --preset production
cd my-app
uv run pytest
uv run python manage_workers.py d1 migrations apply DB --local
uv run python manage_workers.py dev
```

The generated README keeps the scaffold-to-start path under ten documented
minutes and includes a fail-closed production checklist.

## Runtimes

| Template | Runtime | Default composition |
|---|---|---|
| `api` (default) | ASGI | Tested TODO API |
| `workers` | ASGI and Cloudflare Python Workers | The same tested API |
| `mcp` | ASGI and Workers | `workers` + the MCP component |

`mcp` remains a compatibility shortcut. It is not a copied template.

## Features

Compose features explicitly instead of choosing from a template matrix:

```sh
uvx create-hayate my-app \
  --template workers \
  --with openapi,mcp,sql \
  --auth cloudflare-access
```

| Feature | Generated boundary |
|---|---|
| `openapi` | OpenAPI 3.1.1, hardened Scalar, pinned TypeScript export |
| `mcp` | MCP 2025-11-25 tools sharing request identity and storage |
| `sql` | Migration-checked `hayate-sql`; SQLite on ASGI and D1 on Workers |
| `--auth cloudflare-access` | Local explicit identity; production RS256/JWKS verification |

All 40 supported runtime/feature/auth/entrypoint combinations, plus both
production entrypoints, are generated, dependency resolved, and imported in
CI. Invalid combinations fail before the destination directory is written;
for example, Cloudflare Access production verification requires the Workers
runtime.

## Production preset

`--preset production` is the reviewed composition of:

- `openapi,mcp,sql`;
- Cloudflare Access identity;
- exact-origin CORS;
- secure response headers and a 1 MiB request-body ceiling;
- a Cloudflare native rate-limit binding;
- D1 migration and deployment configuration;
- explicit secret, identity, CORS, abuse, observability, migration, and rollout
  checks in `PRODUCTION.md`.

Local CI drives the generated preset over both real ASGI HTTP and real workerd.
The workerd path applies a real D1 migration, writes through the HTTP API, and
reads the same authenticated data through MCP.

## Design

- **Zero-dependency CLI.** Generation uses only the standard library and
  bundled, versioned components; it performs no network fetch.
- **Small composition surface.** One base app, one Workers runtime overlay,
  three feature components, and explicit auth/production components replace
  copied full-template combinations.
- **Portable application core.** `src/app.py` does not change between ASGI and
  Workers. Runtime resources enter through the Hayate request context.
- **Feature-complete Workers default.** `WorkerEntrypoint` remains the default.
  HTTP-only services can explicitly request `--workers-entrypoint global`.
- **Evidence over claims.** CI runs unit tests, every dependency composition,
  real ASGI, real workerd, D1 migrations, MCP, workflow audit, and dependency
  audit.

The internal design memo (Japanese, per project convention) is
[DESIGN.md](DESIGN.md); release history is in [CHANGELOG.md](CHANGELOG.md).

> **Status: alpha (0.5.x).** Generated projects pin released compatibility
> lines. Public APIs may still move before 1.0.

## License

MIT
