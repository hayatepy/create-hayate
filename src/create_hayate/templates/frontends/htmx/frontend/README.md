# htmx profile

This generated profile owns the HTML transport only. JSON and HTML routes call
the same todo domain and storage functions under `src/`; no second application
model is hidden in the frontend.

- UI: `/app`
- JSON API: `/api`
- identity boundary: `/auth`
- templates: `templates/`
- browser assets: `public/assets/`

`frontend/profile.toml` records the reviewed server integration, browser
version, and asset checksum. See the project README for ASGI, Workers, and
Chromium commands. ASGI installs the published `hayate-htmx>=0.1,<0.2`
release. Workers carries the reviewed 0.1 source snapshot under
`src/hayate_htmx` because its Pywrangler/Pyodide bundle does not install the
wheel at runtime. `manage_workers.py` regenerates an embedded Jinja
`DictLoader` snapshot before every Workers command, so `templates/` remains
the only editable source of HTML.
`public/_headers` gives the fingerprinted vendor asset the same immutable
cache contract on Cloudflare that the ASGI middleware applies locally.
