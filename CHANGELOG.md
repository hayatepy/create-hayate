# Changelog

All notable changes to create-hayate are documented here.

## Unreleased

### Added

- Add `--renderer jinja|htpy|jx|tdom` as an htmx-only generation axis. Jinja2
  remains the byte-for-byte default; htpy supports ASGI and Workers, while Jx
  and experimental Python 3.14 tdom target ASGI.
- Generate native page, fragment, validation, edit, item, and identity views
  for each explicit renderer with exact `hayate-htmx` extras, renderer
  metadata, strict mypy boundaries, and fail-fast runtime/Python constraints.
- Extend pull-request compatibility evidence from 6 to 10 cases with
  renderer-specific Chromium and real-workerd boundaries without weakening or
  replacing the existing 112-composition full matrix.

### Fixed

- Reject renderer and generated-tool dependency names as project names before
  generation, avoiding uv self-dependency cycles such as an htpy-rendered
  project named `htpy`.
- Keep the unrendered project manifest under a template-only filename so
  GitHub dependency submission does not parse generator placeholders as a
  real `pyproject.toml`.

## [0.11.1] - 2026-07-28

### Fixed

- Preserve separate Emscripten and CPython `rpds-py` resolutions in generated
  MCP universal locks so macOS can install Python 3.14 wheels instead of
  attempting the Pyodide-pinned 0.23.1 source build.
- Keep host-only development tools out of the Emscripten side of MCP locks so
  native packages such as Playwright cannot make Workers resolution fail.

## [0.11.0] - 2026-07-28

### Added

- Generate validated request correlation and compact structured access events
  by default, before identity, production controls, and optional features.
- Exercise safe response IDs, exact final statuses, and query exclusion
  through generated direct, ASGI, Workers class, and Workers global paths.

### Changed

- Generate projects on `hayate>=0.15.1,<0.16` so final handled responses are
  logged only after the application error boundary has selected their status.

## [0.10.0] - 2026-07-28

### Added

- Generate escaped plain-text admin branding with contrast-checked theme
  tokens, hashed-CSP styling, semantic landmarks, visible focus, reduced-motion
  handling, and application-scoped localization support.

### Changed

- Refresh the unmodified vendored `hayate-admin` snapshot to reviewed main
  commit `aedd4c4`, whose Python, SQLite, Chromium/axe, native D1, package,
  dependency, workflow, and CodeQL gates passed.
- Extend direct and native generated-project evidence to cover the safe theme
  and localized history output without adding ambient locale state, remote CSS,
  raw HTML, or `unsafe-inline`.

## [0.9.0] - 2026-07-28

### Added

- Generate commit-pinned `hayate-admin` 0.2 saved views, forward keyset
  pagination, and separately authorized bounded CSV exports from the opt-in
  admin profile.
- Exercise cursor traversal and CSV downloads through direct, Chromium, and
  native workerd/D1 gates.

### Changed

- Refresh the unmodified vendored admin snapshot to the reviewed 0.2.0 release
  commit and keep export and pagination access owner-scoped through generated
  checked SQL.

## [0.8.0] - 2026-07-28

### Added

- Add an opt-in `admin` feature that composes checked SQL and Cloudflare
  Access into an explicit identity-scoped operations UI with bounded
  search/sort/paging and persistent redacted object history.
- Generate exact operator allowlist and Origin trust boundaries, SQLite and D1
  audit storage, direct security/CRUD tests, an optional Chromium gate, and
  real-workerd bundle and mutation evidence.
- Bundle unmodified, commit-pinned, MIT-license-preserving `hayate-admin` 0.1
  and `hayate-htmx` 0.2 sources until their first PyPI publications make a
  normal portable Workers lock possible.

### Changed

- Expand the backend feature matrix from 42 to 52 reviewed compositions while
  retaining admin as an explicit production-preset opt-in.
- Use a first-primary D1 session for sequential storage reads and apply every
  ordered SQLite migration in generated SQL projects.

## [0.7.2] - 2026-07-27

### Changed

- Generate projects on the compatible `hayate>=0.13,<0.14` and
  `hayate-openapi>=0.7,<0.8` release lines so bounded multipart uploads and
  typed file contracts are available from the normal scaffold path.
