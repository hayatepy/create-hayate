# $project_name web

This directory is a static Astro site with one deliberately small Preact
island. Hayate remains the only backend and the only owner of user identity,
validation, storage, and `/api` behavior.

```sh
npm ci
npm run api:check
npm run typecheck
npm run build
```

For local development, run Hayate from the project root:

```sh
uv run uvicorn app:app --app-dir src --reload
```

Then run `npm run dev` here. Astro proxies `/api` to
`http://127.0.0.1:8000`. Override that development-only destination with
`HAYATE_DEV_ORIGIN`; the built island always calls the current browser origin.

## Static and runtime data boundary

- `src/data/public.ts` contains public editorial data that may be rendered at
  build time.
- `src/components/WorkspaceIsland.tsx` requests identity-scoped data only
  inside a browser effect after its `client:visible` hydration boundary.
- `src/pages/` contains no API endpoints or Astro actions. Business behavior
  stays in Hayate.

Never fetch private, cookie-scoped, or user-specific Hayate data from Astro
frontmatter during a static build. `npm run check:static` inspects generated
HTML for private-data signatures and verifies the expected static routes.

## OpenAPI ownership

`openapi.json`, `src/api/schema.d.ts`, and the dependency-free Fetch transport
in `src/api/transport.ts` come from the same shared frontend contract as the
React profile. Do not hand-edit them. Run `npm run api:generate` after changing
Hayate routes and commit all three artifacts. `npm run api:check` fails when
any artifact drifts.

## Deployment and optional SSR

Publish `dist/` as static files. Route `/api/*`, `/openapi.json`, and `/docs`
to Hayate before static HTML handling. The generated Workers configuration
uses Cloudflare Static Assets with trailing-slash HTML and the generated
`404.html`.

Astro SSR is not part of this profile. If a real BFF is later required, add
the official adapter for the target host and opt only the required pages into
on-demand rendering. Do not duplicate Hayate endpoints, actions, validation,
or storage inside Astro.

Build the static site and run its browser smoke test with:

```sh
npx playwright install chromium
npm run test:e2e
```
