# Frontend compatibility

This is the published compatibility contract for `create-hayate` frontend
profiles. It is rendered from
`src/create_hayate/frontend_compatibility.json`; CI fails if this document,
the CLI allow-list, or the executable matrix drifts from that source.

## Supported axes

| Frontend | Templates | Required features | Optional features |
|---|---|---|---|
| htmx | api, workers, mcp | none | mcp, openapi, sql |
| react | api, workers, mcp | openapi | mcp, sql |
| astro | api, workers, mcp | openapi | mcp, sql |

- `api` supports `auth=none` and the class entrypoint.
- `workers` and the `mcp` shortcut support `auth=none|cloudflare-access` and
  `workers-entrypoint=class|global`.
- `mcp` is implicit in the `mcp` shortcut. `openapi` is implicit in React and
  Astro. Removing those duplicates leaves
  **112 unique supported frontend compositions**.
- Frontends remain intentionally incompatible with `--preset production`
  until each profile has a dedicated reviewed production contract.

## Exact CI toolchains

| Tool | Version |
|---|---|
| Python (ASGI smoke) | 3.14.6 |
| Python (Workers/full matrix) | 3.13.11 |
| Node.js | 24.18.0 |
| npm | 11.16.0 |
| uv | 0.11.28 |

Every run records the actual tool versions, wheel SHA-256, composition, phase,
command, exit code, and duration in the uploaded
`frontend-compatibility-evidence` JSON artifact. A run fails before generation
if any actual tool version differs from this contract. Browser cases also
record isolated, dynamically selected backend and frontend ports so an
unrelated local server cannot satisfy their readiness probes.

## Pull-request smoke cases

| Composition | Chromium | Real workerd |
|---|---|---|
| `htmx-api-none-class-base` | yes | no |
| `htmx-workers-cloudflare-access-global-mcp-openapi-sql` | no | yes |
| `react-api-none-class-openapi` | yes | no |
| `react-workers-cloudflare-access-global-mcp-openapi-sql` | no | yes |
| `astro-api-none-class-openapi` | yes | no |
| `astro-workers-cloudflare-access-global-mcp-openapi-sql` | no | yes |

Pull requests run these 6 boundary cases. A weekly schedule and
manual `workflow_dispatch` split all 112 compositions
across 12 deterministic shards. Scheduled workflows run from the
latest default-branch commit; manual runs can select `smoke` or `full`.

## Per-composition phases

1. Build `create-hayate` as a wheel and scaffold with
   `uvx --from <wheel> create-hayate ...`.
2. Create a Python lock with `uv lock`, then install only with
   `uv sync --locked`.
3. Run generated pytest, Ruff check, and Ruff format check.
4. For React/Astro, install `package-lock.json` with `npm ci`, export and
   drift-check OpenAPI, prove a stale artifact is rejected, regenerate it,
   typecheck, build, verify required assets, and run `npm audit`.
5. Run focused Chromium smoke tests with console/page errors treated as
   failures, plus representative real-workerd routing contracts.

The workflow and local entrypoint are:

```sh
uv run python scripts/check_frontend_matrix.py matrix --scope smoke
uv run python scripts/check_frontend_matrix.py run \
  --scope smoke \
  --selector react-api-none-class-openapi \
  --wheel dist/create_hayate-<version>-py3-none-any.whl \
  --evidence frontend-evidence
uv run python scripts/check_frontend_matrix.py matrix --scope full
```

The broader Hayate package-version contract remains in the ecosystem
[compatibility matrix](https://github.com/hayatepy/.github/blob/main/docs/COMPATIBILITY.md).
