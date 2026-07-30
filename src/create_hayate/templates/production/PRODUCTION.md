# Production checklist

The preset supplies secure defaults but cannot know your Cloudflare account,
domains, identity policy, or rollout process. Complete every item before the
first production deployment.

## Identity and secrets

- Protect the Worker with a Cloudflare Access application and an explicit
  allow policy.
- Replace `ACCESS_TEAM_DOMAIN` and `ACCESS_AUD` in
  `[env.production.vars]`. Requests fail closed until they are correct.
- Do not commit application secrets. Add future secrets with
  `wrangler secret put --env production`.
- Confirm `/whoami` returns the Access subject expected by your tenancy model.
$admin_production_checklist

## Database

- Create the production D1 database and replace its placeholder
  `database_id`.
- Compile contracts: `uv run python scripts/check_sql_contracts.py`.
- Apply migrations before code:
  `uv run python manage_workers.py d1 migrations apply DB --remote --env production`.
- Back up data and define rollback/forward-fix ownership. The scaffold never
  applies production migrations implicitly.

## Browser and abuse boundaries

- Replace `CORS_ORIGINS` with the exact HTTPS origins that may call the API.
  Do not use `*` with authenticated traffic.
- Allocate account-unique rate-limit namespace IDs and review the generated
  60 requests/minute policy against expected workload.
- Keep the 1 MiB body limit or document and test a deliberate replacement.
- Review Cloudflare Access, rate-limit, D1, and Worker observability retention.
  Never record SQL text, bound values, Access JWTs, or personal data.
- Confirm access events contain `event`, `method`, `path`, `status`,
  `duration_ms`, and `request_id`, and that the configured sink parses each
  event as one JSON object. Query strings, headers, and bodies must remain
  absent.
- Define retention and incident-response access for request logs. Treat
  request IDs as correlation metadata, not authentication or authorization
  credentials.

## Build and deploy

- Keep `APP_VERSION` in both generated Wrangler environments equal to the
  application version in `pyproject.toml`. `X-App-Version` identifies that
  semantic release; `X-Worker-Version` identifies the exact Cloudflare Worker
  version created by the deploy. The generated version-metadata binding is not
  a secret and exposes only its bounded version ID. See Cloudflare's
  [version metadata binding](https://developers.cloudflare.com/workers/runtime-apis/bindings/version-metadata/).
- Run `uv run pytest`.
- Export and review `openapi.json`, `client/api-types.ts`, and the zero-runtime
  `client/api-client.ts` with `sh scripts/export_api.sh`.
- Run a production bundle inspection:
  `uv run python manage_workers.py deploy --dry-run --env production`.
- The generated `python_modules` exclusions remove ASGI/AWS adapters, WSGI,
  bytecode, and package metadata. Remove an exclusion only with a measured,
  tested reason.
- Deploy with `uv run python manage_workers.py deploy --env production`.
- Confirm both release headers after deployment:
  `curl --silent --head https://your-worker.example/health`.
  Match `X-Worker-Version` against `wrangler versions list` before shifting
  traffic or investigating a mixed-version rollout.
- Exercise `/health`, `/whoami`, `/todos`, `/docs`, and MCP `tools/call` from
  an Access-authenticated client before shifting traffic.

## Portable fallback

The identical `src/app.py` runs on ASGI for local verification:

```sh
uv run uvicorn app:app --app-dir src --reload
```

The Cloudflare Access strategy is Workers-specific in production. Choose a
different verified identity middleware before using ASGI as a production
deployment target.
