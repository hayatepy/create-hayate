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

## Build and deploy

- Run `uv run pytest`.
- Export and review `openapi.json` and `client/api-types.ts` with
  `sh scripts/export_api.sh`.
- Run a production bundle inspection:
  `uv run python manage_workers.py deploy --dry-run --env production`.
- The generated `python_modules` exclusions remove ASGI/AWS adapters, WSGI,
  bytecode, and package metadata. Remove an exclusion only with a measured,
  tested reason.
- Deploy with `uv run python manage_workers.py deploy --env production`.
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
