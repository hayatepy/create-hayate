# $project_name web

This directory is an independently buildable React SPA. Hayate remains the
only backend; the browser consumes its checked-in OpenAPI contract through
same-origin `/api` requests.

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

Then run `npm run dev` here. Vite proxies `/api` to
`http://127.0.0.1:8000`. Override that development-only destination with
`HAYATE_DEV_ORIGIN`; the production bundle always uses `window.location.origin`.

## OpenAPI ownership

`openapi.json` is exported from the generated Hayate application.
`src/api/schema.d.ts` is generated from that document; do not hand-edit either
file. Run `npm run api:generate` after changing routes, then commit both files.
`npm run api:check` regenerates into a temporary directory and fails on drift.
Application code imports its request and response types from that generated
file, so there is no handwritten API model.

## Authentication

The client sets `credentials: "include"` and expects HttpOnly same-origin
cookies, or an explicitly implemented bearer flow. Never copy session tokens
into local storage. For Cloudflare Access, keep authentication at the edge and
let the browser send its protected same-origin cookie normally.

## Static hosting and deep links

Publish `dist/` as static files. Route `/api/*`, `/openapi.json`, and `/docs`
to Hayate before the SPA fallback. Rewrite navigation requests such as
`/about` to `index.html`, but never rewrite API requests. The generated Workers
configuration already applies these rules with Cloudflare Static Assets.

Run the real-browser smoke test with:

```sh
npx playwright install chromium
npm run test:e2e
```