## [0.7.1] - 2026-07-27

### Changed

- Generate new OpenAPI-enabled projects with `hayate-openapi` 0.6 and exercise
  portable typed query constraints in the default TODO API.

## [0.7.0] - 2026-07-27

### Added

- Generate a pinned Node 24, Vite, React Router, and TypeScript SPA with
  `openapi-fetch`, responsive starter UI, same-origin credential transport,
  production security headers, and no handwritten API models.
- Export the React profile's OpenAPI document and TypeScript types from the
  generated Hayate application, fail on artifact drift, and exercise
  `npm ci`, typecheck, build, dependency audit, Chromium CRUD/deep links, and
  Cloudflare Static Assets through real workerd.
- Generate a pinned static Astro site with public build-time content, a small
  visible Preact island for authenticated runtime state, local same-origin API
  proxying, static-output privacy checks, custom deep routes and 404s, and
  Cloudflare Static Assets routing through real workerd.
- Share one generated, drift-checked OpenAPI document, TypeScript schema, and
  `openapi-fetch` client between the React and Astro profiles, with no
  handwritten browser API models.
- Define the 112 unique supported frontend compositions as packaged data used
  by both the CLI allow-list and CI, with six built-wheel pull-request boundary
  cases and a 12-shard weekly or manually dispatched full matrix.
- Publish exact Python, Node, npm, and uv toolchains plus phase-level commands,
  artifact digests, failures, and timings as aggregated frontend compatibility
  evidence.

### Changed

- Move frontend smoke coverage into the data-driven compatibility workflow and
  make React and Astro browser console/page errors fail their generated gates.

### Fixed

- Include optional MCP routes in generated React and Astro OpenAPI contracts.
- Preserve frontend API prefixes and Cloudflare Access identity across the
  htmx, React, and Astro feature compositions.
- Isolate browser smoke tests on dynamic ports so unrelated local servers
  cannot satisfy backend or frontend readiness probes.
- Keep setup-uv's host `UV_PYTHON` override out of Pywrangler's nested Pyodide
  environment so compiled Wasm dependencies resolve on clean CI runners.

## [0.6.0] - 2026-07-27

### Added

- Add an independent `--frontend none|htmx|react|astro` generation-plan axis
  while preserving `none` as the compatibility default.
- Compose frontend-owned trees after every backend layer and reject frontend
  collisions before a partial project can survive.
- Add isolated profile metadata boundaries and fail-fast production
  compatibility constraints for the upcoming executable frontend profiles.
- Generate an executable Hayate + htmx profile with shared JSON/HTML domain
  logic, safe Jinja page/fragment rendering, CRUD validation, history, SSE,
  identity and CSRF boundaries, and responsive starter UI.
- Pin the reviewed hayate-htmx 0.1 release-gate commit and self-host htmx
  2.0.10 with recorded SHA-256/SRI, ASGI serving, Cloudflare Static Assets,
  direct tests, Chromium smoke tests, and a real workerd contract.
- Install the immutable hayate-htmx Git source on ASGI and bundle the same
  license-preserving source snapshot on Workers until Pywrangler can consume
  its VCS lock or the package is published.
- Regenerate a deterministic Jinja `DictLoader` module from canonical HTML
  before Workers commands, retaining editable file templates locally without
  relying on unsupported arbitrary files in the Python module bundle.
- Generate typed UUID path and response contracts from `hayate-openapi` 0.5
  for OpenAPI-enabled TODO APIs, while preserving the dependency-light
  Context-first implementation in minimal projects.
### Changed

- Add shared todo title normalization and update/toggle storage operations so
  API, htmx, in-memory, SQLite, and D1 compositions use one domain contract.
- Split TODO API registration into an overlay boundary so optional features
  can improve transport contracts without duplicating the application shell.
### Fixed

- Keep the generated Chromium smoke strict while accepting the one
  `net::ERR_ABORTED` signal produced when the completed SSE demo deliberately
  closes its `EventSource`.

## [0.5.1] - 2026-07-27

### Fixed

- Require hayate-openapi 0.4.2 so generated raw JSON Schema contracts are
  enforced at runtime as well as projected into OpenAPI without initializing
  the schema compiler in forbidden Workers global scope.
