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
| `openapi` | Typed UUID/response contracts, OpenAPI 3.1.1, hardened Scalar, pinned TypeScript export |
| `mcp` | MCP 2025-11-25 tools sharing request identity and storage |
| `sql` | Migration-checked `hayate-sql`; SQLite on ASGI and D1 on Workers |
| `--auth cloudflare-access` | Local explicit identity; production RS256/JWKS verification |

All 40 supported runtime/feature/auth/entrypoint combinations, plus both
production entrypoints, are generated, dependency resolved, and imported in
CI. Invalid combinations fail before the destination directory is written;
for example, Cloudflare Access production verification requires the Workers
runtime.

## Frontends

Frontend choice is independent from runtime, authentication, and optional
backend features:

```sh
uvx create-hayate my-app \
  --template workers \
  --frontend htmx \
  --with openapi,sql
```

| Frontend | Ownership boundary |
|---|---|
| `none` (default) | Backend-only output; byte-for-byte compatibility path |
| `htmx` | Executable Hayate + htmx app at `/app`; shared JSON API at `/api` |
| `react` | Vite/React Router SPA with generated, drift-checked API types |
| `astro` | A separate static/hybrid site consumes an explicit Hayate API |

The frontend layer is composed last and is forbidden from overwriting backend
files. `htmx` generates autoescaping Jinja templates, identity-scoped CRUD,
validation fragments, history restoration, SSE, CSP/CSRF/cache defaults,
browser smoke tests, and a checksum-verified self-hosted htmx 2.0.10 asset.
ASGI serves that asset through Hayate; Workers uses Cloudflare Static Assets
with the same same-origin URLs. Until `hayate-htmx` is published, ASGI pins
its immutable release-gate Git commit and Workers bundles the same small
source snapshot to work around Pywrangler's VCS-lock installation gap.

`react` generates a pinned Node 24/Vite/React Router application in
`frontend/`. It enables Hayate OpenAPI automatically, keeps JSON below `/api`,
derives the `openapi-fetch` client entirely from checked-in generated types,
and fails CI when the OpenAPI document drifts. Vite proxies `/api` locally;
the Workers template serves the production build through Cloudflare Static
Assets with API-first routing and SPA deep-link fallback. `npm ci`, typecheck,
build, dependency audit, Chromium CRUD, and real-workerd routing are exercised
in CI. Astro retains a metadata-only ownership boundary until its
profile-specific change lands. Non-`none` profiles are rejected with the
production preset until each profile has a reviewed production contract.

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
- **Orthogonal frontend ownership.** Runtime and backend features compose
  first; one frontend overlay may add only non-colliding files. htmx calls the
  same domain and storage functions as the JSON API; React consumes generated
  OpenAPI types without introducing a second backend.
- **Portable application core.** `src/app.py` does not change between ASGI and
  Workers. Runtime resources enter through the Hayate request context.
- **Feature-complete Workers default.** `WorkerEntrypoint` remains the default.
  HTTP-only services can explicitly request `--workers-entrypoint global`.
- **Evidence over claims.** CI runs unit tests, every dependency composition,
  real ASGI, real workerd, D1 migrations, MCP, workflow audit, and dependency
  audit.

The internal design memo (Japanese, per project convention) is
[DESIGN.md](DESIGN.md); release history is in [CHANGELOG.md](CHANGELOG.md).

> **Status: alpha (0.6.x).** Generated projects pin released compatibility
> lines. Public APIs may still move before 1.0.

## License

MIT
