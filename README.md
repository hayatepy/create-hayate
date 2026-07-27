# create-hayate

> **Hayate ecosystem:** [Start here](https://github.com/hayatepy/.github/blob/main/docs/START.md)
> · [Production golden app](https://github.com/hayatepy/golden-app)
> · [Tested compatibility](https://github.com/hayatepy/.github/blob/main/docs/COMPATIBILITY.md)
> · [Frontend matrix](docs/FRONTEND_COMPATIBILITY.md)

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
  --with admin,openapi,mcp,sql \
  --auth cloudflare-access
```

| Feature | Generated boundary |
|---|---|
| `admin` | Explicit identity-scoped TODO operations UI with checked SQL, redacted audit history, safe branding, and accessible localized controls |
| `openapi` | Typed UUID/response contracts, OpenAPI 3.1.1, hardened Scalar, pinned TypeScript export |
| `mcp` | MCP 2025-11-25 tools sharing request identity and storage |
| `sql` | Migration-checked `hayate-sql`; SQLite on ASGI and D1 on Workers |
| `--auth cloudflare-access` | Local explicit identity; production RS256/JWKS verification |

`admin` implies `sql` and Cloudflare Access and is currently limited to the
Workers template with `--frontend none`; that template still runs unchanged
through ASGI for local and fallback verification. The generator creates no
anonymous mode or default superuser. Operators are an explicit
case-insensitive email allowlist, records are scoped to the Access subject,
mutations require an exact configured Origin, and audit rows never contain
submitted values.

All 52 supported backend compositions are generated, dependency resolved, and
imported in CI. Invalid combinations fail before the destination directory is
written; for example, admin rejects an explicit `--auth none` and every
unreviewed frontend composition.

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
| `astro` | Static Astro site with a small Preact runtime island and generated API types |

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
in CI.

`astro` generates a pinned Node 24 static site in the same `frontend/`
boundary. Public content is imported at build time; authenticated TODO data is
requested only after the visible Preact island hydrates in the browser. React
and Astro share one generated OpenAPI contract component, so neither profile
maintains handwritten API models. Local development proxies `/api` to Hayate,
while Workers serves the static build and API from one origin. The generated
static-output audit rejects private data markers, and CI covers `npm ci`,
typecheck, static build, Chromium persistence/deep links, dependency audit,
and real-workerd routing. Astro SSR remains an explicit, adapter-backed BFF
extension rather than part of the initial runtime.

Non-`none` profiles are rejected with the production preset until each profile
has a reviewed production contract. The data-backed
[frontend compatibility matrix](docs/FRONTEND_COMPATIBILITY.md) is also the
CLI allow-list: pull requests exercise six boundary compositions from a built
wheel, while weekly and manual runs cover all 112 unique supported
runtime/frontend/auth/feature/entrypoint compositions in deterministic shards.
Each run publishes phase-level commands, exact tool versions, and the wheel
digest as JSON evidence.

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

Admin remains opt-in on the production preset:

```sh
uvx create-hayate my-app \
  --template workers \
  --preset production \
  --with admin
```

The admin profile copies unmodified MIT-licensed snapshots of reviewed,
exact commits into the generated source tree. This preserves offline,
zero-network generation and avoids floating branches and Pywrangler's
VCS-lock limitation; exact commits and licenses are recorded under `admin/`.
The generated site uses escaped plain-text branding, contrast-checked theme
tokens, hashed-CSP styling, keyboard/assistive-technology semantics, and the
upstream application-scoped message-catalog contract.

Local CI drives the generated preset over both real ASGI HTTP and real workerd.
The workerd path applies a real D1 migration, writes through the HTTP API, and
reads the same authenticated data through MCP.

## Design

- **Zero-dependency CLI.** Generation uses only the standard library and
  bundled, versioned components; it performs no network fetch.
- **Small composition surface.** One base app, one Workers runtime overlay,
  four feature components, and explicit auth/production components replace
  copied full-template combinations.
- **Orthogonal frontend ownership.** Runtime and backend features compose
  first; one frontend overlay may add only non-colliding files. htmx calls the
  same domain and storage functions as the JSON API; React consumes generated
  OpenAPI types without introducing a second backend; Astro keeps public
  build-time content separate from browser-only private state.
- **Portable application core.** `src/app.py` does not change between ASGI and
  Workers. Runtime resources enter through the Hayate request context.
- **Feature-complete Workers default.** `WorkerEntrypoint` remains the default.
  HTTP-only services can explicitly request `--workers-entrypoint global`.
- **Evidence over claims.** CI runs unit tests, every dependency composition,
  wheel-based frontend compatibility, real ASGI, real workerd, D1 migrations,
  MCP, workflow audit, and dependency audit.

The internal design memo (Japanese, per project convention) is
[DESIGN.md](DESIGN.md); release history is in [CHANGELOG.md](CHANGELOG.md).

> **Status: alpha (0.10.x).** Generated projects pin released compatibility
> lines. Public APIs may still move before 1.0.

## License

MIT