- Reject malformed TODO UUID route parameters in the shared application even
  without the OpenAPI feature, keeping the base scaffold lightweight while
  preserving the same public behavior across compositions.

## [0.5.0] - 2026-07-27

### Changed

- Generate projects on Hayate 0.12.1+ and hayate-openapi 0.4, completing the
  shared runtime/OpenAPI validation contract for JSON bodies and route
  parameters while retaining route middleware on the native Workers fast path.
- Reject malformed JSON through the core RFC 9457 validation path and emit the
  UUID route-parameter schema from the same generated application.
- Resolve and import all 42 supported compositions against the released
  package lines.

## [0.4.3] - 2026-07-27

### Changed

- Generate MCP and production projects on the released hayate-mcp 0.11 line,
  preserving MCP 2025-11-25 and existing Bearer/Cloudflare Access defaults.
- Check installed distribution metadata against the public `__version__`
  during ordinary CI. The signed v0.4.2 tag was rejected by this release
  invariant before build and was never published.

## [0.4.1] - 2026-07-26

### Changed

- Link generated projects and the published package description to the
  canonical ecosystem start page, production golden app, and tested
  compatibility evidence.

## [0.4.0] - 2026-07-26

### Added

- Add composable `openapi`, `mcp`, and `sql` feature generators plus explicit
  `none` and `cloudflare-access` identity strategies.
- Add a production preset that joins API routes, hardened Scalar docs, typed
  client export, MCP 2025-11-25, Access identity, D1, native rate limiting,
  CORS, security headers, and a deployment checklist.
- Test all 40 supported runtime/feature/auth/entrypoint combinations plus both
  production entrypoints for dependency resolution and import compatibility.
- Exercise the golden preset over real ASGI with SQLite and real workerd with
  D1, including an authenticated HTTP write read back through MCP.

### Changed

- Replace copied full application templates with one base app, one Workers
  runtime overlay, and small feature components. The `mcp` template is now a
  compatibility shortcut for `workers` plus the MCP component.
- Reject unsupported combinations before writing a destination directory and
  explain the compatible alternative.

## [0.3.0] - 2026-07-26

### Changed

- Align every generated project with Hayate 0.11.1+, whose lazy runtime
  adapter exports make the documented Workers exclusions deployable.
- Keep the feature-complete `WorkerEntrypoint` class as the Workers default
  while exposing the HTTP-only global handler through the explicit
  `--workers-entrypoint global` option.
- Reduce Workers uploads with safe module exclusions while retaining `uts46`;
  document the package-metadata trade-off and verify internationalized
  hostname behavior through real workerd.
- Record Wrangler's dry-run upload size and successful HTTP/MCP contract
  payloads in the real-workerd CI gate.

## [0.2.0] - 2026-07-25

### Added

- Add an `mcp` template with MCP 2025-11-25, input/output JSON Schema
  validation, request context, direct application tests, and one application
  that runs unchanged on ASGI and Cloudflare Python Workers.
- Exercise generated MCP projects through real workerd in CI without requiring
  `hayate-auth`, so existing identity providers remain a first-class path.
- Keep generated Workers launchers compatible with current Node.js 24 by
  filtering Pywrangler's obsolete experimental WASM flag.

## [0.1.3] - 2026-07-25

### Fixed

- Align generated Workers projects with workerd's Python 3.13 runtime and
  Pywrangler's supported Node.js 24 release.
- Add a cross-platform Workers launcher that rejects unsupported Node
  runtimes before Pywrangler can silently create an incomplete dependency
  bundle, and exercise that documented command against real workerd in CI.

## [0.1.2] - 2026-07-24

### Changed

- Generate the Workers template in CI and drive its CRUD API through a real
  workerd process, in addition to the direct application tests.
- Mark the distribution as typed and validate the public source with strict
  mypy.
- Audit locked dependencies on every change and publish an SPDX SBOM plus
  GitHub build and SBOM attestations with each release.

## [0.1.1] - 2026-07-24

### Changed

- Align package metadata, CI, documentation, and the protected release path
  for the public 0.1 line.

## [0.1.0] - 2026-07-22

### Added

- Add a zero-dependency CLI with bundled API and Cloudflare Workers templates,
  generated-project tests, and non-interactive operation.
